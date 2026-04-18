"""Application settings.

This project uses Pydantic Settings v2.

Why we add a maintenance DSN
----------------------------
`POSTGRES_DB` (-> `PostgresSettings.db`) points to the target application
database. If that database does not exist yet, we cannot connect to it to run
Alembic migrations.

So we keep a second DSN (`maintenance_dsn`) that connects to a known-existing
database (by default: `postgres`) and can execute `CREATE DATABASE ...`.
"""

import json
from pathlib import Path
import typing as tp

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class EnvBaseSettings(BaseSettings):
    """Base settings with .env support."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class AppSettings(EnvBaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="app_")

    DEBUG: bool = False

    # Needed for cookie-based sessions in Starlette-Admin (SessionMiddleware).
    SECRET_KEY: str = "CHANGE_ME_PLEASE"

    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"
    ADMIN_TITLE: str = "Vekolom Admin"

    # -------------------------------------------------------------------------
    # Флаги сборки production-бандлов.
    # Влияют только на legacy JS и custom CSS (Vite собирается отдельно).
    # -------------------------------------------------------------------------
    BUNDLE_LEGACY_JS: bool = True
    BUNDLE_CUSTOM_CSS: bool = True


class PostgresSettings(EnvBaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="postgres_")

    host: str
    port: int = 5432
    user: str
    password: str
    db: str  # POSTGRES_DB

    # App works asynchronously, but Starlette-Admin and Alembic use sync engine.
    use_async: bool = True
    async_driver: str = "asyncpg"
    sync_driver: str = "psycopg2"  # psycopg3; can be changed later

    echo: bool = False

    # Pools/sessions (used in Database.from_config)
    pool_size: int = 5
    pool_overflow_size: int = 10
    autoflush: bool = False
    expire_on_commit: bool = False

    # Where to connect to create DB if it doesn't exist (usually `postgres`)
    maintenance_db: str = "postgres"

    # DSNs
    dsn: str | None = None
    sync_dsn: str | None = None
    maintenance_dsn: str | None = None

    # Future: replicas
    slave_hosts: list[str] = Field(default_factory=list)
    slave_dsns: list[str] = Field(default_factory=list)

    def _build_sqlalchemy_url(self, *, driver: str, database: str) -> str:
        return URL.create(
            drivername=f"postgresql+{driver}",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=database,
        ).render_as_string(hide_password=False)

    @model_validator(mode="after")
    def assemble_db_connection(self) -> tp.Self:
        if self.dsn is None:
            driver = self.async_driver if self.use_async else self.sync_driver
            self.dsn = self._build_sqlalchemy_url(driver=driver, database=self.db)

        if self.sync_dsn is None:
            self.sync_dsn = self._build_sqlalchemy_url(driver=self.sync_driver, database=self.db)

        if self.maintenance_dsn is None:
            self.maintenance_dsn = self._build_sqlalchemy_url(
                driver=self.sync_driver,
                database=self.maintenance_db,
            )

        return self


class StaticSettings(EnvBaseSettings):
    """Settings for static files storage.

    STATIC_ROOT — абсолютный или относительный путь к каталогу со статическими
                  файлами на диске. Именно этот путь монтируется в FastAPI в dev
                  и именно его обычно читает Nginx в prod.

    STATIC_URL  — URL-префикс для отдачи статики браузеру.
                  По умолчанию: ``/static/``.

    Почему это вынесено в .env
    --------------------------
    Раньше путь до static-каталога был захардкожен прямо в ``main.py``.
    Это неудобно: dev/prod-окружения, bind mount'ы Docker и layout проекта
    могут отличаться. Теперь путь настраивается так же явно, как и MEDIA_ROOT.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="static_")

    STATIC_ROOT: str = "static"
    STATIC_URL: str = "/static/"

    @property
    def mount_path(self) -> str:
        """Нормализованный mount path для FastAPI/Starlette."""
        return "/" + self.STATIC_URL.strip("/")


class LegacyAssetsSettings(EnvBaseSettings):
    """Настройки legacy-ассетов (jQuery, плагины, старый classic JS).

    LEGACY_MANIFEST_PATH — путь до JSON-файла с именованными модулями.
                           Может лежать где угодно: внутри frontend/, рядом
                           с проектом, в отдельной config-папке и т.д.

    Пути к файлам скриптов внутри манифеста задаются ОТНОСИТЕЛЬНО STATIC_ROOT.
    Например: ``js/legacy/jquery.js`` → ``STATIC_ROOT/js/legacy/jquery.js``.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="legacy_")

    MANIFEST_PATH: str = "frontend/legacy_scripts.json"


class CustomCSSSettings(EnvBaseSettings):
    """Настройки пользовательских CSS-ассетов.

    CUSTOM_CSS_MANIFEST_PATH — путь до JSON-файла с именованными CSS-модулями.
                               Может лежать где угодно.

    Пути к CSS-файлам внутри манифеста задаются ОТНОСИТЕЛЬНО STATIC_ROOT.
    Например: ``css/custom/home.css`` → ``STATIC_ROOT/css/custom/home.css``.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="custom_css_")

    MANIFEST_PATH: str = "static/custom_css.json"


