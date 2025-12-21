"""
Starlette‑Admin configuration for the Vekolom project.

This module initialises the Starlette‑Admin instance and registers
database models so that administrative users can manage the site
content through a web UI.  Authentication is handled by
``SimpleAdminAuthProvider``, which reads credentials from environment
variables via ``Settings``.

In addition to creating the admin instance, this file registers
SQLAlchemy models corresponding to the home page.  Additional models
should be added here as other modules of the project are migrated.
"""

from sqlalchemy import create_engine
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette_admin.auth import AdminUser, AuthProvider
from starlette_admin.contrib.sqla import Admin, ModelView
from starlette_admin.exceptions import LoginFailed

from app.settings.config import Settings
from app.modules.home.infrastructure.sa_models import (
    CoreSeo,
    MainCarousel,
    MainText,
    Action,
    Accept,
    Slogan,
)


class SimpleAdminAuthProvider(AuthProvider):
    """
    Simple username/password authentication.

    For production deployments you should replace this with a more
    sophisticated authentication method (OAuth, JWT, etc.).
    """

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    async def login(self, request: Request) -> AdminUser:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        if username == self._username and password == self._password:
            request.session["admin_user"] = {"username": username}
            return AdminUser(username=username)

        raise LoginFailed("Invalid username or password")

    async def is_authenticated(self, request: Request) -> bool:
        return "admin_user" in request.session

    async def get_admin_user(self, request: Request) -> AdminUser:
        data = request.session.get("admin_user") or {}
        return AdminUser(username=data.get("username", "admin"))

    async def logout(self, request: Request) -> None:
        request.session.clear()


def build_admin(s: Settings) -> Admin:
    """
    Construct and configure the Starlette‑Admin instance.

    This function creates a synchronous SQLAlchemy engine for the admin
    (because starlette‑admin currently does not support async engines),
    registers the necessary models, and applies session middleware for
    authentication.  It reads credentials and the secret key from the
    application settings.
    """

    # Create synchronous engine for admin use.
    engine = create_engine(str(s.database.sync_dsn), pool_pre_ping=True)

    admin = Admin(
        engine,
        title="Vekolom Admin",
        auth_provider=SimpleAdminAuthProvider(
            username=s.app.ADMIN_USERNAME,
            password=s.app.ADMIN_PASSWORD,
        ),
        middlewares=[
            Middleware(SessionMiddleware, secret_key=s.app.SESSION_SECRET_KEY),
        ],
    )

    # Register models from the home module.  Each call to ``add_model``
    # exposes a SQLAlchemy model in the admin UI with default list,
    # create, edit and delete views.  You can customise the behaviour
    # by passing a subclass of ``ModelView`` with additional
    # configuration (e.g. column labels, form validation, etc.).
    admin.add_model(ModelView(CoreSeo))
    admin.add_model(ModelView(MainCarousel))
    admin.add_model(ModelView(MainText))
    admin.add_model(ModelView(Action))
    admin.add_model(ModelView(Slogan))
    admin.add_model(ModelView(Accept))

    return admin