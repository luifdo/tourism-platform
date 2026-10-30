# ---------- Etapa 1: dependencias ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
# Solo las dependencias de pyproject.toml, para que esta capa se reutilice mientras no cambien.
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > requirements.txt \
    && pip install -r requirements.txt

# ---------- Etapa 2: imagen de ejecución ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/srv/src \
    TZ=America/Bogota

RUN useradd --create-home --uid 1000 booking

# La imagen oficial borra los .pyc de la biblioteca estándar y en k8s el sistema de archivos es
# de solo lectura: sin esto, cada arranque recompila toda la stdlib (más de 20 s con CPU limitada).
RUN python -m compileall -q /usr/local/lib/python3.12

WORKDIR /srv
COPY --from=builder /opt/venv /opt/venv
COPY src ./src
# Migraciones: las corre el initContainer de k8s (o booking-migraciones en compose) con
# `alembic upgrade head`; PYTHONPATH=/srv/src permite que env.py importe config y tablas.
COPY alembic.ini ./
COPY migrations ./migrations
RUN python -m compileall -q src migrations

USER booking
EXPOSE 8003

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/health')"

CMD ["uvicorn", "main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8003"]
