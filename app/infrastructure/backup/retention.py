from __future__ import annotations

import logging
import re
from datetime import datetime

from app.infrastructure.backup.webdav_client import RemoteEntry, WebDavClient


logger = logging.getLogger("app.backup")

_ARCHIVE_RE = re.compile(r"^(?P<prefix>.+?)(?P<ts>\d{12})\.tar\.gz$")


def _extract_timestamp(file_name: str) -> datetime | None:
    match = _ARCHIVE_RE.match(file_name)
    if not match:
        return None

    try:
        return datetime.strptime(match.group("ts"), "%d%m%Y%H%M")
    except ValueError:
        return None


def apply_retention(
    *,
    client: WebDavClient,
    remote_dir: str,
    filename_prefix: str,
    retention_count: int,
    write_sha256: bool,
) -> tuple[list[str], list[str]]:
    entries = client.list_dir(remote_dir)
    archive_entries: list[tuple[datetime, RemoteEntry]] = []
    sha_entries = {entry.name for entry in entries if entry.name.endswith(".tar.gz.sha256")}

    for entry in entries:
        if entry.is_dir:
            continue
        if not entry.name.startswith(filename_prefix):
            continue
        if not entry.name.endswith(".tar.gz"):
            continue

        timestamp = _extract_timestamp(entry.name)
        if timestamp is None:
            continue

        archive_entries.append((timestamp, entry))

    archive_entries.sort(key=lambda pair: pair[0], reverse=True)
    keep = [entry.name for _, entry in archive_entries[:retention_count]]

    deleted: list[str] = []
    for _, entry in archive_entries[retention_count:]:
        client.delete_file(entry.path)
        deleted.append(entry.name)
        if write_sha256:
            sidecar_name = f"{entry.name}.sha256"
            if sidecar_name in sha_entries:
                client.delete_file(f"{remote_dir.rstrip('/')}/{sidecar_name}")
                deleted.append(sidecar_name)

    logger.info("Retention completed. Keep=%s delete=%s", keep, deleted)
    return keep, deleted
