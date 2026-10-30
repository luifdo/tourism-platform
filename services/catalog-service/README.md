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
| Coordinación con otros módulos | [`Coordinacion_Modulo_Catalogo.md`](./Coordinacion_Modulo_Catalogo.md): qué espera el catálogo de cada módulo y qué les ofrece |

## Eventos

**Publica:**
* `servicio.publicado.v1` (dueño y aforo para booking-service)
* `auditoria.registrada.v1`

**Consume:**
* `prestador.aprobado.v1` (crea o reactiva el perfil del prestador)
* `prestador.suspendido.v1` (desactiva el perfil y sus servicios)
* `reserva.solicitada.v1`, `reserva.modificada.v1`, `reserva.confirmada.v1`, `reserva.rechazada.v1`, `reserva.cancelada.v1`, `reserva.finalizada.v1` (correos y demanda)
* `resena.publicada.v1` (calificación promedio y métricas)
* `resena.ocultada.v1` (quita del promedio la reseña ocultada por moderación)
* `disponibilidad.actualizada.v1` (cupos por servicio y día, para filtrar por fecha y personas)

Esquemas en [`contracts/events/`](../../contracts/events/).

## Integración con otros módulos

Estado comprobado el 2026-10-30 con `infra/docker-compose.yml` (arranque desde volúmenes vacíos y flujo de punta a punta, con la identidad enviada a mano porque aún no hay Traefik). ✅ conectado y probado · ⏳ pendiente.

Detalle de cada pedido en [`Coordinacion_Modulo_Catalogo.md`](./Coordinacion_Modulo_Catalogo.md).

| Necesita | De | Para qué | Estado |
|---|---|---|---|
| `prestador.aprobado` con `razon_social` | iam | Crear o reactivar el perfil y habilitar UC17 | ✅ |
| `prestador.suspendido` | iam | Ocultar el perfil y sus servicios | ✅ también se restauran al rehabilitarlo |
| `GET /internal/usuarios/{id}/contacto` | iam | Destinatario de los correos | ✅ envía `X-Correlation-ID` y un 404 no se reintenta |
| Cola `iam.auditoria` | iam | Que no se pierda `auditoria.registrada` | ✅ |
| `reserva.*` (los seis) | booking | Demanda y correos | ✅ |
| `disponibilidad.actualizada` | booking | Cupos en búsqueda y mapa | ✅ |
| `resena.publicada` y `resena.ocultada` | review | Promedio del servicio | ✅ coincide con el de review |
| Rutas, ForwardAuth y borrado de `X-Usuario-*` | Traefik (Juan Francisco) | Exponer `/api/catalog` e identidad | ⏳ `gateway/config` no existe; sin él no hay acceso desde fuera del clúster |
| Consumir la API real | PWA (Juan Francisco) | Mostrar el catálogo | ⏳ `useCatalog` carga `/buscar`, pero la vista espera los datos de ejemplo (`km`, `zone`, `items.<id>.name`) |
| Señal de supresión de datos de un prestador | iam | Borrar `razon_social`, `telefono` y `direccion` (Ley 1581, C-27) | ⏳ falta acordar el evento |

| Ofrece | A | Estado |
|---|---|---|
| `servicio.publicado` | booking y review | ✅ |
| Búsqueda, ficha, alertas y capacidad | recommendation | ✅ las tools leen los datos reales |

**Limitación conocida:** lo que catalog publique antes de que existan las colas de booking y review se pierde para ellos. No hay todavía un comando para volver a publicar los servicios existentes.

## Estructura (arquitectura hexagonal)

Solo `app/` tiene `__init__.py`; las subcarpetas son paquetes de espacio de nombres (PEP 420). Cada carpeta se crea en el paso que la implementa, así que algunas de este árbol todavía no existen.

```
app/
├── __init__.py
├── main.py              # composición: crea la app FastAPI, el engine y /metrics
├── config.py            # Settings (pydantic-settings) leídos de variables de entorno / .env
├── domain/              # núcleo puro, sin dependencias de frameworks
│   ├── entities/
│   ├── value_objects/
│   └── ports/           # interfaces (Protocols) que implementa la infraestructura
├── application/
│   └── use_cases/       # una clase por caso de uso
├── infrastructure/      # adaptadores que implementan los puertos
│   ├── persistence/     # SQLAlchemy async + GeoAlchemy2 sobre catalog_db (PostGIS)
│   ├── cache/           # Valkey (búsquedas, idempotencia de formularios)
│   ├── messaging/       # RabbitMQ (outbox, publicador y consumidores)
│   ├── notifications/   # correo SMTP
│   ├── storage/         # S3 (SeaweedFS, imágenes del catálogo)
│   └── clients/         # HTTP hacia booking, iam y Nominatim
└── api/                 # adaptador HTTP
    ├── routers/
    ├── schemas/         # modelos Pydantic de request/response
    └── dependencies.py  # cableado de casos de uso con sus adaptadores
migrations/              # Alembic (async)
tests/
```

## Ejecución

