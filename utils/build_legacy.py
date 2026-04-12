#!/usr/bin/env python3
"""CLI: сборка production-бандлов legacy JS и custom CSS.

Запуск:
    python utils/build_legacy.py             # собрать всё (JS + CSS)
    python utils/build_legacy.py --js        # только legacy JS
    python utils/build_legacy.py --css       # только custom CSS

Что делает
----------
Вызывает ``build_legacy_js()`` и/или ``build_custom_css()`` из модуля
``app.infrastructure.web.bundler``.

Этот скрипт — CLI-обёртка для ручного запуска. В prod-режиме сборка также
автоматически выполняется при старте приложения через ``lifespan`` в ``main.py``.

Почему это отдельный pipeline
-----------------------------
Legacy-скрипты — это не ESM, а старый добрый classic JS. Пытаться засунуть их
в Vite-пайплайн — отличный способ словить хаос с порядком выполнения и ошибки
вроде ``jQuery is not defined``. Поэтому сборка отделена от modern JS/CSS.
"""

from __future__ import annotations

import argparse
import logging
import sys

from app.infrastructure.web.asset_manifest import AssetManifestError
from app.infrastructure.web.bundler import build_custom_css, build_legacy_js
from app.settings.config import settings


def main() -> None:
    """Точка входа CLI-скрипта."""
    parser = argparse.ArgumentParser(
        description="Сборка production-бандлов legacy JS и custom CSS.",
    )
    parser.add_argument(
        "--js", action="store_true",
        help="Собрать только legacy JS бандлы.",
    )
    parser.add_argument(
        "--css", action="store_true",
        help="Собрать только custom CSS бандлы.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    # Если ни один флаг не указан — собираем всё.
    build_js = args.js or not (args.js or args.css)
    build_css = args.css or not (args.js or args.css)

    try:
        if build_js:
            build_legacy_js(settings)
        if build_css:
            build_custom_css(settings)
    except AssetManifestError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    print("\n[build] Готово.")


if __name__ == "__main__":
    main()
