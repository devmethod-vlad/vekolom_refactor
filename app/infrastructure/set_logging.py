from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_LOGGING_SIGNATURE_ATTR = "_vekolom_logging_signature"
_HANDLER_MARK_ATTR = "_vekolom_managed_handler"
_ACCESS_LOGGERS = ("uvicorn.access", "gunicorn.access")
_ERROR_LOGGERS = ("uvicorn.error", "gunicorn.error")


def _env_flag(value: str | bool | None, *, default: bool = False) -> bool:
    """Parse bool-like environment values in a predictable way."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "yes", "y", "on"}


def configure_runtime_logging(
    *,
    service_name: str | None = None,
    debug: bool = False,
    log_level: str | None = None,
    log_to_file: bool | str | None = None,
    log_file: str | None = None,
    access_log_enabled: bool | str | None = None,
    access_log_file: str | None = None,
) -> None:
    """Configure root logging for container-friendly runtime.

    Rules:
    - stdout logging is always enabled;
    - file logging is optional and controlled by env/args;
    - setup is idempotent: repeated calls with same config do nothing;
    - no rotation handlers are used.
    """

    resolved_service_name = service_name or os.getenv("SERVICE_NAME", "vekolom")
    resolved_level_name = (log_level or os.getenv("LOG_LEVEL") or ("DEBUG" if debug else "INFO")).upper()
    resolved_level = getattr(logging, resolved_level_name, logging.INFO)
    resolved_log_to_file = _env_flag(log_to_file if log_to_file is not None else os.getenv("LOG_TO_FILE"))
    resolved_log_file = log_file or os.getenv("LOG_FILE") or f"/vekolom/logs/{resolved_service_name}.log"
    resolved_access_log_enabled = _env_flag(
        access_log_enabled if access_log_enabled is not None else os.getenv("ACCESS_LOG_ENABLED"),
        default=False,
    )
    resolved_access_log_file = access_log_file or os.getenv("ACCESS_LOG_FILE") or "/vekolom/logs/access.log"

    config_signature = (
        resolved_service_name,
        resolved_level,
        resolved_log_to_file,
        str(resolved_log_file),
        resolved_access_log_enabled,
        str(resolved_access_log_file),
    )

    root_logger = logging.getLogger()
    if getattr(root_logger, _LOGGING_SIGNATURE_ATTR, None) == config_signature:
        return

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    for handler in list(root_logger.handlers):
        if getattr(handler, _HANDLER_MARK_ATTR, False):
            root_logger.removeHandler(handler)
            handler.close()

    app_stream_handler = logging.StreamHandler(stream=sys.stdout)
    app_stream_handler.setLevel(resolved_level)
    app_stream_handler.setFormatter(formatter)
    setattr(app_stream_handler, _HANDLER_MARK_ATTR, True)
    root_logger.addHandler(app_stream_handler)

    if resolved_log_to_file:
        file_path = Path(resolved_log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        app_file_handler = logging.FileHandler(file_path, encoding="utf-8")
        app_file_handler.setLevel(resolved_level)
        app_file_handler.setFormatter(formatter)
        setattr(app_file_handler, _HANDLER_MARK_ATTR, True)
        root_logger.addHandler(app_file_handler)

    root_logger.setLevel(resolved_level)

    # Make error-channel loggers emit through root only (stdout + optional app.log).
    for logger_name in _ERROR_LOGGERS:
        error_logger = logging.getLogger(logger_name)
        error_logger.handlers.clear()
        error_logger.propagate = True
        error_logger.disabled = False

    # Access loggers are split from application logs on purpose.
    for logger_name in _ACCESS_LOGGERS:
        access_logger = logging.getLogger(logger_name)
        access_logger.handlers.clear()
        access_logger.propagate = False
        access_logger.setLevel(resolved_level)
        access_logger.disabled = not resolved_access_log_enabled

        if not resolved_access_log_enabled:
            continue

        access_stream_handler = logging.StreamHandler(stream=sys.stdout)
        access_stream_handler.setLevel(resolved_level)
        access_stream_handler.setFormatter(formatter)
        access_logger.addHandler(access_stream_handler)

        if resolved_log_to_file:
            access_file_path = Path(resolved_access_log_file)
            access_file_path.parent.mkdir(parents=True, exist_ok=True)
            access_file_handler = logging.FileHandler(access_file_path, encoding="utf-8")
            access_file_handler.setLevel(resolved_level)
            access_file_handler.setFormatter(formatter)
            access_logger.addHandler(access_file_handler)

    setattr(root_logger, _LOGGING_SIGNATURE_ATTR, config_signature)


def setup_logging(debug: bool = False) -> None:
    """Backward-compatible application logging entrypoint."""
    configure_runtime_logging(debug=debug)
