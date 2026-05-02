# Nginx — общий reverse proxy для всех приложений

## Обзор архитектуры

Nginx вынесен из отдельных приложений в общую сервисную инфраструктуру. Один экземпляр nginx обслуживает все приложения, маршрутизируя трафик по `server_name`.

```
                         ┌─────────────────────────────────────────┐
                         │  docker-compose.service.nginx.yml       │
                         │                                         │
 :80/:443  ──────────────▶  nginx (общий reverse proxy)            │
                         │    ├─ vekolom.com  → vekolom:8001       │
                         │    ├─ app2.com     → app2:8002          │
                         │    └─ ...                               │
                         └──────────┬──────────────────────────────┘
                                    │ vekolom-service-network
                         ┌──────────┴──────────────────────────────┐
                         │  docker-compose.service.yml             │
                         │    ├─ postgresdb-vekolom                │
                         │    ├─ redis-vekolom                     │
                         │    └─ pgadmin-vekolom                   │
                         └─────────────────────────────────────────┘
```

## Файловая структура

```
services/nginx/
├── Dockerfile                          # Multi-stage: nginx + Brotli module
├── entrypoint.sh                       # Активация конфигов + ожидание upstream
├── nginx.conf                          # Глобальные настройки (http, events, rate limits)
│
├── snippets/                           # Общие фрагменты (shared между ВСЕМИ приложениями)
│   ├── compression.conf                #   Brotli + gzip
│   ├── proxy_params.conf               #   Параметры проксирования
│   └── bot_protection.conf             #   Фильтрация вредоносных ботов
│
└── apps/                               # Конфиги ПО ПРИЛОЖЕНИЯМ
    └── vekolom/                        #   ── Приложение vekolom ──
        ├── upstream.conf               #   Upstream-определение (общий для dev/prod)
        ├── locations.conf              #   Location-блоки (общие для dev/prod)
        ├── prod/                       #   Production-окружение
        │   ├── server.conf             #     Server-блок (vekolom.com)
        │   └── security_headers.conf   #     CSP + заголовки безопасности
        └── dev/                        #   Development-окружение
            ├── server.conf             #     Server-блок (vekolom.local)
            └── security_headers.conf   #     CSP + Vite dev server
```

## Принципы

### 1. Один файл — одна ответственность

| Файл | Что содержит | Когда менять |
|------|-------------|--------------|
| `upstream.conf` | Определение backend (host:port) | При смене порта приложения |
| `locations.conf` | Все location-блоки приложения | При добавлении endpoint'а |
| `{env}/server.conf` | Server-блок (listen, server_name) | При смене домена или SSL |
| `{env}/security_headers.conf` | CSP, HSTS, X-Frame-Options | При изменении CSP-политик |

### 2. Переключение dev/prod через entrypoint

Docker-образ содержит ВСЕ конфиги. `entrypoint.sh` при старте контейнера:
1. Читает `NGINX_ENV` (dev/prod)
2. Для каждого приложения в `apps/` копирует `{env}/server.conf` → `conf.d/`
3. Активирует соответствующий `security_headers.conf`
4. Ждёт готовности upstream-сервисов
5. Валидирует конфигурацию и запускает nginx

### 3. Мульти-приложения в dev: локальные домены

Вместо `localhost` (он один, а приложений много) используем **локальные домены**:

```
# /etc/hosts (добавить на хост-машине один раз)
127.0.0.1 vekolom.local
127.0.0.1 app2.local
```

Все приложения слушают **один порт** (8080 в dev), nginx маршрутизирует по `server_name`:
- `http://vekolom.local:8080` → vekolom:8001
- `http://app2.local:8080` → app2:8002

Это зеркалирует production-схему и не требует жонглирования портами.

## Быстрый старт

### Development

```bash
# 1. Добавить в /etc/hosts (один раз):
echo "127.0.0.1 vekolom.local" | sudo tee -a /etc/hosts

# 2. Создать общую сеть (один раз):
docker network create vekolom-service-network

# 3. Запустить сервисы + nginx:
cd service/
# .env уже настроен: COMPOSE_FILE='docker-compose.service.yml;docker-compose.service.nginx.yml'
# NGINX_ENV=dev, NGINX_HTTP_PORT=8080
docker compose up -d

# 4. Запустить приложение:
cd ../vekolom/
docker compose up -d
```

Доступ:
- `http://vekolom.local:8080` — через nginx (тестирование прод-схемы)
- `http://localhost:8001` — напрямую в FastAPI (обычная разработка)
- `http://localhost:5173` — Vite HMR dev server

### Production

```bash
# service/.env:
# NGINX_ENV=prod
# NGINX_HTTP_PORT=80
# NGINX_HTTPS_PORT=443
# NGINX_WAIT_HOSTS=vekolom:8001

cd service/
docker compose up -d --build

cd ../vekolom/
# vekolom/.env: COMPOSE_FILE='docker-compose.yml;docker-compose.prod.yml'
docker compose up -d --build
```

Доступ: `http://vekolom.com`

## Добавление нового приложения

### 1. Создать конфиги nginx

