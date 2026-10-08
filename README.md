# Plataforma Digital de Turismo — Santa Marta

Plataforma para la gestión integrada y sostenible del turismo en Santa Marta, construida con una arquitectura de microservicios 100% software libre.

**Curso:** Arquitectura de Software · Ingeniería de Sistemas — Universidad del Magdalena  
**Documentación:** [rama `Documents`](https://github.com/luifdo/tourism-platform/tree/Documents/Documents/Pages) (SRS, Plan de Desarrollo, Comparación de Alternativas Arquitectónicas y ADRs)

---

## Estructura del repositorio

Monorepo con servicios aislados: cada microservicio vive en su propia carpeta y se comporta como un proyecto independiente (código, dependencias, base de datos, Dockerfile y pruebas propios).

```
tourism-platform/
├── services/                      # un microservicio por carpeta
│   ├── iam-service/               # Módulo 1: Seguridad & IAM
│   ├── catalog-service/           # Módulo 2: Catálogo & GIS
│   ├── booking-service/           # Módulo 3: Reservas & Cupos
│   ├── review-service/            # Módulo 4: Reseñas & Moderación
│   ├── recommendation-service/    # Módulo 5: IA & Recomendación (Python)
│   └── analytics-service/         # Módulo 6: Analítica & Destino
├── gateway/                       # API Gateway (Nginx o Traefik)
├── frontend/                      # Interfaz web
├── contracts/                     # contratos REST (OpenAPI) y esquemas de eventos
├── infra/                         # docker-compose, PostgreSQL, RabbitMQ, observabilidad
├── templates/service-template/    # plantilla base para nuevos servicios
├── docs/                          # documentación técnica del código
└── .github/                       # CODEOWNERS, plantilla de PR y workflows
```

## Servicios y responsables

| Servicio | Módulo | Responsable | Persistencia | Puerto |
|---|---|---|---|---|
| [iam-service](./services/iam-service/) | 1: Seguridad & IAM | Juan Francisco Gonzalez (@JuanFranG) | PostgreSQL `iam_db` | 8001 |
| [catalog-service](./services/catalog-service/) | 2: Catálogo & GIS | Valentina Nieves (@nievesita) | PostgreSQL + PostGIS `catalog_db` | 8002 |
| [booking-service](./services/booking-service/) | 3: Reservas & Cupos | Andres Gamero (@AFGamero) | PostgreSQL `booking_db` | 8003 |
| [review-service](./services/review-service/) | 4: Reseñas & Moderación | Alvaro Ospino (@alvaroospino) | Documental (por definir) | 8004 |
| [recommendation-service](./services/recommendation-service/) | 5: IA & Recomendación | Luis Fernando Barraza (@luifdo) | Por definir | 8005 |
| [analytics-service](./services/analytics-service/) | 6: Analítica & Destino | Luis Fernando Barraza (@luifdo) | Por definir | 8006 |

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
| PostgreSQL | localhost:5432 (bases `iam_db`, `catalog_db`, `booking_db`) |
| Valkey | localhost:6379 |

## Flujo de trabajo

* `main`: código estable; solo recibe cambios por PR.
* `feature/<servicio>-<tarea>`: una rama por historia de usuario, por ejemplo `feature/booking-solicitar-reserva`.
* Sprints de 2 semanas con tablero en GitHub Projects (ver Plan de Desarrollo, §3).

## Decisiones pendientes

* Lenguaje de los servicios principales: Spring Boot o NestJS.
* API Gateway: Nginx o Traefik.
* Base documental de review-service: MongoDB Community o FerretDB.
* Almacén de recommendation-service y analytics-service.