class MediaSettings(EnvBaseSettings):
    """Settings for media files storage.

    MEDIA_ROOT — абсолютный или относительный путь к папке с медиафайлами на диске.
                 В dev это папка рядом с проектом; в prod Nginx читает её напрямую.

    MEDIA_URL  — URL-префикс для отдачи медиафайлов браузеру.
                 В dev FastAPI монтирует MEDIA_ROOT под этот prefix.
                 В prod Nginx отдаёт location /media/ из MEDIA_ROOT.

    CAROUSEL_SIZE — размер (ширина × высота) для ResizeToFill слайдов карусели.
                    Совпадает с ProcessedImageField(processors=[ResizeToFill(2050, 544)]) в Django.

    CAROUSEL_QUALITY — качество JPEG для слайдов карусели (аналог options={'quality': 90}).

    WEBP_QUALITY — качество webp при конвертации (аналог im.save(..., 'webp', quality='20')).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="media_")

    MEDIA_ROOT: str = "media"
    MEDIA_URL: str = "/media/"

    # Carousel image processing — зеркалирует Django ProcessedImageField
    CAROUSEL_WIDTH: int = 2050
    CAROUSEL_HEIGHT: int = 544
    CAROUSEL_QUALITY: int = 90

    # WebP conversion — зеркалирует Celery-задачу slide_to_webp
    WEBP_QUALITY: int = 20

    @property
    def mount_path(self) -> str:
        """Нормализованный mount path для FastAPI/Starlette."""
        return "/" + self.MEDIA_URL.strip("/")


class UploadPhotoSettings(EnvBaseSettings):
    """Settings for file upload validation.

    Все параметры можно задать через .env (с префиксом UPLOAD_) и при этом
    переопределить непосредственно при вызове функции upload-обработчика.

    UPLOAD_ALLOWED_IMAGE_FORMATS — допустимые расширения файлов изображений.
    UPLOAD_MAX_FILE_SIZE_MB      — максимальный размер загружаемого файла в мегабайтах.
    UPLOAD_MAX_FILENAME_LENGTH   — максимальная длина оригинального имени файла в символах.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="upload_")

    ALLOWED_IMAGE_FORMATS: list[str] = ["jpeg", "jpg", "png"]
    MAX_FILE_SIZE_MB: int = 10
    MAX_FILENAME_LENGTH: int = 100


