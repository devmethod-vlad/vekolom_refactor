from __future__ import annotations

import io
import tarfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.infrastructure.backup.manifest import BackupManifest


@dataclass(slots=True)
class ArchiveResult:
    archive_path: Path
    archive_name: str
    created_at: datetime
    file_count: int
    total_uncompressed_size: int


def build_archive_name(prefix: str, timezone: str) -> tuple[str, datetime]:
    now = datetime.now(ZoneInfo(timezone))
    return f"{prefix}{now.strftime('%d%m%Y%H%M')}.tar.gz", now


def create_tar_gz_archive(
    *,
    temp_dir: Path,
    file_paths: list[Path],
    project_root: Path,
    prefix: str,
    timezone: str,
    manifest: BackupManifest | None = None,
) -> ArchiveResult:
    temp_dir.mkdir(parents=True, exist_ok=True)
    archive_name, created_at = build_archive_name(prefix=prefix, timezone=timezone)
    archive_path = temp_dir / archive_name

    file_count = len(file_paths)
    total_uncompressed_size = sum(path.stat().st_size for path in file_paths)

    with tarfile.open(archive_path, mode="w:gz") as tar:
        for path in file_paths:
            relative = path.relative_to(project_root)
            tar.add(path, arcname=str(relative), recursive=False)

        if manifest is not None:
            payload = manifest.as_json().encode("utf-8")
            tar_info = tarfile.TarInfo(name="backup_manifest.json")
            tar_info.size = len(payload)
            tar_info.mtime = created_at.timestamp()
            tar.addfile(tar_info, io.BytesIO(payload))

    return ArchiveResult(
        archive_path=archive_path,
        archive_name=archive_name,
        created_at=created_at,
        file_count=file_count,
        total_uncompressed_size=total_uncompressed_size,
    )
