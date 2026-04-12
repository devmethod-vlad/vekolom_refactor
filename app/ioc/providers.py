from __future__ import annotations

import typing as tp

from dishka import Provider, Scope, provide
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.async_database import AsyncDatabase
from app.infrastructure.uow import AsyncUnitOfWork
from app.infrastructure.web.assets import ViteAssetManager
from app.infrastructure.web.csrf import csrf_input_callable
from app.infrastructure.web.css_assets import CustomCSSManager
from app.infrastructure.web.legacy_assets import LegacyAssetManager
from app.modules.apikeys.application.use_cases import GetSmartCaptchaKeys, GetYandexMapsApiKey
from app.modules.apikeys.domain.repositories import ApiKeysReadRepository
from app.modules.apikeys.infrastructure.repositories import SAApiKeysReadRepository
from app.modules.home.application.use_cases import GetHomePage
from app.modules.home.domain.repositories import HomeReadRepository
from app.modules.home.infrastructure.repositories import SAHomeReadRepository
from app.modules.pricelist.application.use_cases import GetPricelistPage
from app.modules.pricelist.domain.repositories import PricelistReadRepository
from app.modules.pricelist.infrastructure.repositories import SAPricelistReadRepository
from app.modules.contacts.application.use_cases import GetContactsPage, SubmitContactForm
from app.modules.contacts.domain.repositories import (
    ContactsReadRepository,
    ContactsWriteRepository,
)
from app.modules.contacts.infrastructure.repositories import (
    SAContactsReadRepository,
    SAContactsWriteRepository,
)
from app.settings.config import PostgresSettings, Settings, settings


class SettingsProvider(Provider):
    @provide(scope=Scope.APP)
    def get_settings(self) -> Settings:
        return settings

    @provide(scope=Scope.APP)
    def get_postgres(self, s: Settings) -> PostgresSettings:
        return s.database


class DatabaseProvider(Provider):
    @provide(scope=Scope.APP)
    async def get_async_db(self, pg: PostgresSettings) -> tp.AsyncIterator[AsyncDatabase]:
        db = AsyncDatabase.from_config(pg)
        try:
            yield db
        finally:
            await db.engine.dispose()

    @provide(scope=Scope.REQUEST)
    async def get_session(self, db: AsyncDatabase) -> tp.AsyncIterator[AsyncSession]:
        async with db.session_factory() as session:
            yield session


class TemplatesProvider(Provider):
    @provide(scope=Scope.APP)
    def get_templates(self) -> Jinja2Templates:
        templates = Jinja2Templates(directory="app/templates")

        # --- Vite (современный JS/CSS) ---
        vite = ViteAssetManager(settings)
        templates.env.globals["vite_styles"] = vite.render_styles
        templates.env.globals["vite_preloads"] = vite.render_preloads
        templates.env.globals["vite_scripts"] = vite.render_scripts
        templates.env.globals["vite_dev_client"] = vite.render_dev_client

        # Оставляем для обратной совместимости на время миграции
        templates.env.globals["vite_assets"] = vite.render_tags

        templates.env.globals["use_vite_assets"] = vite.enabled

        # --- Legacy JS (jQuery и плагины) ---
        # Полностью обходит Vite pipeline: в dev — отдельные <script> теги
        # через FastAPI StaticFiles, в prod — один сбандлированный legacy.min.js.
        # Подробнее: app/infrastructure/web/legacy_assets.py
        legacy = LegacyAssetManager(settings)
        templates.env.globals["legacy_scripts"] = legacy.render

        # --- Custom CSS (пользовательские стили) ---
        # Аналогичная схема: в dev — отдельные <link> теги,
        # в prod — один минифицированный CSS-бандл.
        # Подробнее: app/infrastructure/web/css_assets.py
        css = CustomCSSManager(settings)
        templates.env.globals["custom_css"] = css.render

        # --- SEO globals ---
        # site_url — каноничный домен (https://vekolom.ru),
        # используется шаблонами для canonical URL и Open Graph.
        templates.env.globals["site_url"] = settings.seo.SITE_URL
        templates.env.globals["og_image_default"] = (
            f"{settings.seo.SITE_URL}"
            f"{settings.static.STATIC_URL}"
            f"{settings.seo.OG_IMAGE_PATH}"
        )

        # --- CSRF-защита ---
        # csrf_input(request) — Jinja2-глобал, генерирующий <input type="hidden">
        # с CSRF-токеном внутри формы. Использование: {{ csrf_input(request) }}.
        # Функция принимает request, чтобы достать токен из request.state.
        templates.env.globals["csrf_input"] = csrf_input_callable

        return templates


class HomeProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def get_home_repo(self, session: AsyncSession) -> HomeReadRepository:
        return SAHomeReadRepository(session)

    @provide(scope=Scope.APP)
    def get_home_use_case(self) -> GetHomePage:
        return GetHomePage()


class PricelistProvider(Provider):
    """DI-провайдер для модуля pricelist.

    Регистрирует:
      - PricelistReadRepository → SAPricelistReadRepository  (REQUEST scope)
      - GetPricelistPage                                      (APP scope)
    """

    @provide(scope=Scope.REQUEST)
    def get_pricelist_repo(self, session: AsyncSession) -> PricelistReadRepository:
        return SAPricelistReadRepository(session)

    @provide(scope=Scope.APP)
    def get_pricelist_use_case(self) -> GetPricelistPage:
        return GetPricelistPage()


class ContactsProvider(Provider):
    """DI-провайдер для модуля contacts.

    Регистрирует:
      - ContactsReadRepository  → SAContactsReadRepository   (REQUEST scope)
      - ContactsWriteRepository → SAContactsWriteRepository  (REQUEST scope)
      - GetContactsPage                                       (APP scope)
      - SubmitContactForm                                     (APP scope)
    """

    @provide(scope=Scope.REQUEST)
    def get_contacts_repo(self, session: AsyncSession) -> ContactsReadRepository:
        return SAContactsReadRepository(session)

    @provide(scope=Scope.REQUEST)
    def get_contacts_write_repo(self, session: AsyncSession) -> ContactsWriteRepository:
        return SAContactsWriteRepository(session)

    @provide(scope=Scope.APP)
    def get_contacts_page_use_case(self) -> GetContactsPage:
        return GetContactsPage()

    @provide(scope=Scope.APP)
    def get_submit_contact_form_use_case(self) -> SubmitContactForm:
        return SubmitContactForm()


class ApiKeysProvider(Provider):
    """DI-провайдер для модуля apikeys.

    Регистрирует:
      - ApiKeysReadRepository → SAApiKeysReadRepository  (REQUEST scope)
      - GetYandexMapsApiKey                               (APP scope)
      - GetSmartCaptchaKeys                               (APP scope)
    """

    @provide(scope=Scope.REQUEST)
    def get_apikeys_repo(self, session: AsyncSession) -> ApiKeysReadRepository:
        return SAApiKeysReadRepository(session)

    @provide(scope=Scope.APP)
    def get_yandex_maps_key_use_case(self) -> GetYandexMapsApiKey:
        return GetYandexMapsApiKey()

    @provide(scope=Scope.APP)
    def get_smartcaptcha_keys_use_case(self) -> GetSmartCaptchaKeys:
        return GetSmartCaptchaKeys()


class UoWProvider(Provider):
    """DI-провайдер для AsyncUnitOfWork.

    Собирает UoW из сессии и всех зарегистрированных репозиториев.
    Вынесен в отдельный Provider, т.к. зависит от репозиториев
    нескольких модулей (home + pricelist + contacts + apikeys).
    """

    @provide(scope=Scope.REQUEST)
    def get_uow(
        self,
        session: AsyncSession,
        home_repo: HomeReadRepository,
        pricelist_repo: PricelistReadRepository,
        contacts_repo: ContactsReadRepository,
        contacts_write_repo: ContactsWriteRepository,
        apikeys_repo: ApiKeysReadRepository,
    ) -> AsyncUnitOfWork:
        return AsyncUnitOfWork(
            session=session,
            home_repo=home_repo,
            pricelist_repo=pricelist_repo,
            contacts_repo=contacts_repo,
            contacts_write_repo=contacts_write_repo,
            apikeys_repo=apikeys_repo,
        )