class AdminTinyMCEEditorSettings(EnvBaseSettings):
    """Настройки self-hosted TinyMCE для админки.

    Идея простая: JS-файлы TinyMCE лежат локально в проекте (или в любом
    другом каталоге, который вы пробросите в контейнер), а админка берёт
    их по URL из `ASSETS_URL`.

    Структура каталога по умолчанию ожидается такой:

        static/vendor/tinymce/
        ├── tinymce.min.js
        └── jquery/
            └── tinymce-jquery.min.js

    При необходимости путь до файлов можно переопределить через `.env`.

    TOOLBAR / PLUGINS / MENUBAR позволяют не хардкодить набор кнопок
    в Python-коде: редактор можно подкручивать переменными окружения,
    а не хирургией по коду в каждом field.

    EXTRA_OPTIONS_JSON — escape hatch для редких настроек TinyMCE, которые
    не хочется выносить в отдельные переменные. Ожидается JSON-объект.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="admin_tinymce_",
    )

    ASSETS_DIR: str = "static/vendor/tinymce"
    ASSETS_URL: str = "/assets/tinymce"

    # Относительные пути внутри ASSETS_DIR/ASSETS_URL
    TINYMCE_JS_PATH: str = "tinymce.min.js"
    TINYMCE_JQUERY_JS_PATH: str = "jquery/tinymce-jquery.min.js"

    HEIGHT: int = 420
    MENUBAR: bool | str = "file edit view insert format tools table help"
    STATUSBAR: bool = True
    TOOLBAR: str = (
        "undo redo | blocks | bold italic underline strikethrough forecolor backcolor | "
        "alignleft aligncenter alignright alignjustify | bullist numlist outdent indent | "
        "link image media table blockquote code fullscreen preview removeformat"
    )
    PLUGINS: str = (
        "advlist autolink lists link image charmap preview anchor searchreplace "
        "visualblocks code fullscreen insertdatetime media table help wordcount"
    )
    CONTENT_STYLE: str = (
        "body { font-family: -apple-system, BlinkMacSystemFont, San Francisco, Segoe UI, "
        "Roboto, Helvetica Neue, sans-serif; font-size: 14px; "
        "-webkit-font-smoothing: antialiased; }"
    )
    EXTRA_OPTIONS_JSON: str = "{}"

    @property
    def extra_options(self) -> dict[str, tp.Any]:
        """Возвращает дополнительные TinyMCE-опции из JSON в .env.

        Если JSON битый или там не объект, сразу падаем понятной ошибкой,
        вместо того чтобы потом ловить загадочные фронтовые артефакты.
        """
        try:
            parsed = json.loads(self.EXTRA_OPTIONS_JSON or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(
                "ADMIN_TINYMCE_EXTRA_OPTIONS_JSON должен быть валидным JSON-объектом"
            ) from exc

        if not isinstance(parsed, dict):
            raise ValueError(
                "ADMIN_TINYMCE_EXTRA_OPTIONS_JSON должен содержать JSON-объект"
            )
        return parsed


class SeoSettings(EnvBaseSettings):
    """Настройки для SEO: canonical URL, Open Graph и структурированные данные.

    SITE_URL — каноничный домен сайта без trailing slash.
               Используется для формирования canonical-ссылок, og:url,
               sitemap.xml и robots.txt.

    OG_IMAGE_PATH — путь к изображению для Open Graph (относительно STATIC_ROOT).
                    Используется как og:image по умолчанию, если страница
                    не задаёт своё собственное.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="seo_")

    SITE_URL: str = "https://vekolom.ru"
    OG_IMAGE_PATH: str = "images/common/logo.png"


