"""Сборщик production-бандлов для legacy JS и custom CSS.

Модуль выполняет две задачи:
1. Конкатенация файлов модуля в порядке, заданном манифестом (с учётом ``extend``).
2. Минификация результата (JS → ``rjsmin``, CSS → ``rcssmin``).

Интеграция
----------
- **Старт приложения**: вызывается из ``lifespan`` в ``main.py``.
  В prod-режиме автоматически собирает бандлы, если включены флаги
  ``BUNDLE_LEGACY_JS`` и/или ``BUNDLE_CUSTOM_CSS``.
- **CLI**: можно запустить вручную через ``python -m utils.build_assets``.

Зачем отдельный модуль
----------------------
Логика сборки не должна дублироваться между CLI-скриптом и startup-хуком.
Оба используют одну и ту же функцию ``build_assets()``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.infrastructure.web.asset_manifest import (
    AssetManifestError,
    AssetModule,
    load_asset_manifest,
    normalize_relative_path,
    resolve_files,
)
from app.settings.config import Settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Минификаторы
# ─────────────────────────────────────────────────────────────────────

def _minify_js(source: str) -> str:
    """Минифицирует JavaScript через rjsmin."""
    try:
        import rjsmin  # type: ignore[import-untyped]
    except ImportError:
        logger.warning(
            "rjsmin не установлен — JS записывается без минификации. "
            "Установите: pip install rjsmin"
        )
        return source
    return rjsmin.jsmin(source)


def _minify_css(source: str) -> str:
    """Минифицирует CSS через rcssmin."""
    try:
        import rcssmin  # type: ignore[import-untyped]
    except ImportError:
        logger.warning(
            "rcssmin не установлен — CSS записывается без минификации. "
            "Установите: pip install rcssmin"
        )
        return source
    return rcssmin.cssmin(source)


# ─────────────────────────────────────────────────────────────────────
# Конкатенация
# ─────────────────────────────────────────────────────────────────────

def _concatenate_files(
    file_list: list[str],
    source_root: Path,
    *,
    module_name: str,
    separator: str = "\n",
) -> str:
    """Читает файлы в указанном порядке и конкатенирует их содержимое.

    Каждый файл предваряется комментарием с именем для удобства отладки.
    Между файлами вставляется разделитель (по умолчанию — перенос строки).

    Args:
        file_list: список относительных POSIX-путей.
        source_root: абсолютный каталог с исходниками.
        module_name: имя модуля (для логирования и комментариев).
        separator: разделитель между фрагментами.

    Returns:
        Конкатенированное содержимое.
    """
    parts: list[str] = []

    for rel_posix in file_list:
        rel_path = normalize_relative_path(
            rel_posix,
            context=f"module {module_name!r}",
        )
        src_path = source_root.joinpath(*rel_path.parts)

        if not src_path.exists():
            raise AssetManifestError(
                f"Файл не найден: {src_path} (модуль {module_name!r})"
            )

        content = src_path.read_text(encoding="utf-8")
        # Комментарий-заголовок для каждого файла.
        parts.append(f"/* {rel_path.as_posix()} */\n{content}")

        logger.debug(
            "  [+] %s (%s bytes)", rel_path.as_posix(), f"{len(content):,}"
        )

    return separator.join(parts)


# ─────────────────────────────────────────────────────────────────────
# Сборка одного бандла
# ─────────────────────────────────────────────────────────────────────

def _build_single_bundle(
    module_name: str,
    modules: dict[str, AssetModule],
    *,
    files_key: str,
    source_root: Path,
    static_root: Path,
    minifier: callable,
    asset_type: str,
) -> None:
    """Собирает и минифицирует один бандл.

    Args:
        module_name: имя модуля из манифеста.
        modules: загруженный манифест.
        files_key: ``scripts`` или ``styles``.
        source_root: каталог с исходными файлами.
        static_root: корень статики (STATIC_ROOT).
        minifier: функция минификации ``(str) -> str``.
        asset_type: ``JS`` или ``CSS`` — для логирования.
    """
    module = modules[module_name]
    dist_path = module.get("dist")
    if not dist_path:
        logger.info(
            "[%s] Модуль %r: ключ 'dist' не задан — пропускаем сборку.",
            asset_type, module_name,
        )
        return

    # Разрешаем файлы с учётом наследования.
    resolved = resolve_files(modules, module_name, files_key=files_key)
    if not resolved:
        logger.info(
            "[%s] Модуль %r: нет файлов для сборки.", asset_type, module_name
        )
        return

    logger.info(
        "[%s] Модуль %r: %d файлов", asset_type, module_name, len(resolved)
    )

    # JS-файлы разделяем через ``;\n`` для безопасности синтаксиса.
    separator = "\n;\n" if files_key == "scripts" else "\n"
    combined = _concatenate_files(
        resolved, source_root, module_name=module_name, separator=separator,
    )
    raw_size = len(combined.encode("utf-8"))

    minified = minifier(combined)
    min_size = len(minified.encode("utf-8"))

    # Путь к выходному файлу: STATIC_ROOT / dist.
    output_file = static_root / dist_path
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(minified, encoding="utf-8")

    ratio = (1 - min_size / raw_size) * 100 if raw_size else 0
    logger.info(
        "[%s] %r → %s  (до: %s bytes, после: %s bytes, сжатие: %.1f%%)",
        asset_type,
        module_name,
        output_file,
        f"{raw_size:,}",
        f"{min_size:,}",
        ratio,
    )


# ─────────────────────────────────────────────────────────────────────
# Публичный API
# ─────────────────────────────────────────────────────────────────────

def build_legacy_js(settings: Settings) -> None:
    """Собирает production-бандлы legacy JS на основе манифеста.

    Читает ``LEGACY_MANIFEST_PATH``, разрешает наследование,
    конкатенирует и минифицирует каждый модуль с ключом ``dist``.

    Пути к файлам в манифесте задаются относительно STATIC_ROOT.
    """
    manifest_path = Path(settings.legacy.MANIFEST_PATH).resolve()
    static_root = Path(settings.static.STATIC_ROOT).resolve()

    logger.info("[JS] Manifest    : %s", manifest_path)
    logger.info("[JS] Static root : %s", static_root)

    modules = load_asset_manifest(manifest_path, files_key="scripts")

    for module_name in modules:
        _build_single_bundle(
            module_name,
            modules,
            files_key="scripts",
            source_root=static_root,
            static_root=static_root,
            minifier=_minify_js,
            asset_type="JS",
        )


def build_custom_css(settings: Settings) -> None:
    """Собирает production-бандлы custom CSS на основе манифеста.

    Читает ``CUSTOM_CSS_MANIFEST_PATH``, разрешает наследование,
    конкатенирует и минифицирует каждый модуль с ключом ``dist``.

    Пути к файлам в манифесте задаются относительно STATIC_ROOT.
    """
    manifest_path = Path(settings.custom_css.MANIFEST_PATH).resolve()
    static_root = Path(settings.static.STATIC_ROOT).resolve()

    logger.info("[CSS] Manifest    : %s", manifest_path)
    logger.info("[CSS] Static root : %s", static_root)

    modules = load_asset_manifest(manifest_path, files_key="styles")

    for module_name in modules:
        _build_single_bundle(
            module_name,
            modules,
            files_key="styles",
            source_root=static_root,
            static_root=static_root,
            minifier=_minify_css,
            asset_type="CSS",
        )


def build_assets(settings: Settings) -> None:
    """Точка входа для сборки всех production-бандлов.

    Вызывается из ``lifespan`` при старте в prod-режиме.
    Проверяет флаги ``BUNDLE_LEGACY_JS`` и ``BUNDLE_CUSTOM_CSS``.

    В dev-режиме (``APP_DEBUG=True``) ничего не делает.
    """
    if settings.app.DEBUG:
        logger.debug("[build_assets] Dev-режим — сборка пропущена.")
        return

    if settings.app.BUNDLE_LEGACY_JS:
        logger.info("[build_assets] Сборка legacy JS бандлов…")
        try:
            build_legacy_js(settings)
        except AssetManifestError as exc:
            logger.error("[build_assets] Ошибка сборки JS: %s", exc)
            raise
    else:
        logger.info("[build_assets] BUNDLE_LEGACY_JS=false — JS-сборка пропущена.")

    if settings.app.BUNDLE_CUSTOM_CSS:
        logger.info("[build_assets] Сборка custom CSS бандлов…")
        try:
            build_custom_css(settings)
        except AssetManifestError as exc:
            logger.error("[build_assets] Ошибка сборки CSS: %s", exc)
            raise
    else:
        logger.info(
            "[build_assets] BUNDLE_CUSTOM_CSS=false — CSS-сборка пропущена."
        )
