# mock-plataforma: simula catalog, booking y review para el desarrollo local del Módulo 5.
# Solo para el docker-compose del servicio; nunca se despliega.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Mismas versiones que uv.lock del servicio.
RUN pip install --no-cache-dir fastapi==0.162.0 uvicorn==0.54.0

RUN useradd --create-home --uid 1000 mock
WORKDIR /srv
COPY app.py datos.py ./mocks/

USER mock
EXPOSE 9000

CMD ["uvicorn", "mocks.app:app", "--host", "0.0.0.0", "--port", "9000"]