class CelerySettings(EnvBaseSettings):
    """Settings for Celery task queue.

    В dev Redis запускается через docker-compose (сервис redis).
    CELERY_BROKER_URL и CELERY_RESULT_BACKEND читаются из .env.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="celery_")

    broker_url: str = "redis://redis-vekolom:6379/0"
    result_backend: str = "redis://redis-vekolom:6379/0"

    # Зеркалирует acks_late=True из Django Celery-задачи
    task_acks_late: bool = True

    # Повторные попытки при потере соединения с брокером
    broker_connection_retry_on_startup: bool = True

    timezone: str = "Europe/Moscow"


class BackupSettings(EnvBaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="backup_")

    ENABLED: bool = False
    INCLUDE_DIRS: list[str] = Field(default_factory=lambda: ["media", "static"])
    IGNORE_FILE: str = ".backupignore"
    EXCLUDE_PATTERNS: list[str] = Field(default_factory=list)
    TEMP_DIR: str = "tmp/backups"
    FILENAME_PREFIX: str = "files_backup_"
    REMOTE_DIR: str = ""
    RETENTION_COUNT: int = 10
    SCHEDULE_CRON: str | None = None
    INTERVAL_MINUTES: int | None = None
    LOG_FILE: str = "logs/files_backup.log"
    LOG_LEVEL: str = "INFO"
    TIMEZONE: str = "Europe/Moscow"
    WEBDAV_BASE_URL: str = ""
    WEBDAV_USERNAME: str = ""
    WEBDAV_PASSWORD: SecretStr = SecretStr("")
    VERIFY_TLS: bool = True
    REQUEST_TIMEOUT_SECONDS: int = 120
    LOCK_REDIS_URL: str | None = None
    LOCK_KEY: str = "vekolom:backup:files:lock"
    LOCK_TTL_SECONDS: int = 7200
    FOLLOW_SYMLINKS: bool = False
    WRITE_SHA256: bool = True

    @property
    def effective_lock_redis_url(self) -> str:
        if self.LOCK_REDIS_URL:
            return self.LOCK_REDIS_URL
        raise ValueError("Backup lock Redis URL is not configured")

    @model_validator(mode="after")
    def validate_paths_and_schedule(self) -> tp.Self:
        if self.SCHEDULE_CRON and self.INTERVAL_MINUTES:
            raise ValueError(
                "Нельзя одновременно задавать BACKUP_SCHEDULE_CRON и BACKUP_INTERVAL_MINUTES"
            )

        if self.ENABLED and not self.INCLUDE_DIRS:
            raise ValueError("BACKUP_INCLUDE_DIRS не может быть пустым при BACKUP_ENABLED=true")
        if self.ENABLED:
            if not self.REMOTE_DIR:
                raise ValueError("BACKUP_REMOTE_DIR обязателен при BACKUP_ENABLED=true")
            if not self.WEBDAV_BASE_URL:
                raise ValueError("BACKUP_WEBDAV_BASE_URL обязателен при BACKUP_ENABLED=true")
            if not self.WEBDAV_USERNAME:
                raise ValueError("BACKUP_WEBDAV_USERNAME обязателен при BACKUP_ENABLED=true")
            if not self.WEBDAV_PASSWORD.get_secret_value():
                raise ValueError("BACKUP_WEBDAV_PASSWORD обязателен при BACKUP_ENABLED=true")

        for include in self.INCLUDE_DIRS:
            include_path = Path(include)
            if include_path.is_absolute():
                raise ValueError(f"BACKUP_INCLUDE_DIRS содержит абсолютный путь: {include}")
            if ".." in include_path.parts:
                raise ValueError(f"BACKUP_INCLUDE_DIRS содержит небезопасный сегмент '..': {include}")

        ignore_path = Path(self.IGNORE_FILE)
        if ignore_path.is_absolute() or ".." in ignore_path.parts:
            raise ValueError("BACKUP_IGNORE_FILE должен быть относительным путём внутри проекта")

        temp_path = Path(self.TEMP_DIR)
        if temp_path.is_absolute() or ".." in temp_path.parts:
            raise ValueError("BACKUP_TEMP_DIR должен быть относительным путём внутри проекта")

        if self.INTERVAL_MINUTES is not None and self.INTERVAL_MINUTES <= 0:
            raise ValueError("BACKUP_INTERVAL_MINUTES должен быть > 0")

        if self.RETENTION_COUNT <= 0:
            raise ValueError("BACKUP_RETENTION_COUNT должен быть > 0")

        if self.REQUEST_TIMEOUT_SECONDS <= 0:
            raise ValueError("BACKUP_REQUEST_TIMEOUT_SECONDS должен быть > 0")

        if self.LOCK_TTL_SECONDS <= 0:
            raise ValueError("BACKUP_LOCK_TTL_SECONDS должен быть > 0")

        return self


class ViteSettings(EnvBaseSettings):
    """Settings for Vite-powered frontend assets.

    ENABLED                — включает новый pipeline ассетов.
    DEV_SERVER_ORIGIN      — откуда шаблоны берут dev-ассеты в DEBUG.
    FRONTEND_ROOT          — корень frontend-проекта с package.json/vite.config.ts.
    BUILD_DIR              — куда `vite build` складывает production-ассеты.
    MANIFEST_FILE          — имя manifest-файла внутри BUILD_DIR.
    ASSET_URL_PREFIX       — URL-префикс для собранных файлов.

    Идея безопасной миграции:
      - VITE_ENABLED=false  -> проект живёт на старой схеме с ручными static links;
      - VITE_ENABLED=true   -> Jinja2 подключает entrypoint'ы через Vite.

    Так можно переводить страницы по одной, а не переписывать весь фронт за раз.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="vite_")

    ENABLED: bool = False
    DEV_SERVER_ORIGIN: str = "http://localhost:5173"

    FRONTEND_ROOT: str = "frontend"
    BUILD_DIR: str = "static/dist"
    MANIFEST_FILE: str = "manifest.json"
    ASSET_URL_PREFIX: str = "/static/dist"

    @property
    def manifest_path(self) -> str:
        return str((Path(self.BUILD_DIR) / self.MANIFEST_FILE).resolve())


class Settings(EnvBaseSettings):
    app: AppSettings = Field(default_factory=AppSettings)
    database: PostgresSettings = Field(default_factory=PostgresSettings)
    media: MediaSettings = Field(default_factory=MediaSettings)
    static: StaticSettings = Field(default_factory=StaticSettings)
    upload: UploadPhotoSettings = Field(default_factory=UploadPhotoSettings)
    admin_tinymce: AdminTinyMCEEditorSettings = Field(default_factory=AdminTinyMCEEditorSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    backup: BackupSettings = Field(default_factory=BackupSettings)
    vite: ViteSettings = Field(default_factory=ViteSettings)
    legacy: LegacyAssetsSettings = Field(default_factory=LegacyAssetsSettings)
    custom_css: CustomCSSSettings = Field(default_factory=CustomCSSSettings)
    seo: SeoSettings = Field(default_factory=SeoSettings)

    @model_validator(mode="after")
    def finalize_backup_settings(self) -> tp.Self:
        if not self.backup.LOCK_REDIS_URL and self.celery.broker_url.startswith("redis://"):
            self.backup.LOCK_REDIS_URL = self.celery.broker_url
        return self


settings = Settings()
