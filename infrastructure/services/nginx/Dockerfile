# =============================================================================
# Nginx с модулем Brotli — multi-stage сборка.
#
# Почему собираем сами:
#   Официальный образ nginx:alpine НЕ включает модуль Brotli.
#   Brotli даёт ~15–20% выигрыш в сжатии по сравнению с gzip,
#   что ускоряет загрузку страниц (особенно на мобильных сетях).
#
# Структура:
#   1. builder   — компилирует ngx_brotli как dynamic module.
#   2. runtime   — копирует .so-файлы в чистый nginx-образ + entrypoint.
#
# Обновление: при смене версии Nginx обновите ARG NGINX_VERSION.
# =============================================================================

ARG NGINX_VERSION=1.27.4

# ---------------------------------------------------------------------------
# Этап 1: сборка модуля Brotli
# ---------------------------------------------------------------------------
FROM nginx:${NGINX_VERSION}-alpine AS builder

RUN apk add --no-cache \
        build-base \
        git \
        pcre2-dev \
        zlib-dev \
        openssl-dev \
        cmake

# Исходники nginx нужны для компиляции dynamic module
RUN wget "http://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz" -O /tmp/nginx.tar.gz \
    && mkdir -p /usr/src/nginx \
    && tar -xzf /tmp/nginx.tar.gz -C /usr/src/nginx --strip-components=1

# Клонируем ngx_brotli и его подмодуль (libbrotli)
RUN git clone --recurse-submodules https://github.com/google/ngx_brotli.git /usr/src/ngx_brotli

# Собираем libbrotli из исходников (CMake)
RUN cd /usr/src/ngx_brotli/deps/brotli \
    && mkdir out && cd out \
    && cmake -DCMAKE_BUILD_TYPE=Release \
             -DBUILD_SHARED_LIBS=OFF \
             -DCMAKE_INSTALL_PREFIX=/usr/local \
             -DCMAKE_C_FLAGS="-Ofast -flto -funroll-loops -ffunction-sections -fdata-sections -Wl,--gc-sections" \
             .. \
    && cmake --build . --config Release --target brotlienc \
    && cmake --build . --config Release --target brotlidec \
    && cmake --build . --config Release --target brotlicommon

# Собираем dynamic modules (ngx_http_brotli_filter_module + ngx_http_brotli_static_module)
RUN cd /usr/src/nginx \
    && CONFARGS=$(nginx -V 2>&1 | sed -n 's/.*configure arguments: //p') \
    && eval ./configure $CONFARGS \
         --add-dynamic-module=/usr/src/ngx_brotli \
    && make modules \
    && cp objs/ngx_http_brotli_filter_module.so /usr/lib/nginx/modules/ \
    && cp objs/ngx_http_brotli_static_module.so /usr/lib/nginx/modules/


# ---------------------------------------------------------------------------
# Этап 2: финальный образ
# ---------------------------------------------------------------------------
FROM nginx:${NGINX_VERSION}-alpine AS runtime

# Копируем скомпилированные модули
COPY --from=builder /usr/lib/nginx/modules/ngx_http_brotli_filter_module.so /usr/lib/nginx/modules/
COPY --from=builder /usr/lib/nginx/modules/ngx_http_brotli_static_module.so /usr/lib/nginx/modules/

# Копируем конфигурацию
COPY nginx.conf      /etc/nginx/nginx.conf
COPY snippets/       /etc/nginx/snippets/
COPY apps/           /etc/nginx/apps/

# Очищаем дефолтные конфиги (entrypoint сгенерирует нужные)
RUN rm -f /etc/nginx/conf.d/*.conf

# Копируем и настраиваем entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80 443

ENTRYPOINT ["/entrypoint.sh"]
