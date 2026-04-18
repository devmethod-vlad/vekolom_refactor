from __future__ import annotations

import argparse
import json
import sys

from app.infrastructure.backup.service import BackupLockNotAcquiredError, FilesBackupService
from app.settings.config import settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Run project files backup to WebDAV")
    parser.add_argument("command", nargs="?", default="run", choices=["run"])
    args = parser.parse_args()

    if args.command != "run":
        parser.print_help()
        return 1

    service = FilesBackupService(settings.backup)
    try:
        summary = service.run(force=True)
    except BackupLockNotAcquiredError as exc:
        print(f"Backup skipped: {exc}")
        return 2
    except Exception as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary.__dict__, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