Requiere [uv](https://docs.astral.sh/uv/) y Python 3.12 (`uv python install 3.12`).

```bash
docker compose -f docker-compose.dev.yml up -d   # PostGIS, Valkey, RabbitMQ y SeaweedFS
uv sync                                          # instala dependencias (incluye dev)
cp .env.example .env
uv run alembic upgrade head                      # aplicar migraciones (incluye las zonas iniciales)
uv run uvicorn app.main:app --reload --port 8002
uv run python -m app.worker                      # worker: relay del outbox, 5 consumidores, correos y limpieza diaria (métricas en :9102)
# Correos de desarrollo: Mailpit (docker-compose.dev.yml) en http://localhost:8026
uv run pytest                                    # unitarias + integración (PostGIS en testcontainers)
uv run pytest -m "not integration"               # solo unitarias, sin Docker
uv run ruff check . && uv run ruff format --check .
```

Los puertos de `docker-compose.dev.yml` (5434, 6380, 5673, 15673 y 8333) no chocan con los de iam-service, así que ambos entornos pueden correr a la vez. Las pruebas de integración levantan su propio PostGIS efímero y no tocan la base de desarrollo; sin Docker se omiten.

Las zonas iniciales (migración `0002`) son rectángulos **aproximados** que no se superponen; la Entidad los corrige desde la API. Si dos zonas cubren un mismo punto, el servicio queda en la de menor área.

## Pruebas

| Capa | Qué comprueba | Dónde |
|---|---|---|
| Unitarias | Dominio, casos de uso y API con los puertos simulados | `tests/unit/` (`uv run pytest -m "not integration"`, sin Docker) |
| Integración | Consultas espaciales, caché, consumidores, idempotencia, outbox y cada endpoint de punta a punta con PostgreSQL+PostGIS, Valkey, RabbitMQ y Mailpit reales (testcontainers) | `tests/integration/` |
| Contrato REST | **Toda** respuesta que recibe cualquier prueba se valida contra [`catalog.yaml`](../../contracts/openapi/catalog.yaml): código documentado, tipo de contenido y cuerpo según su esquema. Una prueba que se sale del contrato a propósito (un 500 provocado) lleva `@pytest.mark.sin_contrato` | `tests/conftest.py` |
| Contrato REST (fuzzing) | Schemathesis genera cientos de peticiones válidas e inválidas por operación desde el contrato, como Entidad y como Prestador, contra la app con la base real: nunca un 500, solo respuestas documentadas | `tests/integration/test_contrato_schemathesis.py` |
| Contrato de eventos | Cada evento que las pruebas publican (como lo haría booking, iam o review) y cada fila que el servicio deja en el outbox se valida contra `envelope.v1` y su esquema en [`contracts/events/`](../../contracts/events/). Un evento roto a propósito (prueba de la DLQ) se publica con `segun_contrato=False` | `tests/conftest.py`, `tests/integration/conftest.py` |
| Carga (k6) | ESC-02 y ESC-08 | [`k6/`](./k6/README.md) |

`tests/unit/test_pruebas_de_contrato.py` comprueba que los validadores **sí** detectan errores (un cuerpo que no cumple, una operación que no existe, un payload con un tipo equivocado): sin eso, un validador mal conectado dejaría pasar todo en silencio.

Si cambias el contrato, corre la suite: lo que la API devuelva distinto aparece como fallo con la ruta del campo (`items.0.zona: None is not of type 'object'`).

## Despliegue

### Con el compose del monorepo

`infra/docker-compose.yml` levanta la infraestructura compartida y el servicio en contenedores: `catalog-migraciones` aplica las migraciones una vez y termina, y luego arrancan `catalog-service` (API en :8002) y `catalog-worker` (métricas en :9102). Prometheus (http://localhost:9090) ya los tiene como objetivos.

```bash
cd infra
cp .env.example .env
docker compose up -d --build
```

Usa los puertos estándar (5432, 6379, 5672, 8333, 1025/8025 de Mailpit), así que **no** corre a la vez que `docker-compose.dev.yml` (los dos usan el 8333): detén uno antes de levantar el otro (`docker compose -f docker-compose.dev.yml stop`).

### Kubernetes (`k8s/`)

Manifiestos con Kustomize (Plan §7.2-7.4), basados en [`templates/service-template/k8s/`](../../templates/service-template/k8s/):

| Archivo (`k8s/base/`) | Qué es |
|---|---|
| `deployment-api.yaml` | API: 2 réplicas, `RollingUpdate` sin indisponibilidad, *startup* hasta 90 s, *readiness* `/health` cada 2 s, *liveness* `/metrics` (no toca la base: si PostgreSQL cae, las réplicas salen del tráfico pero no se reinician todas). Un `initContainer` aplica las migraciones; el candado `pg_advisory_xact_lock` de `migrations/env.py` hace que varios pods que arrancan a la vez esperen al primero. |
| `deployment-worker.yaml` | Worker: 1 réplica, sin HPA. Se puede subir a 2 sin duplicar publicaciones (SKIP LOCKED en el relay, consumidores idempotentes). |
| `hpa.yaml` | De 2 a 6 réplicas de la API con objetivo de CPU del 70 %. |
| `pdb.yaml` | Al drenar un nodo queda al menos una réplica de la API. |
| `networkpolicy.yaml` | A la API solo entran Traefik, recommendation-service y Prometheus; al worker, solo Prometheus. |
| `service.yaml`, `configmap.yaml` | Service ClusterIP en el 8002 y la configuración no secreta. |

Las credenciales van en el Secret `catalog-secretos`, que **cada entorno** genera desde un `secretos.env` que no se sube al repositorio (`overlays/local/secretos.env.example` lista las claves). Los contenedores corren sin root, con el sistema de archivos de solo lectura (más `/tmp` en memoria) y sin *capabilities*.

> **Migraciones compatibles hacia atrás:** durante un rolling update los pods viejos siguen atendiendo con la base ya migrada. Primero se agrega (columna nueva con valor por defecto), en otro despliegue se quita lo viejo.

#### Probarlo en el Kubernetes de Docker Desktop (`k8s/overlays/local/`)

El overlay `local` usa la imagen construida en tu Docker y la infraestructura del compose del monorepo, a la que los pods llegan por `host.docker.internal`.

**1. Encender Kubernetes (una sola vez).** Docker Desktop → ⚙️ *Settings* → *Kubernetes* → *Enable Kubernetes* (tipo **kubeadm**) → *Apply & restart*. Queda listo cuando el ícono de Kubernetes, abajo a la izquierda, se pone verde. Para apagarlo, desmarca la misma casilla (libera unos 2 GB de RAM).

**2. Conectarse.** `kubectl` habla con el clúster del *contexto* activo:

```bash
kubectl config get-contexts               # el activo tiene *; Docker Desktop crea "docker-desktop"
kubectl config use-context docker-desktop # elegirlo (si tienes otros clústeres)
kubectl get nodes                         # debe mostrar el nodo "docker-desktop" en Ready
```

**3. Medidor de CPU para el HPA (una sola vez).** El HPA necesita `metrics-server`. Las versiones recientes de Docker Desktop ya lo traen: prueba primero `kubectl top nodes`; si muestra CPU y memoria, salta este paso. Si da error, instálalo:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.7.2/components.yaml
kubectl -n kube-system patch deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl top nodes                         # al minuto muestra CPU y memoria
```

**4. Desplegar.** Con la infraestructura del compose arriba (`cd infra && docker compose up -d postgres valkey rabbitmq seaweedfs seaweedfs-init mailpit`):

```bash
cd services/catalog-service
docker build -t catalog-service:local .                  # el clúster usa esta imagen directamente
cp k8s/overlays/local/secretos.env.example k8s/overlays/local/secretos.env
kubectl apply -k k8s/overlays/local                      # crea o actualiza todo
kubectl -n turismo-app rollout status deployment/catalog-service
```

Si el compose también tiene `catalog-service` y `catalog-worker` corriendo, detenlos (`docker compose stop catalog-service catalog-worker`): si no, dos workers consumen las mismas colas y el 8002 queda ocupado.

**5. Usarlo.** El Service es interno al clúster; para llegar desde tu máquina se abre un túnel (queda abierto mientras la terminal siga corriendo, Ctrl+C lo cierra):

```bash
kubectl -n turismo-app port-forward service/catalog-service 8002:8002
curl http://localhost:8002/health                        # en otra terminal
```

**6. Mirar qué pasa.**

| Para… | Comando (`-n turismo-app` en todos) |
|---|---|
| Ver todo | `kubectl -n turismo-app get pods,deploy,svc,hpa` |
| Logs de la API (todas las réplicas) | `kubectl -n turismo-app logs -l app.kubernetes.io/component=api -f` |
| Logs del worker | `kubectl -n turismo-app logs deploy/catalog-worker -f` |
| Logs de las migraciones de un pod | `kubectl -n turismo-app logs <pod> -c migraciones` |
| Por qué un pod no arranca | `kubectl -n turismo-app describe pod <pod>` (mira *Events* al final) |
| Eventos recientes | `kubectl -n turismo-app get events --sort-by=.lastTimestamp` |
| Consumo de CPU y memoria | `kubectl -n turismo-app top pods` |
| Estado del HPA | `kubectl -n turismo-app get hpa -w` |
| Entrar a un pod | `kubectl -n turismo-app exec -it deploy/catalog-service -- sh` |

**7. Cambiar cosas.**

| Para… | Comando |
|---|---|
| Desplegar código nuevo | `docker build -t catalog-service:local .` y `kubectl -n turismo-app rollout restart deployment/catalog-service deployment/catalog-worker` |
| Aplicar cambios de los YAML o de `secretos.env` | `kubectl apply -k k8s/overlays/local` (si cambió el Secret, los pods se recrean solos: su nombre lleva un hash) |
| Escalar a mano el worker | `kubectl -n turismo-app scale deployment/catalog-worker --replicas=2` |
| Volver a la versión anterior | `kubectl -n turismo-app rollout undo deployment/catalog-service` |
| Ver lo que se aplicaría, sin aplicarlo | `kubectl kustomize k8s/overlays/local` o `kubectl diff -k k8s/overlays/local` |
| Borrar todo el servicio | `kubectl delete -k k8s/overlays/local` (borra también el namespace `turismo-app`) |

**Problemas comunes.**

* `ErrImageNeverPull` / `ImagePullBackOff`: no construiste `catalog-service:local`, o el clúster es de tipo *kind* (en ese caso: `kind load docker-image catalog-service:local --name desktop`).
* `Init:CrashLoopBackOff`: fallaron las migraciones; casi siempre la base no responde. Mira `logs <pod> -c migraciones` y que el compose tenga `postgres` arriba.
* `0/1 Running` sin pasar a `1/1`: la *readiness* (`/health`) falla; revisa `DATABASE_URL` en `secretos.env`.
* El HPA en `<unknown>`: es normal el primer minuto tras desplegar o sin tráfico; si sigue así con carga, falta el paso 3 (`metrics-server`).
* Docker Desktop queda "verde" pero `docker ps` responde `500 Internal Server Error` y `kubectl` da `TLS handshake timeout` (pasa a veces al activar Kubernetes): ciérralo del todo (clic derecho en el ícono → *Quit Docker Desktop*), en PowerShell ejecuta `wsl --shutdown` y vuelve a abrirlo. No se pierden imágenes, volúmenes ni el clúster.
* Todo va lento o los pods tardan mucho en arrancar: la máquina virtual de Docker tiene poca RAM para el clúster más el compose. Apaga lo que no uses o dale más memoria en *Settings → Resources* (con el backend WSL, en `%UserProfile%\.wslconfig`).

**Qué se comprobó en local (2026-10-24):** rolling update con peticiones continuas sin un solo fallo (340/340); con PostgreSQL caído 40 s las réplicas salen del tráfico (`0/1`) sin reiniciarse y vuelven solas; con carga el HPA pasó de 2 a 6 réplicas en unos 100 s. La app tarda entre 10 y 20 s en importar (FastAPI, SQLAlchemy, GeoAlchemy2, boto3); por eso hay `startupProbe` (hasta 90 s) y el límite de CPU es de 1 núcleo (el *request*, que es lo que reserva y lo que mide el HPA, sigue en 100m).

En el clúster k3s real cambian tres cosas: la imagen sale de GHCR (`images` de `k8s/base/kustomization.yaml`), la infraestructura vive en el namespace `turismo-datos` (`infra/k8s/`) y el tráfico entra por Traefik. Docker Desktop no aplica las NetworkPolicy (su red no las soporta); k3s sí.

## Endpoints implementados

El servicio atiende bajo `/api/catalog` (el mismo prefijo del Gateway) y `/health` y `/metrics` en la raíz, como define el contrato. Detalle en [`catalog.yaml`](../../contracts/openapi/catalog.yaml); una prueba verifica que toda ruta implementada esté en el contrato.

| Ruta | Caso de uso | Notas |
|---|---|---|
| `GET /api/catalog/servicios` | UC7 | Pública, paginada |
| `GET /api/catalog/servicios/{id}` | UC9 | Pública; incluye alertas vigentes del servicio y de su zona, `atributos` en el idioma pedido con sus `etiquetas`, `aviso_pagos` y `regla_base_cancelacion` (la regla que aplica booking, junto a la política informativa del prestador; texto en `app/api/i18n/textos_plataforma.py`) |
| `GET /api/catalog/buscar` | UC8 | Pública; texto, categorías, tipos, zona, precio y su unidad, cercanía en metros, filtros de atributos y `fecha`/`personas` (ver abajo); caché de 300 s en Valkey, salvo con `fecha` |
| `GET /api/catalog/zonas` | Filtros | Pública |
| `GET /api/catalog/alertas` | UC26 | Pública; vigentes, de mayor a menor nivel |
| `POST /api/catalog/alertas` | UC26 | Entidad o Admin; sobre un servicio **o** una zona (activos, si no 404); expiración futura y como máximo a 365 días, con zona horaria; audita `ALERTA_PUBLICADA` |
| `PUT /api/catalog/alertas/{id}` | UC26 | Entidad o Admin; cambia nivel, mensaje o vigencia (el destino no); `If-Match`; una retirada no se edita (`ALERTA_RETIRADA` 409); audita `ALERTA_EDITADA` |
| `POST /api/catalog/alertas/{id}/desactivar` | UC26 | Entidad o Admin; la retira (no se borra); repetir no cambia nada ni se audita; audita `ALERTA_RETIRADA` |
| `GET /api/catalog/prestador/metricas` | UC22 | Prestador (también suspendido); por servicio y por fecha de la visita: reservas por estado actual, personas atendidas, ocupación (personas ÷ aforo × días, sin tope), calificación de siempre (reseñas visibles) e intenciones de visita |
| `GET /api/catalog/analitica/demanda` | UC23 | Entidad y Admin; serie por `dia`, `semana` (desde el lunes) o `mes` de personas solicitadas, confirmadas, finalizadas y canceladas (+ rechazadas), por fecha de la visita y estado actual; periodos vacíos en 0; `zona` y `categoria` opcionales |
| `GET /api/catalog/analitica/tablero` | UC25 | Entidad y Admin; totales del rango, capacidad de hoy por zona, las 5 zonas con más personas (reservas no canceladas) con sus intenciones y las alertas vigentes |
| `GET /api/catalog/analitica/reportes/demanda` | UC38 | Entidad y Admin; CSV **en español** para Excel (`;`, coma decimal, UTF-8 con BOM), en streaming: una fila por servicio y día con actividad, con personas solicitadas, confirmadas, finalizadas, canceladas, total de personas, capacidad recomendada, índice e intenciones de visita. Audita `EXPORT` (usuario y filtros) antes de entregarlo; textos que empiezan por `=`, `+`, `-` o `@` llevan un apóstrofo (sin inyección de fórmulas). PDF: más adelante (RF-13 es *Could*) |
| `GET /api/catalog/analitica/capacidad` | UC24 | Entidad, Admin y Turista (este solo ve zona, fecha y nivel); índice por zona de un día (hoy por defecto) sobre la capacidad **recomendada** (no es un tope: puede pasar de 1), servicios con bandera ≥ 0,85, ordenado de mayor a menor; se calcula al consultar con caché de 5 min (`calculado_en`) |
| `GET /api/catalog/analitica/mapa-calor` | RF-07 | Entidad y Admin; polígonos de las zonas con su índice y nivel (GeoJSON) |
| `POST /api/catalog/servicios/{id}/intencion-visita` | Mapa | Pública; la PWA la llama en "Cómo llegar". Cuenta una vez por visitante, servicio y día: en Valkey solo queda un HMAC del IP con sal diaria (derivada de `INTENCION_VISITA_SECRETO` y la fecha), durante 24 h; en la base, solo el conteo por servicio y día (migración 0009). Si Valkey no responde, cuenta igual. Servicio apagado o inexistente: 404 sin contar. No entra en la saturación |
| `GET /api/catalog/analitica/intenciones-visita` | Analítica | Entidad y Admin; conteos por zona (la actual de cada servicio) y día, `desde`/`hasta` (hasta 366 días) y `zona` opcional |
| `GET /api/catalog/entidad/alertas` | UC26 | Entidad o Admin; panel con todas las alertas o las de un `estado` (`VIGENTE`, `VENCIDA`, `RETIRADA`), recientes primero, con mensaje en ambos idiomas y versión |
| `GET /api/catalog/mapa/servicios` | UC16 | Pública; GeoJSON recortado a `bbox`; mismos filtros de tipo y atributos que `/buscar`; con zoom < 13 agrupa en el servidor (caché de 300 s) |
| `GET /api/catalog/mapa/zonas` | UC16 | Pública; polígonos simplificados según el zoom |
| `GET /api/catalog/mapa/alertas` | UC16, UC26 | Pública; puntos (alertas de servicio) y polígonos (de zona) |
| `POST /api/catalog/servicios` | UC17 | Prestador activo; `tipo`, `unidad_tarifa` y `atributos` por tipo (ver abajo); `Idempotency-Key`; publica `servicio.publicado` (outbox) |
| `PUT /api/catalog/servicios/{id}` | UC18 | Dueño; `If-Match` e `Idempotency-Key` |
| `POST /api/catalog/servicios/{id}/desactivar`, `/reactivar` | UC18 | Dueño; `If-Match`; repetir no publica nada |
| `GET /api/catalog/prestador/servicios` | UC18 | Sus servicios, inactivos incluidos, en ambos idiomas |
| `GET`, `PUT /api/catalog/prestador/perfil` | UC4 | Teléfono, dirección y política de cancelación; `If-Match` |
| `POST /api/catalog/prestador/imagenes` | UC17 | URL firmada de SeaweedFS (JPEG/PNG/WebP, 5 MB, 10 min) |
| `GET /api/catalog/geocodificar` | UC17 | Rol Prestador; Nominatim con caché de 7 días y 1 petición/s entre réplicas |
| `POST /api/catalog/zonas` | Zonas | Entidad o Admin; reasigna los servicios que cubre; `CODIGO_EXISTENTE` 409. Crear, editar y desactivar guardan `auditoria.registrada` en el outbox |
| `GET`, `PUT /api/catalog/zonas/{id}` | Zonas | Entidad o Admin; polígono completo y textos es/en; `If-Match`; si cambia el polígono reasigna los servicios |
| `POST /api/catalog/zonas/{id}/desactivar` | Zonas | Entidad o Admin; `If-Match`; con alertas vigentes `ZONA_EN_USO` 409; sus servicios pasan a otra zona o quedan sin zona |
| `GET /health` | RNF-01 | `200` si PostgreSQL responde, `503` si no. Valkey y RabbitMQ no se revisan: sin caché la búsqueda sigue y los eventos esperan en el outbox (ESC-01) |
| `GET /metrics` | RNF-12 | Prometheus |

## Idioma (español e inglés)

El sistema funciona completo en ambos idiomas según `Accept-Language` (español por defecto) y lo informa en `Content-Language`:

* **Textos del sistema** (mensajes de error y etiquetas de categorías y niveles): catálogo en [`app/api/i18n/`](./app/api/i18n/). Una prueba falla si una regla de validación, un error o un valor fijo no tiene texto en los dos idiomas.
* **Textos de usuarios** (nombres, descripciones, alertas, zonas): se guardan como `{"es": ..., "en": ...}`; si falta el inglés se muestra el español. La búsqueda de texto usa el diccionario del idioma pedido (`spanish` / `english`) sin tildes.

## Mapa (OpenStreetMap)

Las capas salen en GeoJSON (RFC 7946, `application/geo+json`), siempre en `[lon, lat]`, listas para `L.geoJSON` de Leaflet sobre teselas de OSM. El zoom define la escala: un píxel equivale a `360 / (256·2^zoom)` grados ([`escala_mapa.py`](./app/application/dto/escala_mapa.py)).

* **Servicios:** con zoom < 13 se agrupan en celdas de unos 64 px y la vista se amplía al borde de las celdas, para que los grupos no cambien al mover el mapa y vistas cercanas compartan caché. Desde zoom 13 llegan uno a uno (hasta 1000). El recorte usa un índice GIST en `geometry` (migración `0003`), exacto en grados.
* **Zonas:** se simplifican con tolerancia de un píxel (`ST_SimplifyPreserveTopology`); nunca se cruzan ni desaparecen.
* **Alertas:** no se cachean. La búsqueda y el mapa comparten la generación de caché (`catalog:gen`): un cambio del catálogo invalida ambos.

## Escritura del prestador

* **Identidad:** `X-Usuario-Id` y `X-Usuario-Rol`, que pone Traefik tras validar el JWT. Sin ellas, `401 NO_AUTENTICADO`; otro rol, `403 ROL_NO_PERMITIDO`. El perfil existe cuando iam aprueba al prestador (`prestador.aprobado`); antes, o si está suspendido, `403 PERFIL_INACTIVO`. Un suspendido puede leer su perfil y sus servicios, pero no escribir.
* **Concurrencia:** cada respuesta trae `ETag: "n"` y cada edición exige `If-Match` (sin él, `428`; con una versión vieja, `409` con el `ETag` actual).
* **Formularios sin conexión:** con `Idempotency-Key` un reenvío devuelve la misma respuesta (`Idempotent-Replayed: true`) sin repetir la operación, durante 48 h. La clave vale por usuario y operación (`idem:catalog:{usuario}:{método}:{ruta}:{clave}` en Valkey).
* **Eventos:** el cambio y `servicio.publicado` se guardan en la misma transacción (tabla `outbox`); el worker los publica en RabbitMQ (ver *Worker y mensajería*). Tras confirmar se invalida la caché de búsqueda y mapa.
* **Bloqueos:** toda escritura bloquea primero el perfil y luego el servicio (`SELECT ... FOR UPDATE`), siempre en ese orden. El panel lee sin bloquear.
* **Imágenes:** la PWA sube directo a SeaweedFS con una URL firmada que incluye el tipo y el tamaño; cada imagen queda en `{prestador_id}/{uuid}.{ext}` y un servicio solo acepta imágenes de la carpeta de su prestador. `docker-compose.dev.yml` levanta SeaweedFS en el puerto 8333 y crea el bucket.

## Tipos de servicio y atributos

Cada oferta tiene un **`tipo`** (21 tipos, ver `TipoServicio` en el [contrato](../../contracts/openapi/catalog.yaml)) que define su categoría y qué datos pide el formulario. La categoría ya no se envía: sale del tipo. Se suma la categoría **`TRANSPORTE`** (lanchas y traslados).

* **Ofertas combinadas:** cada cosa que se reserva por separado es un servicio distinto. Un hostal con tour y restaurante registra tres servicios, cada uno con su tarifa, aforo, reservas y reseñas. Lo que viene incluido y no se reserva aparte (desayuno, guía, transporte) es un atributo.
* **`unidad_tarifa`** acompaña a `tarifa_base`: `POR_PERSONA`, `POR_NOCHE`, `POR_GRUPO`, `POR_UNIDAD`, `POR_HORA` o `POR_DIA`.
* **`atributos`** (columna JSONB, migración `0004`) agrupa lo propio de cada tipo en bloques. Cada tipo exige su bloque principal y rechaza los que no le corresponden (`400 bloque_obligatorio` / `bloque_no_permitido`):

| Bloque | Para | Contenido |
|---|---|---|
| `comunes` | Todos | Horario, idiomas de atención, qué incluye y qué no, accesibilidad, mascotas, apto para niños, prácticas y certificación sostenibles |
| `alojamiento` | Hotel, hostal, posada, glamping, apartamento | Check-in y check-out, habitaciones por tipo y capacidad, amenidades, desayuno |
| `experiencia` | Tours, senderismo, deportes, avistamiento, experiencias culturales y comunitarias | Duración, nivel físico, punto de encuentro, edad mínima, tamaño de grupo (no supera el aforo), guía e idiomas, qué llevar, requisitos |
| `gastronomia` | Restaurante, café o bar | Tipos de cocina, opciones dietarias, rango de precio por persona, reserva, puestos, domicilio |
| `entrada` | Parques, playas, museos, eventos | Tarifas por tipo de visitante, temporadas de cierre, reglas, servicios en el sitio |
| `alquiler` | Alquiler de equipo | Equipos, depósito, documento |
| `transporte` | Lancha y traslado terrestre | Origen, destino, duración, capacidad, horarios, chaleco salvavidas |
| `pagos` | Todos (la PWA lo sugiere en experiencias, entradas y transporte) | Ver abajo |

**Dinero y pagos en el lugar (`pagos`):** en sitios alejados puede no haber señal para pagar ni cajeros. El prestador informa la señal de internet (`CON_SENAL`, `INTERMITENTE`, `SIN_SENAL`), los medios que acepta (efectivo, tarjeta, transferencia como Nequi, Daviplata o Bre-B), qué recomienda llevar (`EFECTIVO`, `DIGITAL` o `CUALQUIERA`, que debe coincidir con los medios aceptados), si ofrece **crédito** (cubre el gasto y el turista le paga después, al recuperar señal o pasar por un cajero, con plazo y condiciones) y si hay **cajeros** cerca o dónde está el más cercano. El crédito es un acuerdo entre turista y prestador: la plataforma lo informa, no lo cobra ni lo garantiza.

Textos en `{"es", "en"}`, horas `"HH:MM"` e idiomas en ISO 639-1.

**Lectura pública:**

* **Resultados y listados** traen `tipo` y `unidad_tarifa` con sus etiquetas.
* **Ficha** (`GET /servicios/{id}`): `atributos` con los mismos bloques, pero con los textos ya en el idioma pedido; los códigos fijos (`DE_MAR`, `SIN_SENAL`...) se mantienen y su texto va en `etiquetas`. Si el servicio informó `pagos`, `aviso_pagos` trae una frase lista para mostrar o para el chatbot, por ejemplo: *«Lleva efectivo: no hay señal de internet y no hay cajeros cerca (el más cercano: Parque de Minca, a 8 km). El prestador ofrece crédito…»*. `importante=true` (sin señal o intermitente, solo efectivo o sin cajeros) indica que la PWA debe destacarlo.
* **Filtros de `/buscar` y `/mapa/servicios`** (los mismos, para que la lista y el mapa de la PWA muestren lo mismo; `GET /servicios` no los tiene porque para filtrar está `/buscar`): `tipo` (uno o varios), `unidad_tarifa`, `idioma_atencion`, `accesible`, `mascotas`, `apto_ninos`, `opcion_dietaria`, `nivel_fisico`, `acepta_pago_digital` y `ofrece_credito`. Los de atributos se combinan en una sola contención `atributos @> {...}` sobre el índice GIN. Un sí/no filtra por lo informado: `accesible=false` trae los que dijeron que no, no los que no lo informaron. Todos forman parte de la clave de la caché.
* **Disponibilidad (`fecha`, `personas`):** catalog no llama a booking (Plan §4.1: solo el Módulo 5 llama a otros servicios). Filtra con la proyección que alimenta `disponibilidad.actualizada`: excluye los servicios sin cupo para `personas` ese día o con el día cerrado; los que aún no tienen dato de ese día se muestran con `disponibilidad_confirmada=false` ("disponibilidad sin confirmar") para no esconderlos mientras booking no publique su calendario. Cada resultado trae `cupos_disponibles`. Las búsquedas y mapas con `fecha` no se cachean. Al reservar, booking vuelve a comprobar los cupos con bloqueo: este dato es para buscar, no garantiza el cupo.

## Worker y mensajería (RabbitMQ)

La API no publica en RabbitMQ ni consume eventos: todo el trabajo en segundo plano lo hace el **worker** ([`app/worker.py`](app/worker.py)), un proceso aparte que usa la misma imagen con otro comando (`python -m app.worker`) y tiene su propio Deployment.

**Por qué un proceso aparte:** publicar eventos, consumirlos y enviar correos no compite por CPU ni por conexiones con las peticiones de los turistas. Los reinicios o el escalado de la API (HPA 2–6) no cortan un consumo a medias, y el worker se escala por su lado (ver *Operación del worker*).

El worker corre a la vez, en un mismo bucle asyncio (`asyncio.gather`), estos componentes:

| Componente | Objetivo | Código |
|---|---|---|
| Relay del outbox | Llevar a RabbitMQ los eventos que la API y los consumidores guardan en la tabla `outbox` | `RelayOutbox`, `PublicarEventosPendientes`, `SqlOutboxPendiente`, `PublicadorRabbitMQ` |
| `catalog.prestadores` | Habilitar o suspender prestadores según iam | `ManejadorPrestadores`, `AplicarPrestadorAprobado`, `AplicarPrestadorSuspendido` |
| `catalog.demanda` | Proyección de reservas para la capacidad de carga y la analítica | `ManejadorDemanda`, `AplicarEventoReserva` |
| `catalog.calificaciones` | Promedio de calificación de cada servicio | `ManejadorCalificaciones`, `AplicarEventoResena` |
| `catalog.disponibilidad` | Cupos por día para filtrar por fecha y personas | `ManejadorDisponibilidad`, `AplicarDisponibilidad` |
| `catalog.notificaciones` | Correos de reservas al turista y al prestador | `ManejadorNotificaciones`, `NotificarReserva` |
| Limpieza diaria | Borrar la disponibilidad de días pasados | `TareaPeriodica`, `LimpiarDisponibilidadPasada` |
| Métricas | `/metrics` para Prometheus y sonda de vida en k8s | `start_http_server(WORKER_METRICS_PORT)` |

### Topología común

[`topologia_rabbitmq.py`](app/infrastructure/messaging/topologia_rabbitmq.py) la declara al conectar, tanto el publicador como cada consumidor. Declararla otra vez con los mismos argumentos no cambia nada, así que no importa quién arranque primero (Plan §4.2–4.3).

* Exchange `turismo.eventos` (*topic*, durable): la clave de enrutamiento es el `event_type` (`servicio.publicado`, `reserva.confirmada`...).
* Exchange `turismo.dlx` (*topic*) y cola `turismo.dead-letter` enlazada con `#`: la DLQ común de la plataforma.
* Las colas de cada consumidor (`catalog.*`) las declara su propio consumidor.

### Relay del outbox (publicación de eventos)

**Objetivo:** que cada evento que catalog produce llegue a RabbitMQ sin perderse, aunque el broker esté caído en ese momento. Los eventos son `servicio.publicado` (para booking: al crear, editar, activar o apagar un servicio, y al suspender o reactivar a un prestador) y `auditoria.registrada` (para iam: `ACCESS_DENIED` de cada `403 ROL_NO_PERMITIDO`, `ZONA_CREADA`/`EDITADA`/`DESACTIVADA`, `ALERTA_PUBLICADA`/`EDITADA`/`RETIRADA` y `EXPORT` del CSV).

**Por qué un outbox (ADR-008):** si la API publicara directo, un fallo entre guardar en PostgreSQL y publicar dejaría un cambio sin evento, o un evento de un cambio que no se guardó. Con el outbox, el cambio y su evento se guardan en la misma transacción, y el worker los publica después.

**Qué hace:**

* **Toma un lote:** cada `OUTBOX_INTERVALO_SEGUNDOS` (1 s) toma hasta `OUTBOX_LOTE` (100) eventos pendientes (`publicado_en IS NULL`), en orden de creación, con `FOR UPDATE SKIP LOCKED` sobre el índice parcial `ix_outbox_pendientes` (migración 0001). Así dos workers nunca toman el mismo evento. Si el lote salió lleno, sigue de inmediato sin esperar.
* **Publica uno a uno, con confirmación:** los mensajes son persistentes y se envían con *publisher confirms*. La clave es el `event_type` y el cuerpo, el sobre `envelope.v1`. Además, `message_id` (= `event_id`), `type`, `correlation_id`, `app_id` y `timestamp` van como propiedades AMQP, para filtrar en la consola sin abrir el cuerpo. Solo cuando el broker confirma se marca `publicado_en`; cada intento suma 1 a `intentos`.
* **Si falla un evento:** el lote se corta ahí, para que los siguientes no se adelanten y se conserve el orden. La espera se duplica con cada fallo, hasta `OUTBOX_ESPERA_MAXIMA_SEGUNDOS` (30 s), y vuelve a 1 s con el primer lote bueno. Nada se descarta: el evento sigue pendiente.
* **Conexión:** se abre con el primer envío y se reconecta sola (`connect_robust`). Si RabbitMQ no está al arrancar, el envío falla y el relay reintenta con la espera creciente.
* **Métricas:** después de cada lote actualiza `catalog_outbox_pendientes` y `catalog_outbox_antiguedad_segundos`, la edad del pendiente más viejo, que es la alerta de que el relay no avanza.
* **Retención:** una vez al día (la primera, al arrancar) borra los eventos publicados hace más de `OUTBOX_RETENCION_DIAS` (7). Así la tabla no crece sin fin y queda una semana para revisar qué salió.

**Garantías y límites:**

* **Entrega "al menos una vez":** si el worker cae entre la confirmación del broker y la marca `publicado_en`, el evento sale otra vez. Los consumidores descartan los duplicados por `event_id` (tabla `evento_procesado`).
* **Sin cola enlazada, el broker descarta el mensaje** (`mandatory=False`): cada consumidor de otro módulo (iam, booking...) debe declarar su cola durable antes de necesitar los eventos.
* **Auditoría (ESC-04):** el `ACCESS_DENIED` guarda el usuario, su rol, los roles permitidos, el método, la ruta y la IP de origen (`X-Forwarded-For`). Si no se puede guardar, queda en el log y el 403 sale igual. `PERFIL_INACTIVO` no se audita: es una regla del negocio, no un acceso indebido.

### Consumidores: base común

**Objetivo:** que catalog tenga su propia copia de lo que necesita de iam, booking y review, y responda sin llamarlos en cada petición. Plan §4.1: solo el Módulo 5 llama a otros servicios; la única excepción en catalog es el contacto de iam para los correos.

Todas las colas usan la misma base, `ConsumidorRabbitMQ` ([`consumidor_rabbitmq.py`](app/infrastructure/messaging/consumidor_rabbitmq.py)):

* **Cola principal** durable `catalog.<propósito>`, enlazada a sus claves en `turismo.eventos`, con `x-dead-letter-exchange: turismo.dlx`.
* **Prefetch:** cada consumidor procesa a la vez hasta `CONSUMIDOR_PREFETCH` (10) mensajes. Así una cola lenta (p. ej. correos esperando a SMTP) no acapara al worker.
* **Validación:** el sobre se valida con `SobreEvento` y el payload con el esquema Pydantic de cada evento (`messaging/esquemas/`). Solo se acepta la `version` 1. El `correlation_id` del sobre se fija para los logs y para los eventos que se generen (p. ej. el `servicio.publicado` que provoca una suspensión lleva la correlación de iam).
* **Reintentos a 1 s, 5 s y 25 s:** ante un error transitorio (base de datos, iam o SMTP caídos), el mensaje se copia a `<cola>.reintento.<espera>`, una cola con TTL que, al vencer, lo devuelve a la cola principal. El intento viaja en la cabecera `x-intentos`, y el último error, en `x-ultimo-error`.
* **DLQ:** si falla el 3.er reintento (unos 31 s en total), el mensaje se copia a `turismo.dead-letter` con `x-cola`, `x-intentos` y `x-error`. Un **error permanente** va directo, sin reintentos: un sobre o payload que no cumple el contrato, una versión distinta de 1, una clave que la cola no maneja (`EventoInvalido`) o un dato que el dominio rechaza (`DatoInvalido`). Reintentarlo no lo arregla.
* **No se pierde nada:** el original se reconoce (`ack`) solo después de copiarlo al reintento o a la DLQ. Si la copia al reintento falla, el mensaje vuelve a la cola (`nack` con `requeue`). Si falla la copia a la DLQ, se rechaza y el broker lo lleva igual a la DLQ (por el `x-dead-letter-exchange` de la cola), solo que sin el texto del error.
* **Idempotencia:** el caso de uso registra el `event_id` en `evento_procesado` (con el nombre del consumidor) en la misma transacción del efecto; un duplicado se reconoce y se descarta. La excepción son los correos (ver `catalog.notificaciones`).
* **Orden:** los eventos pueden llegar repetidos o desordenados (reintentos, varias réplicas). Cada proyección guarda la marca del último evento aplicado y descarta uno más viejo, que cuenta como `ignorado`.
* **Resultado** en la métrica `catalog_eventos_consumidos_total{cola,event_type,resultado}`: `aplicado`, `duplicado`, `ignorado`, `reintento` o `dlq`.

Cada cola tiene un **manejador** (`messaging/manejador_*.py`) que traduce el evento a un DTO de la capa de aplicación y llama a su caso de uso. Así la lógica no depende de RabbitMQ y se prueba sin broker.

### `catalog.prestadores` (iam → perfil del prestador)

**Claves:** `prestador.aprobado`, `prestador.suspendido`.

**Objetivo:** que solo un prestador aprobado por iam pueda publicar servicios (UC17, UC28), y que una suspensión saque del catálogo sus servicios (UC27).

**Qué hace:**

* **Aprobado:** crea el perfil (habilita UC17) o lo reactiva, y actualiza la razón social. Al reactivar vuelven solo los servicios apagados por la suspensión; los que apagó el propio prestador siguen apagados.
* **Suspendido:** apaga el perfil y sus servicios activos, marcados como apagados por suspensión para saber cuáles restaurar.
* Cada servicio que cambia guarda un `servicio.publicado` en el outbox, para que booking deje de aceptar reservas o vuelva a aceptarlas. Si cambió algún servicio, se invalida la caché de búsqueda y mapa.
* Siempre bloquea primero el perfil y después los servicios, el mismo orden que en toda escritura, para no crear interbloqueos con la API.

**Por qué así:**

* **Orden:** `prestador_perfil.estado_iam_en` (migración 0005) guarda el `occurred_at` del último evento de iam aplicado. Uno más viejo (p. ej. un reintento que llega tarde) se ignora y no reactiva a un suspendido.
* **Suspensión antes de la aprobación:** si llega primero (por un reintento de la aprobación), se guarda un perfil mínimo ya suspendido. La aprobación vieja se ignora y no queda activo un prestador que iam suspendió; una aprobación más nueva sí lo activa.

### `catalog.demanda` (booking → proyección de reservas)

**Claves:** `reserva.solicitada`, `.modificada`, `.confirmada`, `.rechazada`, `.cancelada`, `.finalizada`.

**Objetivo:** tener la demanda por servicio y día para la capacidad de carga (UC24), el mapa de calor (RF-07), la analítica (UC22–UC25) y el CSV (UC38), sin consultar nunca `booking_db`.

**Qué hace:** guarda en `reserva_proyeccion` el estado actual de cada reserva: servicio, prestador, turista, fecha, personas y estado. `modificada` mueve la fecha y las personas. La demanda de un día es la suma de las personas de las reservas activas (Solicitada y Confirmada) de esa fecha. Si llega, por ejemplo, la confirmación antes que la solicitud, crea la fila igual.

**Por qué el estado y no contadores:** un evento solo se aplica si ocurrió después del último aplicado, así los repetidos o desordenados no descuadran nada; con contadores, un duplicado sumaría dos veces. No invalida la caché, porque la demanda no sale en búsqueda ni mapa. Estas filas no se borran: son la historia de la analítica.

### `catalog.calificaciones` (review → promedio)

**Claves:** `resena.publicada`, `resena.ocultada`.

**Objetivo:** mostrar el promedio de calificación de cada servicio en búsqueda, mapa y ficha (UC22).

**Qué hace:** guarda una fila por reseña en `calificacion_resena`, con su puntuación y si está `visible`. El promedio se calcula al leer y cuenta solo las visibles. Ocultar una reseña (moderación, UC29) la saca del promedio; volver a publicarla la devuelve, sin contar doble. Un evento más viejo que el último aplicado (`ultimo_evento_en`, migración 0006) se ignora, y una ocultación que llega antes que la publicación crea la fila ya oculta.

**Por qué no invalida la caché:** el promedio nuevo se ve cuando la caché expira (300 s). Así una ola de reseñas en temporada alta no borra la caché del catálogo justo cuando más se necesita (ESC-02).

### `catalog.disponibilidad` (booking → cupos por día)

**Clave:** `disponibilidad.actualizada`.

**Objetivo:** que `/buscar` y `/mapa/servicios` filtren por `fecha` y `personas` (ver *Disponibilidad* arriba).

**Qué hace:** guarda en `disponibilidad_proyeccion` (migración 0008) los cupos de cada servicio por día, con la `version` de la fila de booking. Una versión menor o igual se ignora. Un día cerrado llega con `cupos_totales = 0`.

**Por qué un evento y no una llamada a booking:** por Plan §4.1, catalog no llama a otros servicios. Booking publica el estado completo del día cada vez que cambia, así basta el último evento, sin sumar ni restar. No invalida la caché, porque las búsquedas y mapas con `fecha` no se cachean.

### `catalog.notificaciones` (booking → correos)

**Claves:** `reserva.solicitada`, `.modificada`, `.confirmada`, `.rechazada`, `.cancelada`. `reserva.finalizada` no envía correo.

**Objetivo:** avisar por correo a quien le toca actuar o enterarse (UC36).

**Qué hace:**

* **Destinatario:** la solicitud y la modificación van al prestador; la confirmación y el rechazo, al turista. La cancelación va a la otra parte, según `cancelada_por`: si canceló el turista, al prestador; si no, al turista.
* **Contenido:** la confirmación lleva el contacto del prestador, su política, la regla base de cancelación y el aviso de pagos; el rechazo y la cancelación llevan el `motivo`; la modificación, la fecha y las personas anteriores, y la solicitud, cuándo expira.
* **Datos:** el servicio y el perfil del prestador salen de la base de catalog. El contacto del destinatario (nombre, correo, idioma) se pide a iam al momento (`GET /internal/usuarios/{id}/contacto`, `contracts/openapi/iam-interno.yaml`) y no se guarda.
* **Redacción:** plantillas Jinja en el idioma del destinatario (es/en), en HTML y texto (`infrastructure/notificaciones/plantillas/`). Se envían por SMTP (`aiosmtplib`): STARTTLS en producción y Mailpit en desarrollo.
* **Si no se puede enviar:** si no existe el servicio, el perfil o el usuario en iam (404), no se envía y cuenta como `ignorado`. Si iam falla o tarda más de `IAM_TIMEOUT_SECONDS`, o el servidor SMTP no acepta el correo, se reintenta (1 s, 5 s, 25 s) y luego va a la DLQ.

**Por qué así:**

* **Un correo no es transaccional:** se revisa si el evento ya se procesó, se envía y después se registra el `event_id`. Si el worker cae entre ambos pasos, el correo sale dos veces; se prefiere eso a perderlo.
* **Una cola aparte de `catalog.demanda`:** un correo que falla reintenta solo él, sin frenar la proyección de reservas, y un reintento de la demanda no reenvía correos.

### Limpieza diaria de la disponibilidad

**Objetivo:** que `disponibilidad_proyeccion` no crezca sin fin. Los días pasados ya no sirven para buscar.

**Qué hace:** `TareaPeriodica` ([`infrastructure/tareas/`](app/infrastructure/tareas/tarea_periodica.py)) corre `LimpiarDisponibilidadPasada` al arrancar el worker y luego cada 24 h desde ese momento, no a una hora fija. Borra las filas con fecha anterior a hoy. Si falla, queda en el log y se intenta otra vez en la siguiente vuelta: una limpieza que no corrió hoy no afecta a nadie.

**Por qué en el worker y no en un CronJob:** no hace falta otro manifiesto ni otro pod, y la tarea se puede repetir sin daño (es un `DELETE` por fecha). Con dos réplicas del worker corre en las dos sin problema. Las reservas de `reserva_proyeccion` **no** se borran: son la analítica.

### Configuración del worker

Variables de entorno (`app/config.py`, valores de desarrollo en `.env.example`; en k8s, `configmap.yaml` y el Secret `catalog-secretos`):

| Variable | Por defecto | Para qué |
|---|---|---|
| `DATABASE_URL` | base de desarrollo | Outbox, proyecciones y `evento_procesado` |
| `VALKEY_URL` / `VALKEY_TIMEOUT_SECONDS` | `:6380` / 0,25 s | Invalidar la caché tras un cambio de prestador |
| `RABBITMQ_URL` / `RABBITMQ_TIMEOUT_SECONDS` | `:5673` / 5 s | Conexión, confirmación del broker y copias a reintento o DLQ |
| `EVENTS_EXCHANGE` | `turismo.eventos` | Exchange donde publica y del que consume |
| `OUTBOX_LOTE` | 100 | Eventos por vuelta del relay |
| `OUTBOX_INTERVALO_SEGUNDOS` | 1 | Pausa entre vueltas sin fallos |
| `OUTBOX_ESPERA_MAXIMA_SEGUNDOS` | 30 | Tope de la espera tras fallos (relay y conexión inicial de los consumidores) |
| `OUTBOX_RETENCION_DIAS` | 7 | Días que se guardan los eventos ya publicados |
| `CONSUMIDOR_PREFETCH` | 10 | Mensajes en proceso a la vez por cola |
| `WORKER_METRICS_PORT` | 9102 | `/metrics` (Prometheus y sondas) |
| `IAM_URL_INTERNA` / `IAM_TIMEOUT_SECONDS` | `:8001` / 3 s | Contacto de usuarios para los correos |
| `SMTP_HOST`, `SMTP_PORT` | `localhost`, 1026 (Mailpit) | Servidor de correo |
| `SMTP_USUARIO`, `SMTP_CLAVE`, `SMTP_STARTTLS` | vacíos, `false` | Autenticación y TLS en producción (Secret) |
| `SMTP_REMITENTE` / `SMTP_TIMEOUT_SECONDS` | Turismo Santa Marta / 10 s | Remitente y espera máxima del envío |
| `LOG_LEVEL` | `INFO` | Logs JSON con el nombre `catalog-service-worker` |

### Dependencias: qué pasa si fallan

| Si falla... | Relay del outbox | Consumidores |
|---|---|---|
| **PostgreSQL** | El lote falla y la espera crece hasta 30 s; los eventos siguen pendientes | El evento se reintenta (1 s, 5 s, 25 s) y, si la base sigue caída, va a la DLQ |
| **RabbitMQ** | Igual: espera creciente; nada se pierde (está en el outbox) | Al arrancar, cada consumidor reintenta la conexión con espera creciente (de 1 s hasta 30 s); después, `connect_robust` reconecta solo |
| **Valkey** | — | No se invalida la caché (queda en el log); los datos viejos expiran solos en 300 s |
| **iam** | — | Solo afecta a `catalog.notificaciones`: reintentos y luego DLQ |
| **SMTP** | — | Igual que iam |

Los mensajes de la DLQ conservan el cuerpo original y las cabeceras `x-cola`, `x-intentos` y `x-error`, así que se pueden reenviar a su cola desde la consola de RabbitMQ cuando la dependencia vuelva.

### Operación del worker

* **Arranque:** primero levanta `/metrics` en `WORKER_METRICS_PORT` y luego el relay, los consumidores (uno tras otro) y la limpieza.
* **Apagado ordenado:** con SIGTERM o SIGINT (en Windows, solo Ctrl+C) termina las vueltas en curso y cierra los consumidores, el publicador, el cliente de iam, Valkey y la base de datos. Un mensaje que no alcanzó a reconocerse vuelve a la cola, y como el consumo es idempotente, no se duplica su efecto.
* **Kubernetes** (`deployment-worker.yaml`): 1 réplica sin HPA; *requests* de 50m de CPU y 192Mi, límites de 1 núcleo y 384Mi. La `startupProbe` (hasta 90 s) y la `livenessProbe` usan `/metrics`. No tiene *readiness* porque no recibe tráfico. Se puede subir a 2 réplicas sin duplicar publicaciones (`SKIP LOCKED` en el relay, consumidores idempotentes, limpieza repetible).
* **Métricas:** `catalog_outbox_pendientes`, `catalog_outbox_antiguedad_segundos` (alertar si crece), `catalog_eventos_publicados_total{event_type}`, `catalog_eventos_fallos_publicacion_total` y `catalog_eventos_consumidos_total{cola,event_type,resultado}`.
* **Logs:** en JSON, con el `correlation_id` de cada evento consumido.

## Correlación

Cada respuesta lleva `X-Correlation-ID` (el que envía Traefik o uno nuevo) y los logs salen en JSON con ese mismo identificador.

Imagen de contenedor (multi-stage):

```bash
docker build -t catalog-service:dev .
docker run --env-file .env -p 8002:8002 catalog-service:dev
```
