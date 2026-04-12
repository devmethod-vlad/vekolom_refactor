"""Celery tasks for the home and pricelist modules.

Зеркалирует Celery-задачи из core/models.py и pricelist/models.py Django-проекта.

Django (оригинал, home):
    @shared_task(acks_late=True)
    def slide_to_webp(pk):
        time.sleep(1.5)
        slide = MainCarousel.objects.get(pk=pk)
        photo_name = os.path.basename(slide.photo.url)
        webp_name = photo_name.split('.')[0] + '.webp'
        photo_path = media_path + photo_name
        im = Image.open(photo_path)
        im.save(media_path + webp_name, 'webp', quality='20')
        slide.photo_webp = '/media/media/' + webp_name
        slide.save()

Django (оригинал, pricelist):
    @shared_task()
    def pos_webp(pk):       — конвертация photo2 → photo2_webp + avatar_webp
    @shared_task()
    def foto_webp(pk):      — конвертация foto → foto_webp

Важное отличие: задачи принимают относительный путь photo как аргумент,
а не читают его из БД — это позволяет избежать race condition между
сохранением записи и запуском задачи.
"""

import os
import time

from sqlalchemy import create_engine, update

from app.infrastructure.celery.worker import celery_app
from app.infrastructure.media.image_processor import make_webp_sync
from app.modules.home.infrastructure.sa_models import MainCarousel
from app.modules.pricelist.application.excel_export import generate_pricelist_xlsx
from app.modules.pricelist.infrastructure.sa_models import Foto, Position
from app.settings.config import settings


# ---------------------------------------------------------------------------
# Home module: slide_to_webp
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    acks_late=True,
    max_retries=3,
    default_retry_delay=10,
)
def slide_to_webp(self, slide_id: int, photo_relative_path: str) -> None:
    """Конвертирует фото слайда в WebP и обновляет запись в БД.

    Аналог Django slide_to_webp(pk):
      1. Ждём 1.5 с, пока файл гарантированно записан на диск.
      2. Конвертируем JPEG → WebP через Pillow.
      3. Обновляем MainCarousel.photo_webp в PostgreSQL.

    Аргументы:
        slide_id            — id записи в таблице maincarousel.
        photo_relative_path — значение поля photo (напр. 'media/abc.jpg').

    Записывает в photo_webp URL вида '/media/media/abc.webp'
    (совместимо с legacy Django-схемой).
    """
    # 1. Ждём, пока файл точно попал на диск (как в Django-задаче: time.sleep(1.5))
    time.sleep(1.5)

    # 2. Проверяем наличие файла
    from app.infrastructure.media.storage import abs_path
    src_abs = abs_path(photo_relative_path)
    if not os.path.isfile(src_abs):
        # Если файл не появился — повторяем задачу (до max_retries раз)
        raise self.retry(
            exc=FileNotFoundError(f"Source photo not found: {src_abs}"),
            countdown=5,
        )

    # 3. Конвертируем в WebP
    try:
        webp_url = make_webp_sync(photo_relative_path)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)

    # 4. Обновляем photo_webp в БД через синхронный SQLAlchemy (в Celery-воркере нет event loop)
    engine = create_engine(settings.database.sync_dsn, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            conn.execute(
                update(MainCarousel)
                .where(MainCarousel.id == slide_id)
                .values(photo_webp=webp_url)
            )
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Pricelist module: position_photo_to_webp
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    acks_late=True,
    max_retries=3,
    default_retry_delay=10,
)
def position_photo_to_webp(self, position_id: int, photo_relative_path: str) -> None:
    """Конвертирует фото позиции (photo2) в WebP и обновляет запись в БД.

    Аналог Django pos_webp(pk) из pricelist/models.py:
      1. Ждём 1.5 с, пока файл гарантированно записан на диск.
      2. Конвертируем JPEG → WebP через Pillow.
      3. Обновляем Position.photo2_webp и Position.avatar_webp в PostgreSQL.

    В оригинале Django генерировал avatar (370×260) через ImageSpecField,
    а потом конвертировал и его в WebP. Здесь avatar_webp пока получает
    тот же WebP, что и photo2_webp — при необходимости можно добавить ресайз.

    Аргументы:
        position_id         — id записи в таблице position.
        photo_relative_path — значение поля photo2 (напр. 'media/abc.jpg').
    """
    time.sleep(1.5)

    from app.infrastructure.media.storage import abs_path
    src_abs = abs_path(photo_relative_path)
    if not os.path.isfile(src_abs):
        raise self.retry(
            exc=FileNotFoundError(f"Source photo not found: {src_abs}"),
            countdown=5,
        )

    try:
        webp_url = make_webp_sync(photo_relative_path)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)

    # В Django avatar_webp генерировался из ImageSpecField (370×260).
    # Пока записываем тот же WebP — можно добавить отдельный ресайз позже.
    engine = create_engine(settings.database.sync_dsn, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            conn.execute(
                update(Position)
                .where(Position.id == position_id)
                .values(
                    photo2_webp=webp_url,
                    avatar_webp=webp_url,
                )
            )
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Pricelist module: foto_to_webp
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    acks_late=True,
    max_retries=3,
    default_retry_delay=10,
)
def foto_to_webp(self, foto_id: int, foto_relative_path: str) -> None:
    """Конвертирует фото прайс-листа в WebP и обновляет запись в БД.

    Аналог Django foto_webp(pk) из pricelist/models.py:
      1. Ждём 1.5 с, пока файл гарантированно записан на диск.
      2. Конвертируем JPEG → WebP через Pillow.
      3. Обновляем Foto.foto_webp в PostgreSQL.

    Аргументы:
        foto_id             — id записи в таблице foto.
        foto_relative_path  — значение поля foto (напр. 'media/abc.jpg').
    """
    time.sleep(1.5)

    from app.infrastructure.media.storage import abs_path
    src_abs = abs_path(foto_relative_path)
    if not os.path.isfile(src_abs):
        raise self.retry(
            exc=FileNotFoundError(f"Source photo not found: {src_abs}"),
            countdown=5,
        )

    try:
        webp_url = make_webp_sync(foto_relative_path)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)

    engine = create_engine(settings.database.sync_dsn, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            conn.execute(
                update(Foto)
                .where(Foto.id == foto_id)
                .values(foto_webp=webp_url)
            )
    finally:
        engine.dispose()

@celery_app.task(
    bind=True,
    acks_late=True,
    max_retries=3,
    default_retry_delay=10,
)
def regenerate_pricelist_excel(self) -> None:
    """Regenerates static/excel/pricelist.xlsx from current DB state."""
    engine = create_engine(settings.database.sync_dsn, pool_pre_ping=True)
    try:
        from sqlalchemy.orm import Session

        with Session(engine) as session:
            generate_pricelist_xlsx(session)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)
    finally:
        engine.dispose()
