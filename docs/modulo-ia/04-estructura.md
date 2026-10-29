# Estructura de carpetas

> Módulo 5 · [Índice](./README.md)

Sigue la arquitectura hexagonal de la plantilla del monorepo:

```
services/recommendation-service/
├── Dockerfile
├── docker-compose.yml        # compose propio del servicio
├── pyproject.toml            # dependencias y configuración de ruff y pytest
├── uv.lock                   # versiones exactas (lo genera uv)
├── .dockerignore
├── .env.example
├── src/
│   ├── __init__.py
│   ├── main.py               # crea la app FastAPI y conecta los adaptadores
│   ├── domain/               # reglas de negocio puras
│   ├── application/          # casos de uso
│   │   └── ports/            # interfaces: modelo de lenguaje, tools, sesiones, log
│   └── infrastructure/
│       ├── http/             # endpoints (health ahora; chat en la Fase 3)
│       ├── persistence/      # PostgreSQL y Valkey
│       ├── llm/              # adaptadores del proveedor de IA (uno por proveedor)
│       └── tools/            # las 7 tools: argumentos, recortes y cliente HTTP (httpx)
├── mocks/                    # contenedor mock-plataforma (app.py, datos.py, Dockerfile)
└── tests/
    ├── unit/
    └── integration/
```

Las carpetas `llm/` y `tools/` son nuevas respecto a la plantilla; la plantilla trae `messaging/`, que se quitó porque este módulo no usa RabbitMQ. Desde la Fase 1, `domain/`, `application/ports/` y `persistence/` tienen código; además se agregó `db/` con el script SQL de la tabla y `src/config.py` con la configuración. En la Fase 2 se llenaron `tools/` y `mocks/`, y se agregó el puerto `application/ports/herramientas.py`.

---
[← Stack elegido](./03-stack.md) · [Dockerfile (explicado) →](./05-dockerfile.md)
