###########################################
# БАЗА С UV И PYTHON — только для сборки  #
###########################################
ARG PYTHON_VERSION=3.12
ARG DIST=bookworm

FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-${DIST} AS base-uv
WORKDIR /vekolom

# Храним виртуалку вне /app, чтобы монтирование проекта в dev
# не «перезатирало» .venv. Это главный трюк для dev-тома.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1

#############################
# DEPS (prod-зависимости)   #
#############################
FROM base-uv AS deps
COPY pyproject.toml uv.lock* README.md ./
# Кешируем установку зависимостей
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

#############################
# DEPS-DEV (dev-зависимости)#
#############################
FROM base-uv AS deps-dev
COPY pyproject.toml uv.lock* README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --dev --no-install-project

###############################################
# RUNTIME-BASE (минимальный рантайм без кода) #
###############################################
FROM python:${PYTHON_VERSION}-slim-${DIST} AS runtime-base
WORKDIR /vekolom

# Рантайм-зависимости ОС (дополняй под свой стек)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 tzdata curl && \
    rm -rf /var/lib/apt/lists/*

# Копируем виртуалку и uv-бинарник из deps-стейджа (выбор — позже)
# PATH укажем после копирования.
COPY --from=deps /opt/venv /opt/venv
COPY --from=base-uv /usr/local/bin/uv /usr/local/bin/uv

ENV PATH="/opt/venv/bin:${PATH}"


#####################
# PROD (копируем код)
#####################
FROM runtime-base AS prod
# Перекрываем виртуалку prod-вариантом (на случай, если base сменили)
COPY --from=deps /opt/venv /opt/venv
# Копируем код внутрь образа
COPY . /vekolom

#####################
# DEV (без копии кода)
#####################
FROM runtime-base AS dev
# Для dev нам нужна .venv с dev-зависимостями:
COPY --from=deps-dev /opt/venv /opt/venv
# Код НЕ копируем — он будет примонтирован томом в compose
