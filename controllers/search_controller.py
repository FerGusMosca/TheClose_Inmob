# controllers/search_controller.py
import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from common.config.settings import get_settings
from common.dto.property_answer import PropertyAnswer
from common.util.search.property_searcher import PropertySearcher

log       = logging.getLogger(__name__)
templates = Jinja2Templates(directory="templates")


class SearchController:

    def __init__(self):
        self.router   = APIRouter()
        self.settings = get_settings()
        self._register_routes()

    def _get_searcher(self) -> PropertySearcher:
        if not hasattr(self, "_searcher"):
            self._searcher = PropertySearcher(
                database_url   = self.settings.database_url,
                openai_api_key = self.settings.openai_api_key,
            )
        return self._searcher

    def _get_answerer(self) -> PropertyAnswer:
        if not hasattr(self, "_answerer"):
            self._answerer = PropertyAnswer(
                openai_api_key  = self.settings.openai_api_key,
                prompt_path     = self.settings.prompt_query_properties,
                llm_class       = self.settings.llm_class,
                llm_model       = self.settings.llm_model,
                llm_temperature = self.settings.llm_temperature,
            )
        return self._answerer

    def _register_routes(self):

        @self.router.get("/search", response_class=HTMLResponse)
        async def search_page(request: Request):
            return templates.TemplateResponse("search.html", {"request": request})

        @self.router.post("/search/query")
        async def search_query(request: Request):
            body  = await request.json()
            query = (body.get("query") or "").strip()
            if not query:
                return JSONResponse({"answer": "Escribí una consulta.", "cards": []})

            try:
                # Extract hints from query to improve search precision
                neighborhood = _extract_neighborhood(query)
                top_k        = _extract_top_k(query)

                context = self._get_searcher().search(
                    query        = query,
                    neighborhood = neighborhood,
                    top_k        = top_k,
                )
                answer = self._get_answerer().get_answer(context)
                cards  = [_to_card(p) for p in context.properties]
                return JSONResponse({"answer": answer, "cards": cards})
            except Exception as e:
                log.exception("search_query error")
                return JSONResponse({"answer": f"Error: {e}", "cards": []}, status_code=500)


def _to_card(p) -> dict:
    return {
        "id": p.id, "title": p.title, "address": p.address,
        "neighborhood": p.neighborhood, "ambientes": p.ambientes,
        "dormitorios": p.dormitorios, "banos": p.banos,
        "m2_total": p.m2_total, "price": p.price, "currency": p.currency,
        "expensas": p.expensas, "source": p.source, "url": p.url,
    }

# Known CABA neighborhoods → DB slug mapping
_NEIGHBORHOOD_MAP = {
    "belgrano": "belgrano", "recoleta": "recoleta", "palermo": "palermo",
    "caballito": "caballito", "nunez": "nunez", "núñez": "nunez",
    "cañitas": "las-canitas", "canitas": "las-canitas", "las cañitas": "las-canitas",
    "villa urquiza": "villa-urquiza", "almagro": "almagro",
    "villa crespo": "villa-crespo", "san telmo": "san-telmo",
    "puerto madero": "puerto-madero", "flores": "flores",
    "floresta": "floresta", "colegiales": "colegiales",
    "barrio norte": "recoleta", "retiro": "retiro",
    "saavedra": "saavedra", "boedo": "boedo",
}

def _extract_neighborhood(query: str):
    """Returns DB slug if a known neighborhood is mentioned in the query."""
    q = query.lower()
    for name, slug in _NEIGHBORHOOD_MAP.items():
        if name in q:
            return slug
    return None

def _extract_top_k(query: str) -> int:
    """Returns the number mentioned in the query (e.g. 'dame 5') capped at 20, default 8."""
    import re
    # Match patterns like "dame 3", "las 5 más", "top 10", "3 propiedades"
    m = re.search(r"\b(\d+)\b", query)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 20:
            return n
    return 8