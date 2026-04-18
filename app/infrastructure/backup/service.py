from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from app.infrastructure.backup.archiver import create_tar_gz_archive
from app.infrastructure.backup.ignore_matcher import load_ignore_patterns
from app.infrastructure.backup.lock import RedisBackupLock
from app.infrastructure.backup.logging_utils import setup_backup_logger
from app.infrastructure.backup.manifest import build_manifest, compute_sha256, write_sha256_sidecar
from app.infrastructure.backup.retention import apply_retention
from app.infrastructure.backup.webdav_client import WebDavClient
from app.settings.config import BackupSettings


class BackupDisabledError(RuntimeError):
    pass


class BackupLockNotAcquiredError(RuntimeError):
    pass


@dataclass(slots=True)
class BackupRunSummary:
    archive_name: str
    remote_archive_path: str
    remote_checksum_path: str | None
    file_count: int
    total_uncompressed_size: int
    duration_seconds: float
    deleted_remote_files: list[str]


class FilesBackupService:
    def __init__(self, backup_settings: BackupSettings, project_root: Path | None = None) -> None:
        self.settings = backup_settings
        self.project_root = (project_root or Path.cwd()).resolve()
        self.logger = setup_backup_logger(
            log_file=self.settings.LOG_FILE,
            log_level=self.settings.LOG_LEVEL,
        )

    def _resolve_relative_path(self, value: str, *, must_exist: bool = False) -> Path:
        candidate = (self.project_root / value).resolve()
        candidate.relative_to(self.project_root)
        if must_exist and not candidate.exists():
            self.logger.error("Required path does not exist: %s", value)
            raise FileNotFoundError(f"Path does not exist: {value}")
        return candidate

    def _collect_candidate_files(self, includes: list[str], follow_symlinks: bool) -> tuple[list[Path], int]:
        file_paths: list[Path] = []
        total_size = 0

        for include in includes:
            include_root = self._resolve_relative_path(include, must_exist=True)
            if not include_root.is_dir():
                self.logger.error("Include path is not a directory: %s", include)
                raise NotADirectoryError(f"Include path is not a directory: {include}")

            for path in include_root.rglob("*"):
                if path.is_dir():
                    continue
                if path.is_symlink() and not follow_symlinks:
                    continue

                resolved = path.resolve()
                resolved.relative_to(self.project_root)
                file_paths.append(resolved)
                total_size += resolved.stat().st_size

        return file_paths, total_size

    def run(self, *, force: bool = False) -> BackupRunSummary:
        if not self.settings.ENABLED and not force:
            raise BackupDisabledError("Backup is disabled by BACKUP_ENABLED=false")

        started_at = time.perf_counter()
        self.logger.info("Starting files backup")

        lock = RedisBackupLock(
            redis_url=self.settings.effective_lock_redis_url,
            key=self.settings.LOCK_KEY,
            ttl_seconds=self.settings.LOCK_TTL_SECONDS,
        )
        if not lock.acquire():
            self.logger.warning("Backup skipped: lock is already acquired")
            raise BackupLockNotAcquiredError("Cannot acquire backup lock")

        archive_path: Path | None = None
        checksum_path: Path | None = None

        try:
            ignore_matcher = load_ignore_patterns(
                project_root=self.project_root,
                ignore_file_relative=self.settings.IGNORE_FILE,
                extra_patterns=self.settings.EXCLUDE_PATTERNS,
            )

            file_paths, _ = self._collect_candidate_files(
                includes=self.settings.INCLUDE_DIRS,
                follow_symlinks=self.settings.FOLLOW_SYMLINKS,
            )
            filtered_files = [
                path
                for path in file_paths
                if not ignore_matcher.is_ignored(path.relative_to(self.project_root))
            ]
            self.logger.info(
                "Collected %s files, after ignore=%s",
                len(file_paths),
                len(filtered_files),
            )

            temp_dir = self._resolve_relative_path(self.settings.TEMP_DIR)
            temp_dir.mkdir(parents=True, exist_ok=True)

            initial_manifest = build_manifest(
                archive_name="pending",
                included_roots=self.settings.INCLUDE_DIRS,
                excluded_patterns=ignore_matcher.patterns,
                file_count=len(filtered_files),
                total_uncompressed_size=sum(path.stat().st_size for path in filtered_files),
                checksum_sha256=None,
                created_at=time_to_datetime(self.settings.TIMEZONE),
            )

            archive_result = create_tar_gz_archive(
                temp_dir=temp_dir,
                file_paths=filtered_files,
                project_root=self.project_root,
                prefix=self.settings.FILENAME_PREFIX,
                timezone=self.settings.TIMEZONE,
                manifest=initial_manifest,
            )
            archive_path = archive_result.archive_path

            checksum = None
            if self.settings.WRITE_SHA256:
                checksum = compute_sha256(archive_path)
                checksum_path = write_sha256_sidecar(archive_path, checksum)

            with WebDavClient(
                base_url=self.settings.WEBDAV_BASE_URL,
                username=self.settings.WEBDAV_USERNAME,
                password=self.settings.WEBDAV_PASSWORD.get_secret_value(),
                timeout_seconds=self.settings.REQUEST_TIMEOUT_SECONDS,
                verify_tls=self.settings.VERIFY_TLS,
            ) as webdav:
                webdav.ensure_remote_dir(self.settings.REMOTE_DIR)

                remote_archive_path = f"{self.settings.REMOTE_DIR.rstrip('/')}/{archive_path.name}"
                webdav.upload_file(archive_path, remote_archive_path)

                remote_checksum_path = None
                if checksum_path is not None:
                    remote_checksum_path = f"{remote_archive_path}.sha256"
                    webdav.upload_file(checksum_path, remote_checksum_path)

                _, deleted = apply_retention(
                    client=webdav,
                    remote_dir=self.settings.REMOTE_DIR,
                    filename_prefix=self.settings.FILENAME_PREFIX,
                    retention_count=self.settings.RETENTION_COUNT,
                    write_sha256=self.settings.WRITE_SHA256,
                )

            duration = time.perf_counter() - started_at
            self.logger.info("Backup finished successfully in %.2f seconds", duration)
            return BackupRunSummary(
                archive_name=archive_path.name,
                remote_archive_path=remote_archive_path,
                remote_checksum_path=remote_checksum_path,
                file_count=archive_result.file_count,
                total_uncompressed_size=archive_result.total_uncompressed_size,
                duration_seconds=duration,
                deleted_remote_files=deleted,
            )
        finally:
            if checksum_path and checksum_path.exists():
                checksum_path.unlink(missing_ok=True)
            if archive_path and archive_path.exists():
                archive_path.unlink(missing_ok=True)

            temp_root = self._resolve_relative_path(self.settings.TEMP_DIR)
            if temp_root.exists() and not any(temp_root.iterdir()):
                shutil.rmtree(temp_root, ignore_errors=True)
            lock.release()


def time_to_datetime(timezone: str):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(timezone))
