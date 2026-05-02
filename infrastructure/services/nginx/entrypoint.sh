#!/bin/sh
# =============================================================================
# entrypoint.sh — активация конфигов и ожидание upstream-сервисов.
#
# Переменные окружения:
#   NGINX_ENV          — dev | prod (default: prod)
#   NGINX_WAIT_HOSTS   — через запятую: host1:port1,host2:port2
#   NGINX_WAIT_TIMEOUT — секунд на каждый хост (default: 60)
# =============================================================================
set -e

NGINX_ENV="${NGINX_ENV:-prod}"
NGINX_WAIT_TIMEOUT="${NGINX_WAIT_TIMEOUT:-60}"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Активация конфигов в зависимости от окружения
# ─────────────────────────────────────────────────────────────────────────────
echo "==> Nginx environment: ${NGINX_ENV}"
echo "==> Activating configs..."

# Очищаем conf.d/ (Dockerfile уже удалил дефолтные, но на всякий случай)
rm -f /etc/nginx/conf.d/*.conf

for app_dir in /etc/nginx/apps/*/; do
    [ -d "$app_dir" ] || continue
    app=$(basename "$app_dir")

    # Проверяем наличие конфига для выбранного окружения
    if [ ! -f "$app_dir/${NGINX_ENV}/server.conf" ]; then
        echo "  !! SKIP ${app}: no ${NGINX_ENV}/server.conf found"
        continue
    fi

    echo "  -> ${app} (${NGINX_ENV})"

    # upstream.conf → conf.d/ (одинаковый для dev и prod)
    if [ -f "$app_dir/upstream.conf" ]; then
        cp "$app_dir/upstream.conf" "/etc/nginx/conf.d/${app}_upstream.conf"
    fi

    # server.conf → conf.d/ (env-специфичный)
    cp "$app_dir/${NGINX_ENV}/server.conf" "/etc/nginx/conf.d/${app}.conf"

    # Активируем env-специфичный security_headers.conf
    # Server-блоки include'ят из /etc/nginx/apps/{app}/active/
    mkdir -p "$app_dir/active"
    if [ -f "$app_dir/${NGINX_ENV}/security_headers.conf" ]; then
        cp "$app_dir/${NGINX_ENV}/security_headers.conf" "$app_dir/active/security_headers.conf"
    fi
done

# ─────────────────────────────────────────────────────────────────────────────
# 2. Ожидание upstream-сервисов
# ─────────────────────────────────────────────────────────────────────────────
if [ -n "$NGINX_WAIT_HOSTS" ]; then
    echo "==> Waiting for upstream services..."

    # Разбираем NGINX_WAIT_HOSTS: "vekolom:8001,app2:8002"
    OLD_IFS="$IFS"
    IFS=','
    for host_port in $NGINX_WAIT_HOSTS; do
        host=$(echo "$host_port" | cut -d: -f1)
        port=$(echo "$host_port" | cut -d: -f2)
        elapsed=0

        echo "  -> Waiting for ${host}:${port} (timeout: ${NGINX_WAIT_TIMEOUT}s)..."

        while ! nc -z -w2 "$host" "$port" 2>/dev/null; do
            elapsed=$((elapsed + 1))
            if [ "$elapsed" -ge "$NGINX_WAIT_TIMEOUT" ]; then
                echo "  !! WARNING: Timeout waiting for ${host}:${port} — proceeding anyway"
                break
            fi
            sleep 1
        done

        if [ "$elapsed" -lt "$NGINX_WAIT_TIMEOUT" ]; then
            echo "  -> ${host}:${port} is ready (${elapsed}s)"
        fi
    done
    IFS="$OLD_IFS"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 3. Валидация конфигурации и запуск
# ─────────────────────────────────────────────────────────────────────────────
echo "==> Validating nginx config..."
nginx -t

echo "==> Starting nginx..."
exec nginx -g 'daemon off;'
