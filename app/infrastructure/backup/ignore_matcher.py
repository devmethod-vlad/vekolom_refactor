from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pathspec


logger = logging.getLogger("app.backup")


@dataclass(slots=True)
class IgnoreMatcher:
    patterns: list[str]

    def __post_init__(self) -> None:
        self._spec = pathspec.PathSpec.from_lines("gitwildmatch", self.patterns)

    def is_ignored(self, relative_path: Path) -> bool:
        return self._spec.match_file(relative_path.as_posix())


def load_ignore_patterns(
    *,
    project_root: Path,
    ignore_file_relative: str,
    extra_patterns: list[str],
) -> IgnoreMatcher:
    patterns: list[str] = []
    ignore_file = project_root / ignore_file_relative

    if ignore_file.exists():
        file_patterns = ignore_file.read_text(encoding="utf-8").splitlines()
        patterns.extend(file_patterns)
    else:
        logger.info("Ignore file does not exist: %s", ignore_file)

    patterns.extend(extra_patterns)
    cleaned = [pattern.strip() for pattern in patterns if pattern.strip() and not pattern.strip().startswith("#")]

    logger.info("Loaded %s backup ignore patterns", len(cleaned))
    return IgnoreMatcher(patterns=cleaned)
