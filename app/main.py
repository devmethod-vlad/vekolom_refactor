"""
FastAPI application factory for the Vekolom project.

This module constructs the FastAPI app, configures dependency
injection via Dishka, mounts static files, includes routers, and
attaches the admin interface.  It also defines a lifespan context
manager to ensure resources like the DI container are properly
closed when the application shuts down.
"""

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
    """
    Manage application startup and shutdown.

    On shutdown the Dishka container is closed which disposes of
    resources like database engines.  Additional cleanup hooks can
    be added here as more parts of the application are implemented.
    """
    yield
    await app.state.dishka_container.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(lifespan=lifespan, debug=settings.app.DEBUG)

    # Initialise dependency injection container.
    container = build_container()
    setup_dishka(container=container, app=app)

    # Mount static files (CSS, JS, images).  Adjust the directory
    # parameter to reflect where your static files reside in the
    # project.  If using a separate frontend build pipeline, you may
    # need to update this path.
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # Include routers.
    app.include_router(home_router)

    # Build and mount the admin interface.
    admin = build_admin(settings)
    admin.mount_to(app)

    return app


# Expose the app instance for ASGI servers.
app = create_app()