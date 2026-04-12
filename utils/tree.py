import sys
from pathlib import Path

# Список игнорируемых элементов
IGNORE_LIST = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    ".env",
    ".env.local",
    ".env.prod",
    ".DS_Store",
    ".pytest_cache",
    ".mypy_cache",
    ".vscode",
    ".idea",
    "*.pyc",
    "*.log",
    "*.tmp",
    "Thumbs.db",
    "__init__.py",
    "tree.py",
}


def should_ignore(name: str) -> bool:
    """Проверяет, нужно ли игнорировать файл/папку по имени."""
    return any(
        name == pattern or (pattern.startswith("*.") and name.endswith(pattern[1:]))
        for pattern in IGNORE_LIST
    )


def tree(dir_path: Path, prefix: str = "") -> None:
    """Рекурсивно выводит структуру директории."""
    # Получаем содержимое, фильтруем игнорируемые элементы
    try:
        contents = sorted(
            [p for p in dir_path.iterdir() if not should_ignore(p.name)],
            key=lambda p: (p.is_file(), p.name.lower()),
        )
    except PermissionError:
        print(prefix + "└── [не доступно]")
        return
    if not contents:
        return
    pointers = ["├── "] * (len(contents) - 1) + ["└── "]

    for pointer, path in zip(pointers, contents, strict=True):
        print(prefix + pointer + path.name)
        if path.is_dir():
            extension = "│   " if pointer == "├── " else "    "
            tree(path, prefix + extension)


if __name__ == "__main__":
    root_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path()
    print("sys.argv[1] ", sys.argv[0])

    if not root_path.exists():
        print(f"Ошибка: путь '{root_path}' не существует.")
        sys.exit(1)

    print("СТРУКТУРА ПРОЕКТА:")  # noqa: RUF001
    print(root_path.name + "/")
    tree(root_path)
