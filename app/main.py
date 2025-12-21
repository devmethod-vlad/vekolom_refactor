"""FastAPI application factory for the Vekolom project.

This module constructs the FastAPI app, configures dependency
injection via Dishka, mounts static files, includes routers, and
attaches the admin interface.

It also defines a lifespan context manager to:

* ensure the database exists (create it if missing)
* run Alembic migrations (`upgrade head`)
* properly close the Dishka container on shutdown

Why migrations in lifespan?
---------------------------
Because you explicitly asked for "check DB + migrate" at application start.

Caveat for production:
Running migrations on startup is convenient, but be mindful of:
* permissions (CREATE DATABASE)
* concurrency (multiple app instances). We handle concurrency with a Postgres
  advisory lock in `app.infrastructure.db.bootstrap`.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
from app.infrastructure.set_logging import setup_logging

from app.admin.admin import build_admin
from app.infrastructure.db.bootstrap import bootstrap_database
from app.ioc.container import build_container
from app.modules.home.presentation.router import router as home_router
from app.settings.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""

    # 1) Ensure target DB exists and schema is up-to-date.
    #    Run in a thread to avoid blocking the event loop.
    await asyncio.to_thread(bootstrap_database, settings.database)

    yield

    # 2) Dispose resources (DB engines, etc.) managed by Dishka.
    await app.state.dishka_container.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    setup_logging(debug=settings.app.DEBUG)
    app = FastAPI(lifespan=lifespan, debug=settings.app.DEBUG)

    # Initialise dependency injection container.
    container = build_container()
    setup_dishka(container=container, app=app)

    # Mount static files (CSS, JS, images).
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # Include routers.
    app.include_router(home_router)

    # Build and mount the admin interface.
    admin = build_admin(settings)
    admin.mount_to(app)

    return app


# Expose the app instance for ASGI servers.
app = create_app()
