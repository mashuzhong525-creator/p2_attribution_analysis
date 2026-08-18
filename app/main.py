"""FastAPI 应用工厂与入口。"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import admin_routes, attachment_routes, auth_routes, chat_routes, task_routes
from .config import settings
from .database import init_db
from .ws import router as ws_router

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "web" / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    for router in (
        auth_routes.router,
        chat_routes.router,
        attachment_routes.router,
        task_routes.router,
        admin_routes.router,
        ws_router,
    ):
        app.include_router(router)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
