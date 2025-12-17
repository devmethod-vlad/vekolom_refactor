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
    page = await use_case.execute(uow)
    return templates.TemplateResponse(
        "home/index.html",
        {"request": request, "page": page},
    )
