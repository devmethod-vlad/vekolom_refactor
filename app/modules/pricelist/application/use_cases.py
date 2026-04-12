"""
Application layer use case for building the pricelist page.

``GetPricelistPage`` replicates the exact data-fetching logic of the legacy
Django view ``pricelist(request)`` from pricelist/views.py:

    date       = PriceDate.objects.all()
    fotos      = Foto.objects.all()
    seo        = PricelistSeo.objects.all()
    categories = Category.objects.order_by('-name')
    positions  = Position.objects.order_by('order')
"""

from app.infrastructure.uow import AsyncUnitOfWork
from app.modules.pricelist.domain.dto import PricelistPageDTO
from app.settings.config import settings


class GetPricelistPage:
    """Use case for assembling the pricelist page data."""

    async def execute(self, uow: AsyncUnitOfWork) -> PricelistPageDTO:
        """Fetch all data for the pricelist page within a single unit of work.

        The returned ``PricelistPageDTO`` uses the same field names as the
        Django template context so that the Jinja2 template can be ported
        with minimal changes.
        """
        async with uow:
            seo = await uow.pricelist.list_seo()
            date = await uow.pricelist.list_dates()
            fotos = await uow.pricelist.list_fotos()
            categories = await uow.pricelist.list_categories()
            positions = await uow.pricelist.list_positions()

        return PricelistPageDTO(
            seo=seo,
            date=date,
            fotos=fotos,
            categories=categories,
            positions=positions,
            debug_flag=settings.app.DEBUG,
        )
