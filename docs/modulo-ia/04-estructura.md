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
│   ├── application/          # casos de uso (responder_mensaje, verificar_salud) e instrucciones del modelo
│   │   └── ports/            # interfaces: modelo de lenguaje, tools, sesiones, log
│   └── infrastructure/
│       ├── http/             # endpoints (health y chat) y formato común de errores
│       ├── persistence/      # PostgreSQL y Valkey
│       ├── llm/              # fabrica.py elige el adaptador del proveedor (Groq en la Fase 5)
│       └── tools/            # las 7 tools: argumentos, recortes y cliente HTTP (httpx)
├── mocks/                    # contenedor mock-plataforma (app.py, datos.py, Dockerfile)
└── tests/
    ├── unit/
    └── integration/
```

Las carpetas `llm/` y `tools/` son nuevas respecto a la plantilla; la plantilla trae `messaging/`, que se quitó porque este módulo no usa RabbitMQ. Desde la Fase 1, `domain/`, `application/ports/` y `persistence/` tienen código; además se agregó `db/` con el script SQL de la tabla y `src/config.py` con la configuración. En la Fase 2 se llenaron `tools/` y `mocks/`, y se agregó el puerto `application/ports/herramientas.py`. En la Fase 3 se agregaron el puerto `modelo_de_lenguaje.py`, el caso de uso `responder_mensaje.py`, el endpoint `http/chat.py` y los dobles de prueba `tests/fakes.py`. En la Fase 4, `domain/privacidad.py`, los puertos `limite_de_tasa.py` y `errores.py`, y el limitador `LimiteValkey`.

---
[← Stack elegido](./03-stack.md) · [Dockerfile (explicado) →](./05-dockerfile.md)
