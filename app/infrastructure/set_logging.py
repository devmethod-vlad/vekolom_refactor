from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_LOGGING_SIGNATURE_ATTR = "_vekolom_logging_signature"
_HANDLER_MARK_ATTR = "_vekolom_managed_handler"


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

    config_signature = (
        resolved_service_name,
        resolved_level,
        resolved_log_to_file,
        str(resolved_log_file),
    )

    root_logger = logging.getLogger()
    if getattr(root_logger, _LOGGING_SIGNATURE_ATTR, None) == config_signature:
        return

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    for handler in list(root_logger.handlers):
        if getattr(handler, _HANDLER_MARK_ATTR, False):
            root_logger.removeHandler(handler)
            handler.close()

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setLevel(resolved_level)
    stream_handler.setFormatter(formatter)
    setattr(stream_handler, _HANDLER_MARK_ATTR, True)
    root_logger.addHandler(stream_handler)

    if resolved_log_to_file:
        file_path = Path(resolved_log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setLevel(resolved_level)
        file_handler.setFormatter(formatter)
        setattr(file_handler, _HANDLER_MARK_ATTR, True)
        root_logger.addHandler(file_handler)

    root_logger.setLevel(resolved_level)
    setattr(root_logger, _LOGGING_SIGNATURE_ATTR, config_signature)


def setup_logging(debug: bool = False) -> None:
    """Backward-compatible application logging entrypoint."""
    configure_runtime_logging(debug=debug)
