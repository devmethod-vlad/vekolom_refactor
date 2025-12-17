from sqlalchemy import create_engine
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette_admin.auth import AdminUser, AuthProvider
from starlette_admin.contrib.sqla import Admin
from starlette_admin.exceptions import LoginFailed

from app.settings.config import Settings


class SimpleAdminAuthProvider(AuthProvider):
    """Простейшая auth-схема под .env (позже можно заменить на OAuth/SSO)."""

    def __init__(self, username: str, password: str):
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
    return admin
