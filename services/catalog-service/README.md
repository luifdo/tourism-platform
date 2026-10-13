# catalog-service

**Módulo 2: Catálogo, GIS & Inteligencia de Destino** · Responsable: Luis Fernando Barraza Sanchez (@luifdo)

Catálogo de atractivos, actividades y perfiles de prestador; búsqueda multicriterio y geoespacial con PostGIS y OpenStreetMap; analítica de demanda y capacidad de carga a partir de eventos; tableros, reportes y alertas oficiales; correos transaccionales. Absorbe el antiguo Módulo 6 (Analítica & Destino).

| Aspecto | Valor |
|---|---|
| Casos de uso | UC7, UC8, UC9, UC16, UC17, UC18, UC22, UC23, UC24, UC25, UC26, UC36, UC38 |
| Requerimientos funcionales | RF-01, RF-02, RF-05, RF-07, RF-08, RF-11, RF-13 |
| Requerimientos no funcionales | RNF-01, RNF-02, RNF-03, RNF-06, RNF-13 |
| Escenarios de calidad | ESC-02, ESC-03, ESC-08, ESC-09 |
| Persistencia | PostgreSQL + PostGIS — base lógica `catalog_db`; caché en Valkey |
| Lenguaje / framework | Python 3.12 + FastAPI (orientado a objetos, arquitectura hexagonal) |
| Puerto interno | `8002` |
| Prefijo en el Gateway (Traefik) | `/api/catalog` |
| Réplicas en k3s | 2 (HPA hasta 6) |
| Contrato REST | [`contracts/openapi/catalog.yaml`](../../contracts/openapi/) |

## Eventos

**Publica:**
* `auditoria.registrada.v1`

**Consume:**
* `prestador.aprobado.v1` (crea el perfil del prestador)
* `reserva.solicitada.v1`, `reserva.confirmada.v1`, `reserva.rechazada.v1`, `reserva.cancelada.v1`, `reserva.finalizada.v1` (correos y demanda)
* `resena.publicada.v1` (calificación promedio y métricas)

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
