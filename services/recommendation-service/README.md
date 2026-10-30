# recommendation-service

**Módulo 5: IA & Recomendación** · Responsable: Alvaro David Ospino Sanchez (@alvaroospino)

Chatbot turístico en español e inglés que consume la API de Groq y consulta la plataforma solo mediante herramientas de solo lectura; entrega recomendaciones justificadas (RNF-08) y las registra en `recomendacion_log`. Ver la [Guía Técnica del Módulo 5](../../Documents/Pages/Guia_Tecnica_Modulo_IA.md).

| Aspecto | Valor |
|---|---|
| Casos de uso | UC14 |
| Requerimientos funcionales | RF-06 |
| Requerimientos no funcionales | RNF-05, RNF-08, RNF-12 |
| Escenarios de calidad | ESC-05 |
| Persistencia | PostgreSQL — base lógica `recommendation_db`; sesiones de chat en Valkey (TTL 24 h) |
| Lenguaje / framework | Python 3.12 + FastAPI (orientado a objetos, arquitectura hexagonal) |
| Puerto interno | `8005` |
| Prefijo en el Gateway (Traefik) | `/api/recommendations` |
| Réplicas en k3s | 1, siempre activa (HPA hasta 3) |
| Contrato REST | [`contracts/openapi/recommendation.yaml`](../../contracts/openapi/) |

## Eventos

**Publica:**
* —

**Consume:**
* — (no participa en el bus; consulta catalog, booking y review por REST)

Esquemas en [`contracts/events/`](../../contracts/events/).

## Estructura (arquitectura hexagonal)

```
src/
├── main.py              # composición: crea la app FastAPI e inyecta los adaptadores
├── config.py            # variables de entorno
├── domain/              # conversación, recomendación, privacidad y texto plano (sin frameworks)
├── application/         # caso de uso del chat, verificación de salud e instrucciones del modelo
│   └── ports/           # interfaces: modelo de lenguaje, tools, sesiones, registro, límite
└── infrastructure/      # adaptadores que implementan los puertos
    ├── http/            # endpoints (chat, health) y formato común de errores
    ├── persistence/     # PostgreSQL (recomendacion_log) y Valkey (sesiones y límite)
    ├── llm/             # adaptador de Groq y fábrica que elige el proveedor
    └── tools/           # las 7 tools: argumentos, recortes y cliente HTTP hacia catalog, booking y review
db/                      # script SQL de la tabla recomendacion_log
mocks/                   # mock-plataforma: simula catalog, booking y review en local
tests/
├── unit/
└── integration/         # PostgreSQL, Valkey y el mock reales; las de Groq real solo con `-m groq`
```

No usa RabbitMQ: obtiene los datos bajo demanda con sus tools.

## Ejecución

Servicio en Python 3.12 + FastAPI, empaquetado como contenedor y desplegado en Kubernetes (k3s) según el [Plan de Implementación](../../Documents/Pages/Plan_de_Implementacion.md) §7.

Cómo levantarlo, llamar al chat, manejar los errores e integrarlo con el frontend y el gateway: **[Guía de uso](../../docs/modulo-ia/guia-de-uso.md)**. En resumen:

```bash
cp .env.example .env          # y poner LLM_API_KEY (clave de Groq)
docker compose up --build -d  # servicio, PostgreSQL, Valkey y mock de la plataforma
curl localhost:8005/health
```
