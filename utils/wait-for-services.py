#!/usr/bin/env python3
"""Wait for selected external TCP services before app startup.

Designed for cross-compose dependencies where `depends_on` is unavailable.

Environment variables:
  POSTGRES_HOST   — PostgreSQL host (default: postgresdb-vekolom)
  POSTGRES_PORT   — PostgreSQL port (default: 5432)
  REDIS_HOST      — Redis host (default: redis-vekolom)
  REDIS_PORT      — Redis port (default: 6379)
  WAIT_TIMEOUT    — timeout per service in seconds (default: 60)
  WAIT_FOR        — comma-separated dependencies: postgres,redis (default: postgres,redis)
  WAIT_STRICT     — when true, exits non-zero if any service is unavailable
"""

from __future__ import annotations

import os
import socket
import sys
import time


SUPPORTED_SERVICES = {"postgres", "redis"}


def _env_flag(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def wait_for_tcp(host: str, port: int, timeout: int, label: str) -> bool:
    """Wait for TCP endpoint availability."""
    print(f"⏳ Waiting for {label} ({host}:{port})...", flush=True)
    start = time.monotonic()

    while time.monotonic() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=2):
                elapsed = time.monotonic() - start
                print(f"✅ {label} is ready ({elapsed:.1f}s)", flush=True)
                return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            time.sleep(1)

    print(f"❌ TIMEOUT: {label} ({host}:{port}) not reachable after {timeout}s", flush=True)
    return False


def _selected_services() -> list[str]:
    raw_value = os.environ.get("WAIT_FOR", "postgres,redis")
    selected = [item.strip().lower() for item in raw_value.split(",") if item.strip()]

    if not selected:
        return []

    unknown = [name for name in selected if name not in SUPPORTED_SERVICES]
    if unknown:
        raise ValueError(
            f"Unsupported WAIT_FOR values: {', '.join(unknown)}. "
            f"Supported values: {', '.join(sorted(SUPPORTED_SERVICES))}"
        )

    return selected


def main() -> int:
    timeout = int(os.environ.get("WAIT_TIMEOUT", "60"))
    strict = _env_flag(os.environ.get("WAIT_STRICT"), default=False)

    service_options = {
        "postgres": {
            "label": "PostgreSQL",
            "host": os.environ.get("POSTGRES_HOST", "postgresdb-vekolom"),
            "port": int(os.environ.get("POSTGRES_PORT", "5432")),
        },
        "redis": {
            "label": "Redis",
            "host": os.environ.get("REDIS_HOST", "redis-vekolom"),
            "port": int(os.environ.get("REDIS_PORT", "6379")),
        },
    }

    selected = _selected_services()
    if not selected:
        print("WAIT_FOR is empty, skipping dependency checks.", flush=True)
        return 0

    print("=" * 60, flush=True)
    print(f"Waiting for services: {', '.join(selected)}", flush=True)
    print("=" * 60, flush=True)

    all_ok = True
    for service_name in selected:
        svc = service_options[service_name]
        ok = wait_for_tcp(svc["host"], svc["port"], timeout, svc["label"])
        if not ok:
            all_ok = False

    print("=" * 60, flush=True)
    if all_ok:
        print("All required services are ready.", flush=True)
        print("=" * 60, flush=True)
        return 0

    if strict:
        print("Required services are unavailable and WAIT_STRICT=true.", flush=True)
        print("=" * 60, flush=True)
        return 1

    print("Some required services are unavailable, continuing (WAIT_STRICT=false).", flush=True)
    print("=" * 60, flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(2)
