from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from markupsafe import Markup

from app.settings.config import Settings


@dataclass(slots=True)
class _ManifestCache:
    mtime_ns: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class ViteAssetManager:
    """Генерирует HTML-теги для подключения Vite-ассетов.

    Важно:
    - styles/preloads/scripts разделены, чтобы шаблон мог сам решать,
      что рендерить в <head>, а что — внизу <body>.
    - @vite/client вынесен в отдельный helper, чтобы не дублировать его
      при подключении base entrypoint + page entrypoint.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._manifest_cache = _ManifestCache()

    @property
    def enabled(self) -> bool:
        return self._settings.vite.ENABLED

    @property
    def is_dev(self) -> bool:
        return self._settings.app.DEBUG

    def render_dev_client(self) -> Markup:
        """Рендерит только @vite/client.

        Нужен ТОЛЬКО в dev-режиме и должен вставляться один раз на страницу.
        """
        if not self.enabled or not self.is_dev:
            return Markup("")

        origin = self._settings.vite.DEV_SERVER_ORIGIN.rstrip("/")
        return Markup(f'<script type="module" src="{origin}/@vite/client"></script>')

    def render_styles(self, entrypoint: str) -> Markup:
        """Рендерит только CSS для entrypoint.

        Dev-режим:
            Обычно возвращает пустую строку. В Vite dev CSS, импортированный из JS,
            подхватывается dev server'ом и инжектится через JS/HMR-клиент.

        Prod-режим:
            Возвращает <link rel="stylesheet"> для entrypoint и его импортов.
        """
        if not self.enabled:
            return Markup("")

        if self.is_dev:
            return Markup("")

        manifest = self._load_manifest()
        css_files = self._collect_css(manifest, entrypoint)
        asset_prefix = self._settings.vite.ASSET_URL_PREFIX.rstrip("/")

        lines = [
            f'<link rel="stylesheet" href="{asset_prefix}/{css_path}">'
            for css_path in css_files
        ]
        return Markup("\n".join(lines))

    def render_preloads(self, entrypoint: str) -> Markup:
        """Рендерит <link rel="modulepreload"> для shared chunks.

        Dev-режим:
            Обычно пусто — Vite dev server сам разруливает загрузку модулей.

        Prod-режим:
            Возвращает modulepreload для импортируемых JS-чанков.
        """
        if not self.enabled:
            return Markup("")

        if self.is_dev:
            return Markup("")

        manifest = self._load_manifest()
        preload_files = self._collect_import_files(manifest, entrypoint)
        asset_prefix = self._settings.vite.ASSET_URL_PREFIX.rstrip("/")

        lines = [
            f'<link rel="modulepreload" href="{asset_prefix}/{import_path}">'
            for import_path in preload_files
        ]
        return Markup("\n".join(lines))

    def render_scripts(self, entrypoint: str) -> Markup:
        """Рендерит только JS entry script.

        Dev:
            <script type="module" src="http://vite-dev-server/<entrypoint>"></script>

        Prod:
            <script type="module" src="/static/dist/assets/<hashed-file>.js"></script>
        """
        if not self.enabled:
            return Markup("")

        if self.is_dev:
            origin = self._settings.vite.DEV_SERVER_ORIGIN.rstrip("/")
            return Markup(
                f'<script type="module" src="{origin}/{entrypoint}"></script>'
            )

        manifest = self._load_manifest()
        node = self._get_manifest_node(manifest, entrypoint)

        entry_file = node.get("file")
        if not isinstance(entry_file, str) or not entry_file:
            raise RuntimeError(
                f"Vite manifest для entrypoint {entrypoint!r} не содержит поля 'file'."
            )

        asset_prefix = self._settings.vite.ASSET_URL_PREFIX.rstrip("/")
        return Markup(
            f'<script type="module" src="{asset_prefix}/{entry_file}"></script>'
        )

    def render_tags(self, entrypoint: str) -> Markup:
        """Совместимость со старой схемой.

        Можно оставить как legacy-wrapper, чтобы миграция шла мягко.
        Но в новых шаблонах лучше использовать styles/preloads/scripts отдельно.
        """
        parts: list[str] = []

        if self.is_dev:
            parts.append(str(self.render_dev_client()))

        parts.append(str(self.render_styles(entrypoint)))
        parts.append(str(self.render_preloads(entrypoint)))
        parts.append(str(self.render_scripts(entrypoint)))

        return Markup("\n".join(part for part in parts if part))

    def _load_manifest(self) -> dict[str, Any]:
        manifest_path = Path(self._settings.vite.manifest_path)
        if not manifest_path.exists():
            raise RuntimeError(
                f"Vite manifest не найден: {manifest_path}. "
                "Соберите frontend через `npm run build` или отключите VITE_ENABLED."
            )

        stat = manifest_path.stat()
        if self._manifest_cache.mtime_ns == stat.st_mtime_ns:
            return self._manifest_cache.payload

        with manifest_path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)

        if not isinstance(payload, dict):
            raise RuntimeError(f"Некорректный формат Vite manifest: {manifest_path}")

        self._manifest_cache = _ManifestCache(
            mtime_ns=stat.st_mtime_ns,
            payload=payload,
        )
        return payload

    def _get_manifest_node(
        self,
        manifest: dict[str, Any],
        entrypoint: str,
    ) -> dict[str, Any]:
        node = manifest.get(entrypoint)
        if not isinstance(node, dict):
            raise RuntimeError(
                "Vite manifest не содержит entrypoint "
                f"{entrypoint!r}. Выполните `npm run build` в frontend/ "
                "или отключите VITE_ENABLED."
            )
        return node

    def _collect_css(self, manifest: dict[str, Any], entrypoint: str) -> list[str]:
        """Собирает CSS entrypoint и его импортов без дублей."""
        collected: list[str] = []
        seen: set[str] = set()

        def walk(name: str) -> None:
            node = manifest.get(name)
            if not isinstance(node, dict):
                return

            for imported_name in node.get("imports", []):
                if isinstance(imported_name, str):
                    walk(imported_name)

            for css_path in node.get("css", []):
                if isinstance(css_path, str) and css_path not in seen:
                    seen.add(css_path)
                    collected.append(css_path)

        walk(entrypoint)
        return collected

    def _collect_import_files(
        self,
        manifest: dict[str, Any],
        entrypoint: str,
    ) -> list[str]:
        """Собирает JS-файлы импортируемых shared chunks без дублей."""
        collected: list[str] = []
        seen: set[str] = set()

        def walk(name: str) -> None:
            node = manifest.get(name)
            if not isinstance(node, dict):
                return

            for imported_name in node.get("imports", []):
                if not isinstance(imported_name, str):
                    continue

                imported_node = manifest.get(imported_name)
                if isinstance(imported_node, dict):
                    file_name = imported_node.get("file")
                    if isinstance(file_name, str) and file_name not in seen:
                        seen.add(file_name)
                        collected.append(file_name)

                walk(imported_name)

        walk(entrypoint)
        return collected