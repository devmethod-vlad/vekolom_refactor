"""
HTTP routing for the contacts module.

Контекст шаблона соответствует переменным оригинального Django-вью
``contacts(request)`` из contacts/views.py:

    debug_flag              ← bool  (из settings.app.DEBUG)
    seo                     ← Sequence[ContactsSeo]  (ContactsSeo.objects.all())
    contacts                ← Sequence[ContactInfo]  (Contacts.objects.all())
    form                    ← dict  (данные формы для повторного заполнения при ошибке)
    errors                  ← list[str]  (ошибки валидации)
    yandex_maps_api_key     ← str  (API-ключ Яндекс.Карт из модуля apikeys)
    smartcaptcha_client_key ← str  (публичный ключ SmartCaptcha из модуля apikeys)

В Django вью выбирал шаблон contacts/dev/contacts.html или
contacts/prod/contacts.html в зависимости от DEBUG.
Здесь используется один шаблон contacts/contacts.html
(dev/prod логика CSS остаётся на уровне base.html).

Обработка формы:
  - GET  /contacts/ — отображение страницы контактов.
  - POST /contacts/ — валидация капчи, валидация и сохранение сообщения из формы.
    При успехе — редирект на '/' (как в Django view).
    При ошибках — повторное отображение формы с ошибками.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.infrastructure.uow import AsyncUnitOfWork
from app.infrastructure.web.captcha import validate_smartcaptcha
from app.modules.apikeys.application.use_cases import (
    GetSmartCaptchaKeys,
    GetYandexMapsApiKey,
)
from app.modules.contacts.application.use_cases import (
    ContactFormData,
    GetContactsPage,
    SubmitContactForm,
)
from app.settings.config import settings


logger = logging.getLogger("app.contacts.router")

router = APIRouter(route_class=DishkaRoute)


def _get_client_ip(request: Request) -> str:
    """Извлекает IP клиента из запроса.

    X-Real-IP устанавливается nginx (snippets/proxy_params.conf).
    Если nginx нет (dev-режим) — используем request.client.host.
    """
    return (
        request.headers.get("x-real-ip")
        or (request.client.host if request.client else "unknown")
    )


@router.get("/contacts/", response_class=HTMLResponse)
async def contacts_get(
    request: Request,
    templates: FromDishka[Jinja2Templates],
    use_case: FromDishka[GetContactsPage],
    maps_key_uc: FromDishka[GetYandexMapsApiKey],
    captcha_uc: FromDishka[GetSmartCaptchaKeys],
    uow: FromDishka[AsyncUnitOfWork],
) -> HTMLResponse:
    """Страница контактов (GET).

    Аналог Django view ``def contacts(request)`` из contacts/views.py
    для GET-запросов.
    """
    page = await use_case.execute(uow)

    # Получаем API-ключи из модуля apikeys
    yandex_maps_api_key = await maps_key_uc.execute(uow)
    smartcaptcha_client_key, _ = await captcha_uc.execute(uow)

    return templates.TemplateResponse(
        "contacts/contacts.html",
        {
            "request": request,
            # соответствие Django-контексту
            "debug_flag": page.debug_flag,
            "seo": page.seo,
            "contacts": page.contacts,
            "form": page.form,
            "errors": page.errors,
            # API-ключи (из БД через модуль apikeys)
            "yandex_maps_api_key": yandex_maps_api_key,
            "smartcaptcha_client_key": smartcaptcha_client_key,
        },
    )


@router.post("/contacts/", response_model=None)
async def contacts_post(
    request: Request,
    templates: FromDishka[Jinja2Templates],
    get_page_uc: FromDishka[GetContactsPage],
    submit_uc: FromDishka[SubmitContactForm],
    maps_key_uc: FromDishka[GetYandexMapsApiKey],
    captcha_uc: FromDishka[GetSmartCaptchaKeys],
    uow: FromDishka[AsyncUnitOfWork],
):
    """Обработка формы контактов (POST).

    Аналог Django view ``def contacts(request)`` из contacts/views.py
    для POST-запросов.

    Последовательность проверок:
      1. Валидация SmartCaptcha (серверная проверка токена через Yandex API).
      2. Валидация полей формы (телефон/email, сообщение).
      3. Сохранение сообщения в БД.

    При успешной отправке — редирект на '/' (как в Django:
    ``return HttpResponseRedirect('/')``).
    При ошибках валидации — повторный рендеринг формы с ошибками.
    """
    form_data_raw = await request.form()

    form_data = ContactFormData(
        name=form_data_raw.get("name"),
        phone=form_data_raw.get("phone"),
        mail=form_data_raw.get("mail"),
        message=form_data_raw.get("message"),
    )

    # --- SmartCaptcha: серверная валидация ---
    # Получаем серверный ключ из БД
    smartcaptcha_client_key, smartcaptcha_server_key = await captcha_uc.execute(uow)

    # Извлекаем smart-token из формы (добавляется JS-виджетом SmartCaptcha)
    smart_token = form_data_raw.get("smart-token")
    client_ip = _get_client_ip(request)

    # В DEBUG-режиме пропускаем проверку капчи, если серверный ключ не настроен.
    # Это позволяет тестировать форму локально без капчи.
    skip_captcha = settings.app.DEBUG and not smartcaptcha_server_key

    if not skip_captcha:
        captcha_result = await validate_smartcaptcha(
            token=smart_token,
            server_key=smartcaptcha_server_key,
            client_ip=client_ip,
        )

        if not captcha_result.passed:
            # Капча не пройдена — возвращаем форму с ошибкой
            page = await get_page_uc.execute(uow)
            yandex_maps_api_key = await maps_key_uc.execute(uow)

            return templates.TemplateResponse(
                "contacts/contacts.html",
                {
                    "request": request,
                    "debug_flag": page.debug_flag,
                    "seo": page.seo,
                    "contacts": page.contacts,
                    "form": {
                        "name": form_data.name or "",
                        "phone": form_data.phone or "",
                        "mail": form_data.mail or "",
                        "message": form_data.message or "",
                    },
                    "errors": [captcha_result.error],
                    "yandex_maps_api_key": yandex_maps_api_key,
                    "smartcaptcha_client_key": smartcaptcha_client_key,
                },
            )
    else:
        logger.debug(
            "SmartCaptcha validation skipped (DEBUG mode, server_key not configured)"
        )

    # --- Валидация полей формы и сохранение ---
    result = await submit_uc.execute(uow, form_data)

    if result.success:
        # В Django: return HttpResponseRedirect('/')
        return RedirectResponse(url="/", status_code=303)

    # При ошибках — рендерим страницу с ошибками и данными формы.
    # Для этого загружаем данные страницы (seo, contacts) через GetContactsPage.
    page = await get_page_uc.execute(uow)
    yandex_maps_api_key = await maps_key_uc.execute(uow)

    return templates.TemplateResponse(
        "contacts/contacts.html",
        {
            "request": request,
            "debug_flag": page.debug_flag,
            "seo": page.seo,
            "contacts": page.contacts,
            "form": result.form,
            "errors": result.errors,
            "yandex_maps_api_key": yandex_maps_api_key,
            "smartcaptcha_client_key": smartcaptcha_client_key,
        },
    )
