"""
HTTP routing for the pricelist module.

Контекст шаблона соответствует переменным оригинального Django-вью
``pricelist(request)`` из pricelist/views.py:

    debug_flag  ← bool  (из settings.app.DEBUG)
    date        ← Sequence[PriceDate]
    fotos       ← Sequence[Foto]
    seo         ← Sequence[PricelistSeo]
    categories  ← Sequence[Category]  (order_by('-name'))
    positions   ← Sequence[PositionEntity]  (order_by('order'))

В Django вью выбирал шаблон pricelist/dev/pricelist.html или
pricelist/prod/pricelist.html в зависимости от DEBUG.
Здесь используется один шаблон pricelist/pricelist.html
(dev/prod логика CSS остаётся на уровне base.html).
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.infrastructure.uow import AsyncUnitOfWork
from app.modules.pricelist.application.use_cases import GetPricelistPage
from app.settings.config import settings


router = APIRouter(route_class=DishkaRoute)


@router.get("/pricelist/", response_class=HTMLResponse)
async def pricelist(
    request: Request,
    templates: FromDishka[Jinja2Templates],
    use_case: FromDishka[GetPricelistPage],
    uow: FromDishka[AsyncUnitOfWork],
) -> HTMLResponse:
    """Страница прайс-листа.

    Аналог Django view ``def pricelist(request)`` из pricelist/views.py.
    """
    page = await use_case.execute(uow)

    return templates.TemplateResponse(
        "pricelist/pricelist.html",
        {
            "request": request,
            # соответствие Django-контексту
            "debug_flag": page.debug_flag,
            "date": page.date,
            "fotos": page.fotos,
            "seo": page.seo,
            "categories": page.categories,
            "positions": page.positions,
        },
    )
