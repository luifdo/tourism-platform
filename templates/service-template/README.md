# service-template

**Módulo N: <Nombre>** · Responsable: <Integrante> (@usuario)

<Propósito del servicio>

| Aspecto | Valor |
|---|---|
| Casos de uso | <UCs> |
| Requerimientos funcionales | <RFs> |
| Requerimientos no funcionales | <RNFs> |
| Escenarios de calidad | <ESCs> |
| Persistencia | <Base de datos propia> |
| Lenguaje / framework | Python 3.12 + FastAPI |
| Puerto interno | `80XX` |
| Contrato REST | [`contracts/openapi/service-template.yaml`](../../contracts/openapi/) |

## Eventos

**Publica:**
* <eventos publicados>

**Consume:**
* <eventos consumidos>

Esquemas en [`contracts/events/`](../../contracts/events/).

## Estructura (arquitectura hexagonal)

```
src/
├── domain/              # entidades y reglas de negocio puras, sin dependencias de frameworks
├── application/         # casos de uso del servicio
│   └── ports/           # interfaces que el dominio necesita (repositorios, publicador de eventos)
└── infrastructure/      # adaptadores que implementan los puertos
    ├── http/            # controladores REST (implementan el contrato OpenAPI)
    ├── persistence/     # acceso a la base de datos propia del servicio
    └── messaging/       # publicación y consumo de eventos en RabbitMQ
tests/
├── unit/
└── integration/
```

## Ejecución

Pendiente (Fase 4): agregar `Dockerfile`, dependencias y comandos de ejecución y pruebas en Python + FastAPI.

```bash
# Desde infra/, una vez agregado el servicio al docker-compose:
docker compose up service-template
```

## Kubernetes

`k8s/` trae los manifiestos base (Deployment, Service, HPA, PodDisruptionBudget, NetworkPolicy y ConfigMap, Plan §7.2-7.4) y un overlay `local` para el Kubernetes de Docker Desktop. Al copiarlos, reemplaza `service-template` por el nombre del servicio y `8000` por su puerto, y ajusta réplicas y HPA según el Plan §7.3. La guía paso a paso (encender el clúster, desplegar, ver logs, actualizar) está en el [README de catalog-service](../../services/catalog-service/README.md#kubernetes-k8s).
