from __future__ import annotations

import logging
import os

from app.infrastructure.set_logging import configure_runtime_logging


def setup_backup_logger(*, log_file: str, log_level: str) -> logging.Logger:
    """Configure backup logger via shared runtime logging helper.

    `log_file` and `log_level` are kept for backward compatibility with
    BACKUP_* settings, but can be overridden by generic LOG_* runtime env vars.
    """

    resolved_level = os.getenv("LOG_LEVEL", log_level)
    resolved_file = os.getenv("LOG_FILE", log_file)
    resolved_log_to_file = os.getenv("LOG_TO_FILE", "false")

    configure_runtime_logging(
        service_name=os.getenv("SERVICE_NAME", "celery_backup_vekolom"),
        log_level=resolved_level,
        log_to_file=resolved_log_to_file,
        log_file=resolved_file,
    )

    return logging.getLogger("app.backup")
