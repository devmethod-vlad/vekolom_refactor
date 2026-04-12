"""
HTTP routing for AMP (Accelerated Mobile Pages) versions of public pages.

AMP-версии повторяют тот же контент, что и основные страницы, но
используют AMP-совместимую разметку и компоненты. Данные для рендеринга
берутся из тех же use case'ов, что и для обычных страниц — дублирования
бизнес-логики нет.

Маршруты:
    GET  /amp/                 — AMP-версия главной страницы
    GET  /amp/pricelist/       — AMP-версия прайс-листа
    GET  /amp/contacts/        — AMP-версия страницы контактов
    POST /amp/contacts/submit/ — XHR-обработчик формы контактов для amp-form

Каждая AMP-страница содержит:
    - <link rel="canonical" href="..."> — ссылка на основную (не-AMP) версию
    - Основные страницы содержат <link rel="amphtml" href="..."> — ссылку сюда

amp-form:
    AMP-формы отправляются через XHR (action-xhr), не через стандартный POST.
    Сервер обязан вернуть JSON-ответ с CORS-заголовками:
      - Access-Control-Allow-Origin: <source-origin>
      - AMP-Access-Control-Allow-Source-Origin: <source-origin>
      - Access-Control-Expose-Headers: AMP-Access-Control-Allow-Source-Origin
    Подробнее: https://amp.dev/documentation/guides-and-tutorials/learn/amp-caches-and-cors/amp-cors-requests/

Подробнее о требованиях AMP:
    https://amp.dev/documentation/guides-and-tutorials/start/create/basic_markup
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.infrastructure.uow import AsyncUnitOfWork
from app.modules.contacts.application.use_cases import (
    ContactFormData,
    GetContactsPage,
    SubmitContactForm,
)
from app.modules.home.application.use_cases import GetHomePage
from app.modules.pricelist.application.use_cases import GetPricelistPage
from app.settings.config import settings


logger = logging.getLogger("app.amp.router")

router = APIRouter(prefix="/amp", route_class=DishkaRoute)


@router.get("/", response_class=HTMLResponse)
async def amp_home(
    request: Request,
    templates: FromDishka[Jinja2Templates],
    use_case: FromDishka[GetHomePage],
    uow: FromDishka[AsyncUnitOfWork],
) -> HTMLResponse:
    """AMP-версия главной страницы.

    Использует тот же use case ``GetHomePage``, что и основная страница.
    Карта Яндекс не подключается — AMP не поддерживает произвольный JS.
    """
    page = await use_case.execute(uow)

    return templates.TemplateResponse(
        "amp/home.html",
        {
            "request": request,
            "seo": page.seo,
            "slides": page.slides,
            "main": page.main,
            "action1": page.action1,
            "action2": page.action2,
            "action3": page.action3,
            "slogan1": page.slogan1,
            "priem": page.priem,
            "positions": page.positions,
        },
    )


@router.get("/pricelist/", response_class=HTMLResponse)
async def amp_pricelist(
    request: Request,
    templates: FromDishka[Jinja2Templates],
    use_case: FromDishka[GetPricelistPage],
    uow: FromDishka[AsyncUnitOfWork],
) -> HTMLResponse:
    """AMP-версия страницы прайс-листа.

    Использует тот же use case ``GetPricelistPage``, что и основная страница.
    Лайтбокс фотографий — через атрибут ``lightbox`` у ``amp-img``,
    активируемый компонентом ``amp-lightbox-gallery``.
    """
    page = await use_case.execute(uow)

    return templates.TemplateResponse(
        "amp/pricelist.html",
        {
            "request": request,
            "seo": page.seo,
            "date": page.date,
            "fotos": page.fotos,
            "categories": page.categories,
            "positions": page.positions,
        },
    )


@router.get("/contacts/", response_class=HTMLResponse)
async def amp_contacts(
    request: Request,
    templates: FromDishka[Jinja2Templates],
    use_case: FromDishka[GetContactsPage],
    uow: FromDishka[AsyncUnitOfWork],
) -> HTMLResponse:
    """AMP-версия страницы контактов.

    Использует тот же use case ``GetContactsPage``, что и основная страница.
    Форма обратной связи реализована через ``amp-form``.
    Карта — через ``amp-iframe`` с виджетом Яндекс.Карт (бесплатный,
    без API-ключа). API-ключ Яндекс.Карт здесь не нужен — JS API в AMP
    запрещён, а Static Maps API требует отдельный платный ключ.
    """
    page = await use_case.execute(uow)

    return templates.TemplateResponse(
        "amp/contacts.html",
        {
            "request": request,
            "seo": page.seo,
            "contacts": page.contacts,
        },
    )


def _build_amp_cors_headers(request: Request) -> dict[str, str]:
    """Формирует CORS-заголовки, необходимые для amp-form.

    AMP требует специальные заголовки для XHR-запросов из amp-form:
      - AMP-Access-Control-Allow-Source-Origin: <origin страницы>
      - Access-Control-Expose-Headers: AMP-Access-Control-Allow-Source-Origin

    Origin берётся из __amp_source_origin (query param, добавляемый AMP runtime)
    или из заголовка Origin запроса.

    Подробнее: https://amp.dev/documentation/guides-and-tutorials/learn/amp-caches-and-cors/
    """
    source_origin = (
        request.query_params.get("__amp_source_origin")
        or request.headers.get("origin")
        or settings.seo.SITE_URL
    )
    return {
        "Access-Control-Allow-Origin": source_origin,
        "AMP-Access-Control-Allow-Source-Origin": source_origin,
        "Access-Control-Expose-Headers": "AMP-Access-Control-Allow-Source-Origin",
        "Access-Control-Allow-Credentials": "true",
    }


@router.post("/contacts/submit/", response_model=None)
async def amp_contacts_submit(
    request: Request,
    submit_uc: FromDishka[SubmitContactForm],
    uow: FromDishka[AsyncUnitOfWork],
):
    """XHR-обработчик формы контактов для amp-form.

    amp-form отправляет данные через XHR (action-xhr), а не стандартный POST.
    Сервер обязан вернуть JSON-ответ (не HTML, не редирект).

    При успехе — HTTP 200 + JSON с полем success.
    При ошибке валидации — HTTP 400 + JSON с полем errors.
    AMP runtime читает HTTP-статус и показывает соответствующий
    блок submit-success или submit-error в шаблоне.

    Капча здесь не проверяется: AMP не поддерживает SmartCaptcha.
    Защита от спама обеспечивается серверной валидацией.
    """
    form_data_raw = await request.form()

    form_data = ContactFormData(
        name=form_data_raw.get("name"),
        phone=form_data_raw.get("phone"),
        mail=form_data_raw.get("mail"),
        message=form_data_raw.get("message"),
    )

    result = await submit_uc.execute(uow, form_data)
    cors_headers = _build_amp_cors_headers(request)

    if result.success:
        logger.info("AMP contact form submitted successfully")
        return JSONResponse(
            content={"success": True},
            status_code=200,
            headers=cors_headers,
        )

    # Ошибки валидации — AMP покажет блок submit-error
    logger.debug("AMP contact form validation errors: %s", result.errors)
    return JSONResponse(
        content={"success": False, "errors": result.errors},
        status_code=400,
        headers=cors_headers,
    )
