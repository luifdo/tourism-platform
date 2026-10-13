# recommendation-service

**Módulo 5: IA & Recomendación** · Responsable: Alvaro David Ospino Sanchez (@alvaroospino)

Chatbot turístico en español e inglés que consume la API de Gemini y consulta la plataforma solo mediante herramientas de solo lectura; entrega recomendaciones justificadas (RNF-08) y las registra en `recomendacion_log`. Ver la [Guía Técnica del Módulo 5](../../Documents/Pages/Guia_Tecnica_Modulo_IA.md).

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
├── domain/              # entidades y reglas de negocio puras, sin dependencias de frameworks
├── application/         # casos de uso del servicio (una clase por caso de uso)
│   └── ports/           # interfaces que el dominio necesita (repositorios, publicador de eventos)
└── infrastructure/      # adaptadores que implementan los puertos
    ├── http/            # routers FastAPI (implementan el contrato OpenAPI)
    ├── persistence/     # repositorios SQLAlchemy sobre la base de datos propia del servicio
    └── messaging/       # publicación y consumo de eventos en RabbitMQ (aio-pika)
tests/
├── unit/
└── integration/
```

## Ejecución

Servicio en Python 3.12 + FastAPI, empaquetado como contenedor y desplegado en Kubernetes (k3s) según el [Plan de Implementación](../../Documents/Pages/Plan_de_Implementacion.md) §7. El código, el `Dockerfile` y los manifiestos se agregan en la Fase 4.
