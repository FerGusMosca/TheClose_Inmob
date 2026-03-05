from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uvicorn
from starlette.middleware.sessions import SessionMiddleware
from common.config.settings import get_settings
from controllers.dashboard_controller import DashboardController
from controllers.property_controller import PropertyController
from controllers.admin_controller import AdminController

settings = get_settings()
app = FastAPI()
templates = Jinja2Templates(directory="templates")

app.add_middleware(SessionMiddleware, secret_key=settings.session_key)

# Static folder
app.mount("/static", StaticFiles(directory="static"), name="static")


# ===========================
#       MAIN DASHBOARD
# ===========================
@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    return templates.TemplateResponse("main_dashboard.html", {"request": request})


# ===========================
#       CONTROLLERS
# ===========================

main_dashboard = DashboardController()
app.include_router(main_dashboard.router)

properties = PropertyController()
app.include_router(properties.router)

admin = AdminController()
app.include_router(admin.router)


# ===========================
#           RUN
# ===========================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(settings.port),
                reload=False,
                timeout_keep_alive=120,
                workers=1)