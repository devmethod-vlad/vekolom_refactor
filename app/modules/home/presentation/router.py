"""
HTTP routing for the home module.

This router uses Dishka's integration with FastAPI to resolve
dependencies from the DI container.  It delegates to the ``GetHomePage``
use case to build the page data and then renders the Jinja2 template
``home/index.html``.  All presentation logic (such as HTML structure
and styling) should live in the template rather than in this function.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.infrastructure.uow import AsyncUnitOfWork
from app.modules.home.application.use_cases import GetHomePage


router = APIRouter(route_class=DishkaRoute)


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    templates: FromDishka[Jinja2Templates],
    use_case: FromDishka[GetHomePage],
    uow: FromDishka[AsyncUnitOfWork],
) -> HTMLResponse:
    """
    Home page endpoint.

    Dependencies are resolved via Dishka.  ``use_case`` is the
    application service that constructs the page data.  ``uow``
    provides the transactional context and repository access.  The
    assembled ``HomePageDTO`` is passed into the Jinja2 template under
    the key ``page``.  The template is responsible for presenting the
    SEO meta tags, carousel, main blocks, actions, slogans, accept
    items, and price list positions.
    """

    page = await use_case.execute(uow)
    return templates.TemplateResponse(
        "home/index.html",
        {
            "request": request,
            "page": page,
        },
    )