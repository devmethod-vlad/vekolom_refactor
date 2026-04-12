"""
HTTP routing for the home module.

Контекст шаблона соответствует переменным оригинального Django-вью:

    seo        ← CoreSeo (объект, не queryset)
    slides     ← list[CarouselSlide]
    main       ← list[MainBlock]
    action1    ← ActionItem | None
    action2    ← ActionItem | None
    action3    ← ActionItem | None
    slogan1    ← list[Slogan]
    priem      ← list[PriemItem]
    positions  ← list[dict]  (пустой до миграции pricelist)
    debug_flag ← bool  (из settings.app.DEBUG)
    yandex_maps_api_key ← str  (API-ключ Яндекс.Карт из модуля apikeys)

Дополнительно в Jinja2-окружении зарегистрированы глобалы (см. providers.py):
    static(path) -> /static/{path}
    media(path)  -> /media/{path}
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.infrastructure.uow import AsyncUnitOfWork
from app.modules.apikeys.application.use_cases import GetYandexMapsApiKey
from app.modules.home.application.use_cases import GetHomePage
from app.settings.config import settings


router = APIRouter(route_class=DishkaRoute)


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    templates: FromDishka[Jinja2Templates],
    use_case: FromDishka[GetHomePage],
    maps_key_uc: FromDishka[GetYandexMapsApiKey],
    uow: FromDishka[AsyncUnitOfWork],
) -> HTMLResponse:
    page = await use_case.execute(uow)

    # Получаем API-ключ Яндекс.Карт из модуля apikeys
    yandex_maps_api_key = await maps_key_uc.execute(uow)

    return templates.TemplateResponse(
        "home/home.html",
        {
            "request": request,
            # соответствие Django-контексту
            "seo": page.seo,
            "slides": page.slides,
            "main": page.main,
            "action1": page.action1,
            "action2": page.action2,
            "action3": page.action3,
            "slogan1": page.slogan1,
            "priem": page.priem,
            "positions": page.positions,
            # в Django передавался из settings.DEBUG
            "debug_flag": settings.app.DEBUG,
            # API-ключ Яндекс.Карт (из БД через модуль apikeys)
            "yandex_maps_api_key": yandex_maps_api_key,
        },
    )
