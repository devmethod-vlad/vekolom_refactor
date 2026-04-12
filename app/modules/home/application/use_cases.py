"""
Application layer use case for building the home page.

``GetHomePage`` replicates the exact data-fetching logic of the legacy
Django view, including splitting the ``Actions`` queryset into three
individual variables (``action1``, ``action2``, ``action3``) just as the
original view did with ``Actions.objects.all()[0..2]``.
"""

from app.infrastructure.uow import AsyncUnitOfWork
from app.modules.home.domain.dto import HomePageDTO
from app.modules.home.domain.entities import ActionItem
from typing import Optional


def _get_action(actions: list, index: int) -> Optional[ActionItem]:
    """Safely return the action at *index*, or ``None`` if it does not exist.

    The legacy Django view raised ``IndexError`` when fewer than three
    ``Actions`` rows existed.  This helper guards against that.
    """
    try:
        return actions[index]
    except IndexError:
        return None


class GetHomePage:
    """Use case for assembling the home page data."""

    async def execute(self, uow: AsyncUnitOfWork) -> HomePageDTO:
        """Fetch all data for the home page within a single unit of work.

        The returned ``HomePageDTO`` uses the same field names as the
        Django template context so that the Jinja2 template can be ported
        with minimal changes.
        """

        async with uow:
            seo = await uow.home.get_seo()
            slides = await uow.home.list_slides()
            main = await uow.home.list_main()
            actions = list(await uow.home.list_actions())
            slogan1 = await uow.home.list_slogan1()
            priem = await uow.home.list_priem()

            # Позиции с check_flag=True — делегируем в pricelist-репозиторий,
            # который теперь доступен через UoW после миграции модуля pricelist.
            checked = await uow.pricelist.list_checked_positions()
            positions = [
                {
                    "name": p.name,
                    "price": p.price,
                    "photo2": p.photo2,
                    "avatar": p.photo2,  # В Django avatar генерировался ImageSpecField(370×260)
                }
                for p in checked
            ]

        return HomePageDTO(
            seo=seo,
            slides=slides,
            main=main,
            action1=_get_action(actions, 0),
            action2=_get_action(actions, 1),
            action3=_get_action(actions, 2),
            slogan1=slogan1,
            priem=priem,
            positions=positions,
        )