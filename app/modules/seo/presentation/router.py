"""
HTTP routing for SEO endpoints: robots.txt and sitemap.xml.

robots.txt — инструкция для поисковых роботов, какие разделы сайта
             можно индексировать, а какие — нет. Также содержит ссылку
             на sitemap.xml для ускорения обнаружения страниц.

sitemap.xml — XML-карта сайта для поисковых систем. Перечисляет все
              публичные URL с приоритетами и частотой обновления.
              Google и Яндекс используют sitemap для более полной
              индексации сайта.

Оба endpoint отдают текстовый/XML-контент напрямую (без шаблонов),
т.к. формат фиксирован и не требует Jinja2.
"""

from datetime import date

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response

from app.settings.config import settings


router = APIRouter()


@router.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
async def robots_txt() -> str:
    """Отдаёт robots.txt для поисковых роботов.

    - Разрешает индексацию всех публичных страниц.
    - Запрещает индексацию /admin/ (админка не должна попадать в поиск).
    - Запрещает индексацию /api/ (внутренние API-эндпоинты).
    - Указывает путь к sitemap.xml.

    Используется Googlebot, YandexBot и другими краулерами.
    """
    site_url = settings.seo.SITE_URL
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /api/\n"
        "Disallow: /offline/\n"
        "\n"
        f"Sitemap: {site_url}/sitemap.xml\n"
        f"Host: {site_url}\n"
    )


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml() -> Response:
    """Генерирует sitemap.xml для поисковых систем.

    Содержит все публичные страницы сайта с указанием:
    - loc       — абсолютный URL страницы
    - lastmod   — дата последнего обновления (текущая дата для динамических страниц)
    - changefreq — ожидаемая частота обновления
    - priority  — приоритет страницы (0.0–1.0) относительно других страниц сайта

    При добавлении новых публичных страниц — добавляйте их сюда.
    """
    site_url = settings.seo.SITE_URL
    today = date.today().isoformat()

    # Статические страницы сайта с приоритетами.
    # priority: 1.0 — главная, 0.8 — ключевые страницы, 0.6 — второстепенные.
    # Статические страницы сайта с приоритетами.
    # priority: 1.0 — главная, 0.8 — ключевые страницы, 0.6 — второстепенные.
    # AMP-версии включены с приоритетом на 0.1 ниже основных — поисковики
    # сами выбирают, какую версию показывать на основе парных ссылок
    # <link rel="amphtml"> / <link rel="canonical">.
    pages = [
        {"loc": f"{site_url}/", "changefreq": "weekly", "priority": "1.0"},
        {"loc": f"{site_url}/pricelist/", "changefreq": "weekly", "priority": "0.8"},
        {"loc": f"{site_url}/contacts/", "changefreq": "monthly", "priority": "0.6"},
        {"loc": f"{site_url}/amp/", "changefreq": "weekly", "priority": "0.9"},
        {"loc": f"{site_url}/amp/pricelist/", "changefreq": "weekly", "priority": "0.7"},
        {"loc": f"{site_url}/amp/contacts/", "changefreq": "monthly", "priority": "0.5"},
    ]

    url_entries = []
    for page in pages:
        url_entries.append(
            f"  <url>\n"
            f"    <loc>{page['loc']}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>{page['changefreq']}</changefreq>\n"
            f"    <priority>{page['priority']}</priority>\n"
            f"  </url>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(url_entries)
        + "\n</urlset>\n"
    )

    return Response(content=xml, media_type="application/xml")
