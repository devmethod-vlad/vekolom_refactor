from __future__ import annotations

import logging
import uuid
from contextlib import AbstractContextManager

from redis import Redis


logger = logging.getLogger("app.backup")


class RedisBackupLock(AbstractContextManager):
    def __init__(self, *, redis_url: str, key: str, ttl_seconds: int) -> None:
        self._redis = Redis.from_url(redis_url, decode_responses=True)
        self._key = key
        self._ttl_seconds = ttl_seconds
        self._token = str(uuid.uuid4())
        self.acquired = False

    def acquire(self) -> bool:
        self.acquired = bool(
            self._redis.set(self._key, self._token, ex=self._ttl_seconds, nx=True)
        )
        return self.acquired

    def release(self) -> None:
        if not self.acquired:
            return

        current_value = self._redis.get(self._key)
        if current_value == self._token:
            self._redis.delete(self._key)
        self.acquired = False

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            self.release()
        except Exception:
            logger.exception("Failed to release backup lock")
        finally:
            self._redis.close()
