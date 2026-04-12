"""Custom CSS asset manager — подключение пользовательских стилей.

Схема работы
------------
1. Исходные CSS-файлы лежат внутри ``STATIC_ROOT``.
   Пути к ним задаются в манифесте относительно ``STATIC_ROOT``.
2. JSON-манифест с именованными модулями задаётся через
   ``CUSTOM_CSS_MANIFEST_PATH`` и может лежать где угодно.
3. Манифест поддерживает наследование (``extend``) и production-бандлы (``dist``).
4. В dev каждый файл подключается отдельно через ``<link rel="stylesheet">``.
5. В prod подключается один минифицированный бандл из ``dist``.

Формат манифеста
----------------
::

    {
      "base": {
        "styles": ["css/custom/reset.css", "css/custom/layout.css"],
        "dist": "dist/css/base.min.css"
      },
      "home": {
        "extend": ["base"],
        "styles": ["css/custom/home-carousel.css"],
        "dist": "dist/css/home.min.css"
      }
    }
"""

from __future__ import annotations

from pathlib import Path

from markupsafe import Markup

from app.infrastructure.web.asset_manifest import (
    AssetManifestError,
    AssetModule,
    load_asset_manifest,
    normalize_relative_path,
    resolve_files,
)
from app.settings.config import Settings

# Ключ в манифесте, содержащий список файлов для CSS-модулей.
_FILES_KEY = "styles"


class CustomCSSManager:
    """Генерирует HTML-теги для подключения пользовательских CSS.

    Dev-режим:
        Возвращает отдельный ``<link rel="stylesheet">`` для каждого файла
        модуля с учётом наследования (``extend``).
        Файлы отдаются через FastAPI StaticFiles из ``STATIC_ROOT``.

    Prod-режим:
        Возвращает один ``<link rel="stylesheet">`` на production-бандл,
        путь к которому берётся из ключа ``dist`` модуля.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._modules: dict[str, AssetModule] | None = None

    @property
    def _manifest_path(self) -> Path:
        """Абсолютный путь до JSON-манифеста CSS-модулей."""
        return Path(self._settings.custom_css.MANIFEST_PATH).resolve()

    @property
    def _static_root(self) -> Path:
        """Абсолютный физический каталог статики."""
        return Path(self._settings.static.STATIC_ROOT).resolve()

    @property
    def _static_url(self) -> str:
        """URL-префикс статики (без trailing slash)."""
        return self._settings.static.STATIC_URL.rstrip("/")

    @property
    def modules(self) -> dict[str, AssetModule]:
        """Возвращает кешированный словарь модулей из манифеста."""
        if self._modules is None:
            self._modules = load_asset_manifest(
                self._manifest_path,
                files_key=_FILES_KEY,
            )
        return self._modules

    def render(self, module_name: str) -> Markup:
        """Рендерит теги для указанного CSS-модуля.

        Используется в шаблонах как ``{{ custom_css('module') }}``.
        """
        if self._settings.app.DEBUG:
            return self._render_dev(module_name)
        return self._render_prod(module_name)

    def _render_dev(self, module_name: str) -> Markup:
        """Возвращает по одному ``<link>`` на каждый CSS-файл модуля.

        Пути в манифесте задаются относительно STATIC_ROOT, поэтому файл
        ищется как ``STATIC_ROOT / rel_path``, а URL формируется как
        ``STATIC_URL / rel_path``.
        """
        files = resolve_files(self.modules, module_name, files_key=_FILES_KEY)
        lines: list[str] = []

        for rel_posix in files:
            rel_path = normalize_relative_path(
                rel_posix,
                context=f"css module {module_name!r}",
            )
            source_file = self._static_root.joinpath(*rel_path.parts)

            if not source_file.exists():
                raise AssetManifestError(
                    f"Не найден CSS-файл: {source_file} "
                    f"(модуль {module_name!r}, manifest {self._manifest_path})"
                )

            href = f"{self._static_url}/{rel_path.as_posix()}"
            lines.append(f'<link rel="stylesheet" href="{href}">')

        return Markup("\n    ".join(lines))

    def _render_prod(self, module_name: str) -> Markup:
        """Возвращает один ``<link>`` на production-бандл из ``dist``."""
        module = self.modules.get(module_name)
        if module is None:
            available = ", ".join(sorted(self.modules.keys()))
            raise AssetManifestError(
                f"CSS-модуль {module_name!r} не найден в {self._manifest_path}. "
                f"Доступные модули: {available}"
            )

        dist_path = module.get("dist")
        if not dist_path:
            raise AssetManifestError(
                f"CSS-модуль {module_name!r} не содержит ключа 'dist' — "
                f"невозможно определить путь к production-бандлу."
            )

        bundle_url = f"{self._static_url}/{dist_path}"
        return Markup(f'<link rel="stylesheet" href="{bundle_url}">')
