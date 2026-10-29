# Variables de entorno

> Módulo 5 · [Índice](./README.md)

Estas son las variables de `services/recommendation-service/.env.example`. El archivo original de `develop` traía variables de RabbitMQ (que este módulo no usa) y luego se le añadieron `GEMINI_MODEL` y `GEMINI_API_KEY`; ambas cosas se reemplazaron por las de aquí. Los valores son de desarrollo; el `.env` real nunca se sube al repositorio.

```
SERVICE_PORT=8005

# Base de datos propia (Fase 1)
DB_URL=postgresql+psycopg://turismo:turismo@postgres:5432/recommendation_db

# Sesiones del chat, TTL de 24 h (Fase 1)
VALKEY_URL=redis://valkey:6379/0

# Servicios que consultan las tools; en local apuntan al mock (Fase 2)
CATALOG_URL=http://mock-plataforma:9000/api/catalog
BOOKING_URL=http://mock-plataforma:9000/api/bookings
REVIEW_URL=http://mock-plataforma:9000/api/reviews

# Proveedor de IA (Fase 5); ver 08-simulacion.md
LLM_PROVIDER=groq
LLM_API_KEY=
LLM_MODEL=
```

Las variables del proveedor de IA son genéricas (`LLM_*`). `LLM_PROVIDER=groq` elige el adaptador de Groq; `LLM_API_KEY` es la clave de Groq (queda vacía hasta la Fase 5) y `LLM_MODEL` el modelo de Groq que se use, que debe admitir llamada a funciones (tools). En Kubernetes la clave será un `Secret` y el modelo un `ConfigMap`.

> **Decisión del equipo:** se usan variables genéricas `LLM_*` y no `GEMINI_*` ni `GROQ_*`, para que cambiar de proveedor no obligue a renombrar variables. El SRS y el Plan todavía nombran `GEMINI_API_KEY` y `GEMINI_MODEL`, de cuando el proveedor previsto era Gemini.

---
[← Dockerfile (explicado)](./05-dockerfile.md) · [Base de datos →](./07-base-de-datos.md)
