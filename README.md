# vekolom

## Runtime compose/logging схема (prod-friendly)

### Согласованные сервисы

Во всех compose-файлах используются единые имена runtime-сервисов:

- `vekolom`
- `celery_vekolom`
- `celery_backup_vekolom`
- `celery_beat_vekolom`

### Переменные окружения для runtime

Ключевые переменные вынесены в `.env`:

- Redis/Celery: `REDIS_HOST`, `REDIS_PORT`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- Startup wait: `WAIT_TIMEOUT`
- Frontend dev: `FRONTEND_PORT`, `FRONTEND_HMR_HOST`, `FRONTEND_HMR_PORT`, `FRONTEND_HMR_PROTOCOL`
- Concurrency: `CELERY_WORKER_CONCURRENCY`, `CELERY_BACKUP_WORKER_CONCURRENCY`
- Host logs root: `HOST_LOG_ROOT`
- Per-service logging:
  - `VEKOLOM_LOG_TO_FILE`, `VEKOLOM_LOG_LEVEL`
  - `CELERY_VEKOLOM_LOG_TO_FILE`, `CELERY_VEKOLOM_LOG_LEVEL`
  - `CELERY_BACKUP_VEKOLOM_LOG_TO_FILE`, `CELERY_BACKUP_VEKOLOM_LOG_LEVEL`
  - `CELERY_BEAT_VEKOLOM_LOG_TO_FILE`, `CELERY_BEAT_VEKOLOM_LOG_LEVEL`

Внутри контейнеров используется унифицированный runtime контракт:

- `SERVICE_NAME`
- `LOG_TO_FILE`
- `LOG_LEVEL`
- `LOG_FILE`

Compose маппит эти значения из service-specific переменных.

### Логирование

- `stdout` включён всегда (удобно для `docker logs`).
- File logging включается только флагом `*_LOG_TO_FILE=true`.
- Ротация не используется (обычный `logging.FileHandler`).
- Схема единая для FastAPI, Celery worker, backup worker и beat.
- Инициализация логирования идемпотентна: повторные вызовы не дублируют handlers.
- По умолчанию file logging выключен.

### Host log mounts

Каждый runtime-сервис пишет в отдельный bind mount:

- `${HOST_LOG_ROOT}/vekolom:/vekolom/logs` → `/vekolom/logs/vekolom.log`
- `${HOST_LOG_ROOT}/celery_vekolom:/vekolom/logs` → `/vekolom/logs/celery_vekolom.log`
- `${HOST_LOG_ROOT}/celery_backup_vekolom:/vekolom/logs` → `/vekolom/logs/celery_backup_vekolom.log`
- `${HOST_LOG_ROOT}/celery_beat_vekolom:/vekolom/logs` → `/vekolom/logs/celery_beat_vekolom.log`

### Startup orchestration

- `utils/wait-for-services.py` ждёт только нужные зависимости через `WAIT_FOR`.
  - `vekolom` ждёт `postgres`.
  - Celery-сервисы ждут `redis`.
- Есть strict-режим (`WAIT_STRICT=true`): при недоступности зависимости процесс завершается с non-zero кодом.
- Исправлено имя env-порта БД: `POSTGRES_PORT` (вместо старого `POSTGRES_POST`).

### Порядок старта внутри compose

- `celery_vekolom` и `celery_backup_vekolom` имеют healthcheck через `celery inspect ping`.
- `vekolom` запускается после `celery_vekolom: healthy`.
- `celery_beat_vekolom` зависит от `celery_backup_vekolom: healthy` (важно: именно beat зависит от backup worker).
- У `vekolom` healthcheck через `GET /health`.

## Локальная установка зависимостей

#### Установка зависимости в контейнер приложения
```bash
uv add --no-sync jinja2
```

Если нужно сразу обновить окружение в контейнере:
```bash
uv sync --no-install-project
```

Почему в 2 шага: обычный `uv add` запускает sync с попыткой собрать проект, а в текущем сервисе это не всегда применимо.

---

## Files backup в Mail.ru Cloud через WebDAV

Реализована инфраструктурная backup-подсистема в `app/infrastructure/backup/*`:

