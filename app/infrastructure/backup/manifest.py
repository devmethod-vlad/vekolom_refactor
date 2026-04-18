from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class BackupManifest:
    created_at: str
    archive_name: str
    included_roots: list[str]
    excluded_patterns: list[str]
    file_count: int
    total_uncompressed_size: int
    checksum_sha256: str | None = None

    def as_json(self) -> str:
        return json.dumps(
            {
                "created_at": self.created_at,
                "archive_name": self.archive_name,
                "included_roots": self.included_roots,
                "excluded_patterns": self.excluded_patterns,
                "file_count": self.file_count,
                "total_uncompressed_size": self.total_uncompressed_size,
                "checksum_sha256": self.checksum_sha256,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_sha256_sidecar(path: Path, checksum: str) -> Path:
    sidecar_path = Path(f"{path}.sha256")
    sidecar_path.write_text(f"{checksum}  {path.name}\n", encoding="utf-8")
    return sidecar_path


def build_manifest(
    archive_name: str,
    included_roots: list[str],
    excluded_patterns: list[str],
    file_count: int,
    total_uncompressed_size: int,
    checksum_sha256: str | None,
    created_at: datetime,
) -> BackupManifest:
    return BackupManifest(
        created_at=created_at.isoformat(),
        archive_name=archive_name,
        included_roots=included_roots,
        excluded_patterns=excluded_patterns,
        file_count=file_count,
        total_uncompressed_size=total_uncompressed_size,
        checksum_sha256=checksum_sha256,
    )