```bash
mkdir -p services/nginx/apps/myapp/{dev,prod}
```

**upstream.conf:**
```nginx
upstream myapp_backend {
    server myapp:8002;
    keepalive 32;
}
```

**locations.conf:**
```nginx
location /static/ {
    alias /data/myapp/static/;
    expires 30d;
    add_header Cache-Control "public, immutable";
    access_log off;
}

location / {
    proxy_pass http://myapp_backend;
    include /etc/nginx/snippets/proxy_params.conf;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
}
```

**prod/server.conf:**
```nginx
server {
    listen 80;
    server_name myapp.com www.myapp.com;
    charset utf-8;
    client_max_body_size 5m;
    include /etc/nginx/apps/myapp/active/security_headers.conf;
    if ($bad_bot) { return 444; }
    limit_req zone=general burst=30 nodelay;
    limit_conn addr 50;
    include /etc/nginx/apps/myapp/locations.conf;
}
```

**dev/server.conf:**
```nginx
server {
    listen 80;
    server_name myapp.local;
    charset utf-8;
    client_max_body_size 5m;
    include /etc/nginx/apps/myapp/active/security_headers.conf;
    if ($bad_bot) { return 444; }
    limit_req zone=general burst=30 nodelay;
    limit_conn addr 50;
    include /etc/nginx/apps/myapp/locations.conf;
}
```

### 2. Обновить docker-compose.service.nginx.yml

```yaml
services:
  nginx:
    volumes:
      # ... существующие volumes ...
      - ${MYAPP_PROJECT_DIR}/static:/data/myapp/static:ro
      - ${MYAPP_PROJECT_DIR}/media:/data/myapp/media:ro
    networks:
      - vekolom-service-network
      - myapp-service-network   # если у нового приложения своя сеть

networks:
  myapp-service-network:
    name: myapp-service-network
    external: true
```

### 3. Обновить service/.env

```env
NGINX_WAIT_HOSTS=vekolom:8001,myapp:8002
MYAPP_PROJECT_DIR=../myapp
```

### 4. Добавить в /etc/hosts (dev)

```
127.0.0.1 myapp.local
```

### 5. Пересобрать nginx

```bash
cd service/
docker compose build nginx
docker compose up -d nginx
```

## Кросс-compose зависимости

### Проблема

`depends_on` работает только **внутри** одного compose-проекта. Приложение vekolom и сервисы (postgres, redis) — в разных compose-файлах.

### Решение: трёхуровневое ожидание

```
┌────────────────────────────────────────────────────────────────┐
│  service/docker-compose.service.yml                            │
│    postgresdb-vekolom (healthcheck: pg_isready)                │
│    redis-vekolom      (healthcheck: redis-cli ping)            │
└──────────────┬─────────────────────────────────────────────────┘
               │ vekolom-service-network (TCP)
┌──────────────┴─────────────────────────────────────────────────┐
│  vekolom/docker-compose.{dev,prod}.yml                         │
│    vekolom (wait-for-services.py → ждёт postgres + redis)      │
│      healthcheck: curl /health                                 │
└──────────────┬─────────────────────────────────────────────────┘
               │ vekolom-service-network (TCP)
┌──────────────┴─────────────────────────────────────────────────┐
│  service/docker-compose.service.nginx.yml                      │
│    nginx (entrypoint.sh → ждёт vekolom:8001)                   │
└────────────────────────────────────────────────────────────────┘
```

1. **PostgreSQL / Redis**: healthcheck'и в docker-compose.service.yml
2. **Vekolom**: `scripts/wait-for-services.py` — ждёт TCP-доступность postgres и redis
3. **Nginx**: `entrypoint.sh` — ждёт TCP-доступность upstream-приложений

## Что общего, что различается

| Компонент                   | Production           | Development               |
|-----------------------------|----------------------|---------------------------|
| `server_name`               | `vekolom.com`        | `vekolom.local`           |
| Порт на хосте               | `80` / `443`         | `8080` / `8443`           |
| www → non-www redirect      | Да                   | Нет                       |
| SSL                         | Готово к включению   | Нет                       |
| CSP (script-src)            | Только prod-домены   | + `localhost:5173`        |
| CSP (connect-src)           | Только prod-домены   | + `ws://localhost:5173`   |
| Location-блоки              | `apps/vekolom/locations.conf` (общий файл)         |
| Bot protection              | `snippets/bot_protection.conf` (общий файл)        |
| Compression                 | `snippets/compression.conf` (общий файл)           |
| Proxy params                | `snippets/proxy_params.conf` (общий файл)          |

## Порядок запуска / остановки

### Запуск (dev)
```bash
docker network create vekolom-service-network 2>/dev/null || true
cd service/ && docker compose up -d       # postgres, redis, nginx
cd ../vekolom/ && docker compose up -d    # app, celery, frontend
```

### Остановка
```bash
cd vekolom/ && docker compose down
cd ../service/ && docker compose down
```

### Полная пересборка nginx
```bash
cd service/
docker compose build --no-cache nginx
docker compose up -d nginx
```
