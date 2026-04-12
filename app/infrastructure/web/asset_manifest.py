"""Универсальный загрузчик и резолвер манифестов ассетов.

Этот модуль — фундамент мини-фреймворка ассетов проекта. Он решает три задачи:

1. Читает JSON-манифест с именованными модулями ассетов.
2. Нормализует и валидирует относительные пути к файлам.
3. Разрешает наследование (``extend``) между модулями: если модуль ``home``
   расширяет ``base``, то при запросе ``home`` сначала идут файлы из ``base``,
   затем собственные файлы ``home`` — без дублей.

Формат манифеста
----------------
JSON-объект, где каждый ключ — имя модуля, а значение — объект::

    {
      "_comment": "служебный комментарий, будет проигнорирован",
      "base": {
        "scripts": ["jquery.js", "plugins/camera.js"],
        "dist": "dist/legacy/legacy.base.min.js"
      },
      "home": {
        "extend": ["base"],
        "scripts": ["home-slider.js"],
        "dist": "dist/legacy/legacy.home.min.js"
      }
    }

Ключи модуля:
  - ``scripts`` / ``styles`` — упорядоченный список файлов (зависит от типа).
  - ``extend``               — список модулей, файлы которых подключаются первыми.
  - ``dist``                 — путь к production-бандлу относительно STATIC_ROOT.

Зачем отдельный модуль
----------------------
Одни и те же правила используются в трёх местах:
  - при рендере тегов в Jinja2 (dev и prod);
  - при сборке production-бандлов;
  - при валидации конфигурации.

Если держать эту логику в каждом менеджере отдельно, неизбежен дрифт.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import TypedDict


class AssetManifestError(RuntimeError):
    """Ошибка конфигурации манифеста ассетов."""


# ─────────────────────────────────────────────────────────────────────
# Типизация модуля манифеста
# ─────────────────────────────────────────────────────────────────────

class AssetModule(TypedDict, total=False):
    """Описание одного модуля в манифесте.

    ``files_key`` (``scripts`` или ``styles``) заполняется динамически
    в зависимости от типа манифеста — здесь указаны оба варианта.
    """

    scripts: list[str]
    styles: list[str]
    extend: list[str]
    dist: str


# ─────────────────────────────────────────────────────────────────────
# Нормализация путей
# ─────────────────────────────────────────────────────────────────────

def normalize_relative_path(raw_path: str, *, context: str) -> PurePosixPath:
    """Нормализует относительный POSIX-путь.

    В JSON-манифесте и в env мы храним web-friendly пути c ``/``, а не системные
    пути конкретной ОС. Это избавляет от лишней магии и делает конфиг одинаковым
    для Windows, Linux и Docker.

    Разрешаем только относительные пути без ``..`` и без пустых сегментов.
    Таким образом скрипт не сможет случайно вылезти за пределы каталога ассетов.

    Args:
        raw_path: строка из JSON-манифеста или ``.env``.
        context: контекст вызова для понятного текста ошибки.

    Returns:
        PurePosixPath: проверенный относительный путь.

    Raises:
        AssetManifestError: если путь некорректный.
    """
    value = (raw_path or "").strip()
    if not value:
        raise AssetManifestError(f"{context} не должен быть пустым.")

    path = PurePosixPath(value)

    if path.is_absolute():
        raise AssetManifestError(
            f"{context} должен быть относительным путём, получен абсолютный: {raw_path!r}"
        )

    if any(part in {"", ".", ".."} for part in path.parts):
        raise AssetManifestError(
            f"{context} содержит недопустимые сегменты '.' или '..': {raw_path!r}"
        )

    return path


# ─────────────────────────────────────────────────────────────────────
# Загрузка и валидация манифеста
# ─────────────────────────────────────────────────────────────────────

def load_asset_manifest(
    manifest_path: Path,
    *,
    files_key: str,
) -> dict[str, AssetModule]:
    """Читает JSON-манифест ассетов и валидирует его структуру.

    Args:
        manifest_path: абсолютный путь до JSON-файла.
        files_key: имя ключа со списком файлов (``scripts`` или ``styles``).

    Returns:
        Словарь ``{module_name: AssetModule}``.

    Raises:
        AssetManifestError: при любых проблемах с файлом или форматом.
    """
    if not manifest_path.exists():
        raise AssetManifestError(
            f"Не найден манифест ассетов: {manifest_path}. "
            "Проверьте путь в настройках."
        )

    try:
        with manifest_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise AssetManifestError(
            f"Манифест содержит невалидный JSON: {manifest_path}"
        ) from exc

    if not isinstance(data, dict):
        raise AssetManifestError(
            f"Манифест должен содержать JSON-объект, получен: {type(data).__name__}"
        )

    modules: dict[str, AssetModule] = {}
    for module_name, module_data in data.items():
        # Служебные ключи (начинаются с ``_``) игнорируются.
        if isinstance(module_name, str) and module_name.startswith("_"):
            continue

        if not isinstance(module_name, str) or not module_name.strip():
            raise AssetManifestError(
                f"Имя модуля должно быть непустой строкой, получено: {module_name!r}"
            )

        if not isinstance(module_data, dict):
            raise AssetManifestError(
                f"Модуль {module_name!r} должен быть объектом, "
                f"получен: {type(module_data).__name__}"
            )

        # Валидация списка файлов.
        raw_files = module_data.get(files_key, [])
        if not isinstance(raw_files, list):
            raise AssetManifestError(
                f"Модуль {module_name!r}: ключ {files_key!r} должен быть массивом."
            )

        validated_files: list[str] = []
        for index, raw_file in enumerate(raw_files, start=1):
            if not isinstance(raw_file, str):
                raise AssetManifestError(
                    f"Модуль {module_name!r}: {files_key}[{index}] должен быть строкой пути."
                )
            norm = normalize_relative_path(
                raw_file,
                context=f"manifest → {module_name}.{files_key}[{index}]",
            )
            validated_files.append(norm.as_posix())

        # Валидация extend.
        raw_extend = module_data.get("extend", [])
        if not isinstance(raw_extend, list):
            raise AssetManifestError(
                f"Модуль {module_name!r}: ключ 'extend' должен быть массивом."
            )
        for ext_name in raw_extend:
            if not isinstance(ext_name, str) or not ext_name.strip():
                raise AssetManifestError(
                    f"Модуль {module_name!r}: элемент extend должен быть непустой строкой, "
                    f"получено: {ext_name!r}"
                )

        # Валидация dist.
        raw_dist = module_data.get("dist")
        if raw_dist is not None:
            if not isinstance(raw_dist, str) or not raw_dist.strip():
                raise AssetManifestError(
                    f"Модуль {module_name!r}: ключ 'dist' должен быть непустой строкой."
                )
            normalize_relative_path(
                raw_dist,
                context=f"manifest → {module_name}.dist",
            )

        module: AssetModule = {}
        module[files_key] = validated_files  # type: ignore[literal-required]
        if raw_extend:
            module["extend"] = [e.strip() for e in raw_extend]
        if raw_dist:
            module["dist"] = raw_dist.strip()

        modules[module_name] = module

    # Проверяем, что все extend-ссылки указывают на существующие модули.
    for module_name, module in modules.items():
        for ext_name in module.get("extend", []):
            if ext_name not in modules:
                raise AssetManifestError(
                    f"Модуль {module_name!r} расширяет несуществующий модуль {ext_name!r}. "
                    f"Доступные модули: {', '.join(sorted(modules.keys()))}"
                )

    return modules


# ─────────────────────────────────────────────────────────────────────
# Разрешение наследования
# ─────────────────────────────────────────────────────────────────────

def resolve_files(
    modules: dict[str, AssetModule],
    module_name: str,
    *,
    files_key: str,
) -> list[str]:
    """Собирает упорядоченный список файлов с учётом наследования (``extend``).

    Алгоритм: depth-first обход графа ``extend``, файлы родителей идут
    раньше файлов потомков. Дубликаты отсекаются: файл попадает в результат
    только при первом появлении.

    Обнаруживает циклические зависимости и бросает ``AssetManifestError``.

    Args:
        modules: загруженный манифест.
        module_name: имя запрашиваемого модуля.
        files_key: ``scripts`` или ``styles``.

    Returns:
        Плоский список относительных путей (POSIX, без дублей).
    """
    if module_name not in modules:
        available = ", ".join(sorted(modules.keys()))
        raise AssetManifestError(
            f"Модуль {module_name!r} не найден в манифесте. "
            f"Доступные модули: {available}"
        )

    resolved_order: list[str] = []
    seen_files: set[str] = set()
    resolved_modules: set[str] = set()
    resolving_stack: set[str] = set()

    def _resolve(name: str) -> None:
        if name in resolved_modules:
            return
        if name in resolving_stack:
            raise AssetManifestError(
                f"Обнаружена циклическая зависимость при разрешении модуля "
                f"{module_name!r}: {name!r} уже в стеке разрешения."
            )

        resolving_stack.add(name)

        module = modules[name]
        for ext_name in module.get("extend", []):
            _resolve(ext_name)

        for file_path in module.get(files_key, []):
            if file_path not in seen_files:
                seen_files.add(file_path)
                resolved_order.append(file_path)

        resolving_stack.discard(name)
        resolved_modules.add(name)

    _resolve(module_name)
    return resolved_order
