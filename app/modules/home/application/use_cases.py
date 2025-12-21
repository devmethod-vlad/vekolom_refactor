"""
Application layer use case for building the home page.

Use cases orchestrate calls to one or more repositories and apply
business rules.  ``GetHomePage`` fetches all pieces of the home page
from the ``HomeReadRepository`` and bundles them into a single
``HomePageDTO``.  Because it depends only on the repository
interface, it can be unit tested with a fake repository or a mock.
"""

from app.infrastructure.uow import AsyncUnitOfWork
from app.modules.home.domain.dto import HomePageDTO


class GetHomePage:
    """Use case for assembling the home page data."""

    async def execute(self, uow: AsyncUnitOfWork) -> HomePageDTO:
        """
        Fetch all required data for the home page in a single unit of
        work.  The unit of work manages the transaction boundary and
        ensures that all queries run against the same session.
        """

        async with uow:
            seo = await uow.home.get_seo()
            slides = await uow.home.list_slides()
            main_blocks = await uow.home.list_main_blocks()
            actions = await uow.home.list_actions()
            slogans = await uow.home.list_slogans()
            accept_items = await uow.home.list_priem_items()
            positions = await uow.home.list_positions()

        return HomePageDTO(
            seo=seo,
            slides=slides,
            main_blocks=main_blocks,
            actions=actions,
            slogans=slogans,
            accept_items=accept_items,
            positions=positions,
        )