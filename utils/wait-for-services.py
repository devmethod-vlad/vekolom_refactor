#!/usr/bin/env python3
"""
wait-for-services.py — ожидание готовности внешних сервисов перед стартом приложения.

Используется для кросс-compose зависимостей: postgres и redis запущены
в отдельном docker-compose.service.yml, depends_on между compose-проектами
не работает. Этот скрипт решает проблему.

Использование в docker-compose:
  command: >
    bash -c "python scripts/wait-for-services.py && uvicorn app.main:app ..."

Переменные окружения:
  POSTGRES_HOST   — хост PostgreSQL (default: postgresdb-vekolom)
  POSTGRES_POST   — порт PostgreSQL (default: 5432)
  REDIS_HOST      — хост Redis (default: redis-vekolom)
  REDIS_PORT      — порт Redis (default: 6379)
  WAIT_TIMEOUT    — таймаут на каждый сервис в секундах (default: 60)
"""

import os
import socket
import sys
import time


def wait_for_tcp(host: str, port: int, timeout: int, label: str) -> bool:
    """Ждёт TCP-соединения с хостом. Возвращает True при успехе."""
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


def main() -> int:
    timeout = int(os.environ.get("WAIT_TIMEOUT", "60"))

    services = [
        {
            "label": "PostgreSQL",
            "host": os.environ.get("POSTGRES_HOST", "postgresdb-vekolom"),
            "port": int(os.environ.get("POSTGRES_POST", "5432")),
        },
        {
            "label": "Redis",
            "host": os.environ.get("REDIS_HOST", "redis-vekolom"),
            "port": int(os.environ.get("REDIS_PORT", "6379")),
        },
    ]

    print("=" * 60, flush=True)
    print("Waiting for external services...", flush=True)
    print("=" * 60, flush=True)

    all_ok = True
    for svc in services:
        ok = wait_for_tcp(svc["host"], svc["port"], timeout, svc["label"])
        if not ok:
            all_ok = False

    if all_ok:
        print("=" * 60, flush=True)
        print("All services ready. Starting application...", flush=True)
        print("=" * 60, flush=True)
        return 0
    else:
        print("=" * 60, flush=True)
        print("WARNING: Some services unavailable. Starting anyway...", flush=True)
        print("=" * 60, flush=True)
        return 0  # Не падаем — пусть приложение само обработает ошибку подключения


if __name__ == "__main__":
    sys.exit(main())
