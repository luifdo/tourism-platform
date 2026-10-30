# ---------- Etapa 1: instalar dependencias con uv ----------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /build

# Solo las dependencias, para que esta capa se reutilice mientras no cambie el lockfile.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ---------- Etapa 2: imagen de ejecución ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN useradd --create-home --uid 1000 recommendation

# La imagen oficial borra los .pyc de la biblioteca estándar y en k8s el sistema de archivos es
# de solo lectura: sin esto, cada arranque recompila toda la stdlib.
RUN python -m compileall -q /usr/local/lib/python3.12

WORKDIR /srv
COPY --from=builder /opt/venv /opt/venv
COPY src ./src

USER recommendation
EXPOSE 8005

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8005/health')"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8005"]
