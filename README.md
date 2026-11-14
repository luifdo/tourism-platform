# Plataforma Digital de Turismo — Santa Marta

Plataforma para la gestión integrada y sostenible del turismo en Santa Marta, construida con una arquitectura de 5 microservicios en Python + FastAPI, desplegados como contenedores en Kubernetes (k3s) y priorizando el software libre (la API de Gemini del chatbot es la única dependencia propietaria).

**Curso:** Arquitectura de Software · Ingeniería de Sistemas — Universidad del Magdalena  
**Documentación:** [`Documents/Pages`](./Documents/Pages/README.md) (SRS, Comparación de Alternativas Arquitectónicas, Registro de Decisiones Arquitectónicas y Plan de Implementación)

---

## Estructura del repositorio

Monorepo con servicios aislados: cada microservicio vive en su propia carpeta y se comporta como un proyecto independiente (código, dependencias, base de datos, Dockerfile y pruebas propios).

```
tourism-platform/
├── services/                      # un microservicio por carpeta
│   ├── iam-service/               # Módulo 1: Seguridad & IAM
│   ├── catalog-service/           # Módulo 2: Catálogo, GIS & Inteligencia de Destino
│   ├── booking-service/           # Módulo 3: Reservas & Cupos
│   ├── review-service/            # Módulo 4: Reseñas & Moderación
│   └── recommendation-service/    # Módulo 5: IA & Recomendación (chatbot con Gemini)
├── gateway/                       # API Gateway (Traefik)
├── frontend/                      # Interfaz web (PWA)
├── contracts/                     # contratos REST (OpenAPI) y esquemas de eventos
├── infra/                         # docker-compose, PostgreSQL, RabbitMQ, observabilidad
├── templates/service-template/    # plantilla base para nuevos servicios
├── Documents/Pages/               # documentación del proyecto (SRS, ADR, Plan)
├── docs/                          # documentación técnica del código
└── .github/                       # CODEOWNERS, plantilla de PR y workflows
```

## Servicios y responsables

Responsables según el [SRS, Apéndice C](./Documents/Pages/Requirements_docIEEE.md#apéndice-c-equipo-de-trabajo-y-asignación-de-roles). Todos los servicios usan Python 3.12 + FastAPI.

| Servicio | Módulo | Responsable | Persistencia | Puerto |
|---|---|---|---|---|
| [iam-service](./services/iam-service/) | 1: Seguridad & IAM | Valentina Nieves (@nievesita) | PostgreSQL `iam_db` | 8001 |
| [catalog-service](./services/catalog-service/) | 2: Catálogo, GIS & Inteligencia de Destino | Luis Fernando Barraza (@luifdo) | PostgreSQL + PostGIS `catalog_db` | 8002 |
| [booking-service](./services/booking-service/) | 3: Reservas & Cupos | Andres Gamero (@AFGamero) | PostgreSQL `booking_db` | 8003 |
| [review-service](./services/review-service/) | 4: Reseñas & Moderación | Luis Fernando Barraza (@luifdo) | PostgreSQL JSONB `review_db` | 8004 |
| [recommendation-service](./services/recommendation-service/) | 5: IA & Recomendación | Alvaro Ospino (@alvaroospino) | PostgreSQL `recommendation_db` + Valkey | 8005 |

| Componente | Responsable |
|---|---|
| `frontend/` (PWA) y `gateway/` (Traefik) | Juan Francisco Gonzalez (@JuanFranG) |
| `contracts/` e `infra/` | Luis Fernando Barraza (@luifdo), arquitecto |
| `templates/` | Alvaro Ospino (@alvaroospino), desarrollador principal |

## Reglas de independencia

1. **Ningún servicio importa código de otro.** Se comunican solo por REST, a través del Gateway, o por eventos en RabbitMQ.
2. **Cada servicio tiene su propia base de datos** y ninguno consulta la de otro.
3. **Los contratos se definen antes que el código** en [`contracts/`](./contracts/) y se versionan.
4. **No hay librerías compartidas.** El código común (validación de JWT, logs) se copia desde [`templates/`](./templates/service-template/).
5. **Cada servicio se puede levantar por separado** con `docker compose up <servicio>`.
6. **Cada carpeta tiene un responsable** que revisa sus PRs ([`CODEOWNERS`](./.github/CODEOWNERS)).

## Entorno local

Requisitos: Docker y Docker Compose.

```bash
cd infra
cp .env.example .env
docker compose up -d
```

| Componente | URL local |
|---|---|
| RabbitMQ (consola) | http://localhost:15672 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |
| PostgreSQL | localhost:5432 (bases `iam_db`, `catalog_db`, `booking_db`, `review_db`, `recommendation_db`) |
| Valkey | localhost:6379 |

## Flujo de trabajo

Se sigue Git Flow:

* `main`: versiones entregadas; solo recibe cambios por PR desde una rama `release/*`.
* `develop`: rama por defecto y de integración.
* `feature/<servicio>-<tarea>`: una rama por historia de usuario, creada desde `develop` y fusionada a `develop` por PR, por ejemplo `feature/booking-solicitar-reserva`.
* `release/*`: una rama por entrega; al fusionarse a `main` se marca con su tag `vX.Y`.
* `hotfix/*`: correcciones urgentes creadas desde `main`.
* Sprints de 2 semanas con tablero en GitHub Projects (ver Plan de Desarrollo, §3).

## Decisiones tomadas

Ver el [Registro de Decisiones Arquitectónicas](./Documents/Pages/Registro_Decisiones_Arquitectonicas.md):

* Lenguaje: Python 3.12 + FastAPI en los 5 servicios (ADR-006).
* Despliegue: contenedores en Kubernetes (k3s); Docker Compose solo para desarrollo local (ADR-005).
* API Gateway: Traefik (ADR-007).
* Reseñas: PostgreSQL con JSONB en lugar de MongoDB (ADR-003).
* Conectividad limitada: PWA con catálogo sin conexión y formularios diferidos (ADR-004).
