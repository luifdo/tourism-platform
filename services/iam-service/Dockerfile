# ---------- Etapa 1: instalar dependencias con uv ----------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /build

# Primero solo las dependencias, para que esta capa se reutilice mientras no cambie el lockfile.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY README.md ./
COPY app ./app
RUN uv sync --frozen --no-dev --no-editable

# ---------- Etapa 2: imagen de ejecución ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    FORWARDED_ALLOW_IPS=127.0.0.1

RUN useradd --create-home --uid 1000 iam

# La imagen oficial borra los .pyc de la biblioteca estándar y en k8s el sistema de archivos es
# de solo lectura: sin esto, cada arranque recompila toda la stdlib.
RUN python -m compileall -q /usr/local/lib/python3.12

# La misma imagen corre la API, el worker (python -m app.worker) y las migraciones
# (alembic upgrade head). Las llaves JWT no van aquí: se montan en /srv/keys. Lo único que se
# escribe va a /tmp, un emptyDir en k8s.
WORKDIR /srv
COPY --from=builder /opt/venv /opt/venv
COPY alembic.ini ./
COPY migrations ./migrations

USER iam
EXPOSE 8001

# /health/live no consulta PostgreSQL ni Valkey (C-32).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health/live')"

# Uvicorn lee FORWARDED_ALLOW_IPS del entorno; en k3s la fija el ConfigMap (C-37, C-56).
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers"]