- синхронный backup-сервис;
- отдельная Celery task `run_files_backup` в очереди `backups`;
- запуск по Celery Beat (cron или interval);
- ручной запуск через CLI;
- lock в Redis, чтобы не было параллельных запусков;
- retention старых архивов;
- `.backupignore` + env-паттерны через `pathspec`.

### Новые env-переменные (`BACKUP_*`)

```env
BACKUP_ENABLED=false
BACKUP_INCLUDE_DIRS=["media","static"]
BACKUP_IGNORE_FILE=.backupignore
BACKUP_EXCLUDE_PATTERNS=[]
BACKUP_TEMP_DIR=tmp/backups
BACKUP_FILENAME_PREFIX=files_backup_
BACKUP_REMOTE_DIR=/vekolom/backups/files
BACKUP_RETENTION_COUNT=10
BACKUP_SCHEDULE_CRON=
BACKUP_INTERVAL_MINUTES=
BACKUP_LOG_FILE=logs/files_backup.log
BACKUP_LOG_LEVEL=INFO
BACKUP_TIMEZONE=Europe/Moscow
BACKUP_WEBDAV_BASE_URL=https://webdav.cloud.mail.ru
BACKUP_WEBDAV_USERNAME=
BACKUP_WEBDAV_PASSWORD=
BACKUP_VERIFY_TLS=true
BACKUP_REQUEST_TIMEOUT_SECONDS=120
BACKUP_LOCK_REDIS_URL=
BACKUP_LOCK_KEY=vekolom:backup:files:lock
BACKUP_LOCK_TTL_SECONDS=7200
BACKUP_FOLLOW_SYMLINKS=false
BACKUP_WRITE_SHA256=true
```

> Если `BACKUP_LOCK_REDIS_URL` не задан, используется `CELERY_BROKER_URL`, если это `redis://...`.

### Поведение backup

1. Читает настройки.
2. Берёт Redis-lock.
3. Проверяет include-директории (fail fast, если нет хотя бы одной).
4. Загружает ignore-правила из `.backupignore` + `BACKUP_EXCLUDE_PATTERNS`.
5. Собирает файлы рекурсивно.
6. Формирует архив на диске: `files_backup_DDMMYYYYHHMM.tar.gz`.
7. Опционально создаёт sidecar checksum `.sha256`.
8. Создаёт удалённую папку в WebDAV (MKCOL), если отсутствует.
9. Загружает архив и checksum.
10. Выполняет retention и удаляет старые архивы.
11. Удаляет временные локальные файлы.
12. Освобождает lock.

### Расписание

Поддерживаются 2 режима (взаимоисключающие):

- `BACKUP_SCHEDULE_CRON="30 2 * * *"`
- `BACKUP_INTERVAL_MINUTES=120`

Если оба пустые — scheduled backup не регистрируется, но ручной запуск доступен.

### Ручной запуск backup

В контейнере приложения:

```bash
python -m app.infrastructure.backup.cli
```

или

```bash
python -m app.infrastructure.backup.cli run
```

CLI возвращает ненулевой exit code при ошибке.

### Docker Compose сервисы

- `celery_vekolom` — общий worker существующих задач;
- `celery_backup_vekolom` — отдельный worker очереди `backups` (`--queues=backups --concurrency=1`);
- `celery_beat_vekolom` — планировщик Celery Beat.

Примеры запуска:

```bash
docker compose up -d celery_backup_vekolom
```

```bash
docker compose up -d celery_beat_vekolom
```

```bash
docker compose exec vekolom python -m app.infrastructure.backup.cli run
```

### `.backupignore`

В корне проекта добавлен рабочий `.backupignore` с безопасными дефолтами (логи, кэши, временные backup-файлы и т.д.).

Поддерживаются gitignore-подобные паттерны и negation (`!`) за счёт `pathspec`.

### Ограничения

- Не follow symlink по умолчанию (`BACKUP_FOLLOW_SYMLINKS=false`).
- Include-пути только относительные и без `..`.
- Backup не стартует без lock Redis.
- Retention сортирует архивы по timestamp в имени, а не только по mtime WebDAV.
