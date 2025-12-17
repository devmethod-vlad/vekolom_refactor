from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
from dishka.integrations.fastapi import setup_dishka

from app.admin.admin import build_admin
from app.ioc.container import build_container
from app.modules.home.presentation.router import router as home_router
from app.settings.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Dishka рекомендует закрывать контейнер на завершение приложения :contentReference[oaicite:10]{index=10}
    await app.state.dishka_container.close()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan, debug=settings.app.DEBUG)

    # DI
    container = build_container()
    setup_dishka(container=container, app=app)

    # Static
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # Routers
    app.include_router(home_router)

    # Admin
    admin = build_admin(settings)
    admin.mount_to(app)

    return app


app = create_app()
