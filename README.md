# vekolom

#### Первоначальная генерация uv.lock:
```bash
docker run --rm -it -v "${PWD}:/app" -w /app ghcr.io/astral-sh/uv:python3.12-bookworm uv lock
```