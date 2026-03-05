# controllers/property_controller.py

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from common.config.settings import get_settings
from data_access_layer.property_manager import PropertyManager

templates = Jinja2Templates(directory="templates")


class PropertyController:

    def __init__(self):
        self.router   = APIRouter()
        self.settings = get_settings()
        self.manager  = PropertyManager(self.settings.database_url)
        self._register_routes()

    def _register_routes(self):

        @self.router.get("/properties", response_class=HTMLResponse)
        async def properties(
            request:        Request,
            neighborhood:   Optional[str] = Query(default=None),
            ambientes:      Optional[str] = Query(default=None),  # str to handle empty string
            price_min:      Optional[str] = Query(default=None),  # str to handle empty string
            price_max:      Optional[str] = Query(default=None),  # str to handle empty string
            source:         Optional[str] = Query(default=None),
            page:           Optional[str] = Query(default=None),  # str to handle empty string
        ):
            page_size = 24

            # Safely convert all params — empty string treated as None
            neighborhood_val = neighborhood.strip() or None if neighborhood else None
            ambientes_val    = int(ambientes)   if ambientes  and ambientes.strip()  else None
            price_min_val    = float(price_min) if price_min  and price_min.strip()  else None
            price_max_val    = float(price_max) if price_max  and price_max.strip()  else None
            source_val       = source.strip() or None if source else None
            page_val         = int(page) if page and page.strip() else 1
            offset           = (page_val - 1) * page_size

            property_list = self.manager.get_properties(
                neighborhood = neighborhood_val,
                ambientes    = ambientes_val,
                price_min    = price_min_val,
                price_max    = price_max_val,
                source       = source_val,
                limit        = page_size,
                offset       = offset,
            )
            neighborhoods = self.manager.get_neighborhoods()

            return templates.TemplateResponse("properties.html", {
                "request":       request,
                "properties":    [p.to_dict() for p in property_list],
                "neighborhoods": neighborhoods,
                "filters": {
                    "neighborhood": neighborhood_val,
                    "ambientes":    ambientes_val,
                    "price_min":    price_min_val,
                    "price_max":    price_max_val,
                    "source":       source_val,
                },
                "page":     page_val,
                "has_more": len(property_list) == page_size,
            })