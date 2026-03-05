# controllers/admin_controller.py

import json
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from common.config.settings import get_settings
from logic.util.scrapper.pipeline_runner import PipelineRunner

templates = Jinja2Templates(directory="templates")

# Single shared runner instance across all requests
_runner: Optional[PipelineRunner] = None


def get_runner() -> PipelineRunner:
    global _runner
    if _runner is None:
        s = get_settings()
        _runner = PipelineRunner(
            database_url   = s.database_url,
            openai_api_key = s.openai_api_key,
        )
    return _runner


class AdminController:

    def __init__(self):
        self.router   = APIRouter()
        self.settings = get_settings()
        self._register_routes()

    def _register_routes(self):

        # ── Main admin page ──────────────────────────────────────────────────

        @self.router.get("/admin", response_class=HTMLResponse)
        async def admin(request: Request):
            runner = get_runner()
            return templates.TemplateResponse("admin.html", {
                "request": request,
                "states":  {k: v.__dict__ for k, v in runner.states.items()},
            })

        # ── SSE stream ───────────────────────────────────────────────────────

        @self.router.get("/admin/stream")
        async def admin_stream(request: Request):
            runner = get_runner()
            q      = runner.subscribe()

            # Send current state immediately on connect
            initial = json.dumps({k: {**v.__dict__, "status": str(v.status)}
                                   for k, v in runner.states.items()})

            async def event_generator():
                try:
                    yield f"event: init\ndata: {initial}\n\n"
                    while True:
                        if await request.is_disconnected():
                            break
                        try:
                            msg = q.get(timeout=1)
                            yield msg
                        except Exception:
                            yield ": keepalive\n\n"
                finally:
                    runner.unsubscribe(q)

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        # ── Action: Scrape ───────────────────────────────────────────────────

        @self.router.post("/admin/scrape/{portal}")
        async def scrape(portal: str, request: Request):
            if portal not in ("argenprop", "zonaprop"):
                return {"ok": False, "error": "Unknown portal"}
            body             = await request.json()
            neighborhood     = body.get("neighborhood", "belgrano")
            max_pages        = int(body.get("max_pages", 3))
            started          = get_runner().run_scrape(portal, neighborhood, max_pages)
            return {"ok": started, "msg": "Started" if started else "Already running"}

        # ── Action: Insert ───────────────────────────────────────────────────

        @self.router.post("/admin/insert")
        async def insert(request: Request):
            body    = await request.json()
            portals = body.get("portals", ["argenprop", "zonaprop"])
            started = get_runner().run_insert(portals)
            return {"ok": started, "msg": "Started" if started else "Already running"}

        # ── Action: Embed ────────────────────────────────────────────────────

        @self.router.post("/admin/embed")
        async def embed():
            started = get_runner().run_embed(batch_size=20)
            return {"ok": started, "msg": "Started" if started else "Already running"}