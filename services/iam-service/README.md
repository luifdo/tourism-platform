# iam-service

**Módulo 1: Seguridad & IAM** · Responsable: Valentina Sarait Nieves Hernandez (@nievesita)

Autenticación JWT (RS256), verificación de tokens para el API Gateway (ForwardAuth), control de acceso por roles (RBAC), verificación de prestadores (RNT, RUT), consentimiento de datos personales (Ley 1581) y bitácora de auditoría inmutable.

| Aspecto | Valor |
|---|---|
| Casos de uso | UC1, UC2, UC3, UC4, UC6, UC27, UC28, UC32, UC33, UC37 |
| Requerimientos funcionales | RF-08, RF-09, RF-12 |
| Requerimientos no funcionales | RNF-04, RNF-10 |
| Escenarios de calidad | ESC-04 |
| Persistencia | PostgreSQL — base lógica `iam_db`; documentos en SeaweedFS (bucket `documentos-verificacion`); tokens revocados en Valkey |
| Lenguaje / framework | Python 3.12 + FastAPI (orientado a objetos, arquitectura hexagonal) |
| Puerto interno | `8001` |
| Prefijo en el Gateway (Traefik) | `/api/iam` |
| Réplicas en k3s | 2 (HPA hasta 4) |
| Contrato REST | [`contracts/openapi/iam.yaml`](../../contracts/openapi/) |

## Eventos

**Publica** (mediante el outbox, ver abajo):
* `prestador.suspendido.v1`: un Prestador activo deja de estarlo (UC27), C-17
* `prestador.aprobado.v1`: en el bloque 5 (UC28)

**Consume:**
* `auditoria.registrada.v1` (de catalog, booking y review), en la cola durable `iam.auditoria`

Esquemas en [`contracts/events/`](../../contracts/events/).

### Worker y bitácora de los demás servicios

El worker (`python -m app.worker`, misma imagen que la API) consume `iam.auditoria` y guarda cada evento en `bitacora_auditoria`:

| Columna | Valor |
|---|---|
| `event_id` | El del sobre. `UNIQUE`: un evento reentregado no se inserta otra vez (`ON CONFLICT DO NOTHING`) |
| `fecha` | El `occurred_at` del sobre (cuándo pasó), no el momento de la inserción |
| `servicio_origen` | El `producer` del sobre |
| `correlation_id` | El del sobre (nulo si no viene) |
| `resultado` | `EXITO`, `DENEGADO` y `ERROR` del contrato se guardan como `Exito`, `Denegado` y `Error` |
| `usuario_id` | Nulo si no existe en `usuario`; el valor recibido queda en `detalles.usuario_id_no_registrado` |
| `ip_origen` | Nula si no es una IP; el texto recibido queda en `detalles.ip_origen_invalida` |

Reintentos a 1, 5 y 25 s ante fallos pasajeros (por ejemplo, PostgreSQL caído). Lo que no cumple el contrato, o falla 4 veces, va a `turismo.dead-letter` con las cabeceras `x-cola`, `x-intentos` y `x-error`. **Nada lo reprocesa solo:** se revisa a mano en la consola de RabbitMQ (http://localhost:15672) y, si se corrigió, se vuelve a publicar desde ahí con la clave `auditoria.registrada`. Repetir un evento ya guardado no lo duplica.

### Outbox y relay

Los eventos del IAM se guardan en la tabla `outbox` en la misma transacción que el cambio (ADR-008, C-09), y el mismo worker los publica en `turismo.eventos` con *publisher confirms*. Lotes de 100 (`OUTBOX_LOTE`) con `FOR UPDATE SKIP LOCKED`, pausa de 1 s entre lotes, espera creciente hasta 30 s si RabbitMQ o PostgreSQL fallan, y limpieza diaria de lo publicado hace más de 7 días. Un evento solo se marca como publicado cuando el broker confirma; la entrega es "al menos una vez" y los consumidores descartan duplicados por `event_id`.

Métricas en `http://localhost:9101/metrics` (`WORKER_METRICS_PORT`), que también sirven de sonda de vida:

* `iam_eventos_consumidos_total{cola, event_type, resultado}`, con `resultado` igual a `aplicado`, `duplicado`, `reintento` o `dlq`.
* `iam_eventos_publicados_total{event_type}`, `iam_eventos_fallos_publicacion_total`, `iam_outbox_pendientes` e `iam_outbox_antiguedad_segundos`.

## Estructura (arquitectura hexagonal)

```
app/
├── main.py              # composición: crea la app FastAPI, el engine y /metrics
├── config.py            # Settings (pydantic-settings) leídos de variables de entorno / .env
├── domain/              # núcleo puro, sin dependencias de frameworks
│   ├── entities/
│   ├── value_objects/
│   └── ports/           # interfaces (Protocols) que implementa la infraestructura
├── application/
│   └── use_cases/       # una clase por caso de uso
├── infrastructure/      # adaptadores que implementan los puertos
│   ├── persistence/     # SQLAlchemy async sobre iam_db
│   ├── security/        # Argon2 (contraseñas) y PyJWT (RS256)
│   ├── cache/           # Valkey (tokens revocados)
│   ├── messaging/       # RabbitMQ
│   └── storage/         # S3 (SeaweedFS)
└── api/                 # adaptador HTTP
    ├── middleware/      # X-Correlation-ID (ASGI puro)
    ├── routers/
    ├── schemas/         # modelos Pydantic de request/response
    └── dependencies.py  # cableado de casos de uso con sus adaptadores
migrations/              # Alembic (async)
tests/
```

## Ejecución

Requiere [uv](https://docs.astral.sh/uv/) y Python 3.12.

```bash
docker compose -f docker-compose.dev.yml up -d   # PostgreSQL, Valkey, RabbitMQ, SeaweedFS, Mailpit, pgAdmin
uv sync                                   # instala dependencias (incluye dev)
cp .env.example .env                      # ajustar DATABASE_URL y demás
uv run python -m uvicorn app.main:app --reload --port 8001
uv run python -m app.worker               # worker: consume iam.auditoria (Ctrl+C para detenerlo)
uv run pytest                             # pruebas (db y valkey se omiten si el servicio no responde)
uv run pytest -m rabbitmq                 # RabbitMQ efímero con testcontainers (requiere Docker)
uv run ruff check . && uv run ruff format --check .
uv run alembic upgrade head               # aplicar migraciones
```

> En Windows, Smart App Control puede bloquear `uvicorn.exe` del `.venv`; `python -m uvicorn` evita el problema.

Mailpit (SMTP de pruebas en `localhost:1025`, interfaz en http://localhost:8025) queda listo para los correos de recuperación del bloque 6.

## Endpoints

Operativos:

* `GET /health`: `200` si PostgreSQL (`SELECT 1`) y Valkey (`PING`) responden, `503` si alguno falla. Lo usan Prometheus y Blackbox para medir la disponibilidad (RNF-01).
* `GET /health/live`: `200 {"status": "ok"}` sin consultar nada. Es la sonda del `HEALTHCHECK` de Docker y, en k8s, de readiness y liveness (C-32).
* `GET /metrics`: métricas Prometheus (prometheus-fastapi-instrumentator), más `iam_contacto_consultas_total{resultado}` de la ruta interna de contacto.

### Correlación y logs

Cada petición lleva un `X-Correlation-ID`: el que llega (lo agrega Traefik) si cumple `^[A-Za-z0-9._-]{1,100}$`, o un UUID nuevo. Se devuelve en la respuesta, va en `correlation_id` de los errores y de las filas propias de la bitácora (C-05, C-12), y en cada línea de log. Los logs de la API y del worker salen en JSON por stdout (`ts`, `nivel`, `servicio`, `logger`, `mensaje`, `correlation_id`), listos para Loki.

### `POST /api/iam/register` (UC1 + UC6)

Registro de Turistas y Prestadores. Otros roles no se autorregistran.

Cuerpo:

```json
{
  "email": "maria.perez@example.com",
  "password": "Tayrona2026",
  "nombre_completo": "María Pérez",
  "rol": "Turista",
  "habeas_data_aceptado": true,
  "es_mayor_de_edad": true,
  "idioma": "es"
}
```

`idioma` (`es` o `en`) es opcional; si no viene, queda `es`. Es el idioma de los correos (C-06).

`201 Created`: nunca incluye la contraseña ni su hash.

```json
{
  "id": "8fa88503-29e2-4ff7-b47e-bc22f8856bce",
  "email": "maria.perez@example.com",
  "nombre_completo": "María Pérez",
  "rol": "Turista",
  "email_verificado": false,
  "idioma": "es",
  "creado_en": "2026-10-23T07:17:49.145181Z"
}
```

Errores, con cuerpo `{"detail": "<mensaje>", "code": "<code>", "correlation_id": "<X-Correlation-ID>"}`:

| HTTP | `code` | Causa |
|---|---|---|
| 409 | `EMAIL_EN_USO` | Ya existe una cuenta con ese correo |
| 422 | `VALIDACION` | La petición no cumple el esquema (email mal formado, rol no permitido, campo faltante…). Incluye `"errores": [{"campo": "...", "mensaje": "..."}]` |
| 422 | `HABEAS_DATA_REQUERIDO` | No aceptó el tratamiento de datos personales (Ley 1581) |
| 422 | `MAYORIA_DE_EDAD_REQUERIDA` | No declaró ser mayor de edad |
| 422 | `PASSWORD_INVALIDA` | La contraseña no tiene entre 8 y 128 caracteres con al menos una letra y un número |
| 422 | `NOMBRE_INVALIDO` | El nombre no tiene entre 2 y 150 caracteres |

Los 422 de `VALIDACION` nunca devuelven el valor enviado, para no repetir la contraseña.

### `POST /api/iam/login` (UC2)

Cuerpo JSON (no formulario OAuth2):

```json
{ "email": "maria.perez@example.com", "password": "Tayrona2026" }
```

`200 OK`:

```json
{
  "access_token": "<JWT RS256>",
  "token_type": "bearer",
  "expires_in": 900,
  "usuario": { "id": "…", "email": "…", "nombre_completo": "…", "rol": "Turista", "email_verificado": false, "creado_en": "…" }
}
```

| HTTP | `code` | Causa |
|---|---|---|
| 401 | `CREDENCIALES_INVALIDAS` | Correo inexistente o mal formado, o contraseña incorrecta: siempre el mismo cuerpo, con `WWW-Authenticate: Bearer` |
| 403 | `CUENTA_INACTIVA` | Credenciales correctas pero la cuenta está desactivada |
| 422 | `VALIDACION` | Falta `email` o `password` |

El token lleva `sub` (id del usuario), `rol`, `jti`, `iat`, `exp`, `iss` (`iam-service`) y `typ` (`access`), y en el encabezado `kid` (huella RFC 7638 de la llave pública). Cada intento queda en la bitácora: `LOGIN_SUCCESS` o `LOGIN_FAIL` con el motivo.

### `POST /api/iam/logout` (UC2)

Requiere `Authorization: Bearer <token>`. Revoca el token (por su `jti`) hasta que expire.

| HTTP | `code` | Causa |
|---|---|---|
| 204 | — | Sesión cerrada, sin cuerpo |
| 401 | `TOKEN_INVALIDO` | Sin token, token inválido, expirado o ya revocado (con `WWW-Authenticate: Bearer`) |
| 503 | `SERVICIO_NO_DISPONIBLE` | Valkey no responde |

Cada `401` deja una fila `ACCESS_DENIED` en la bitácora (ver `GET /api/iam/auth/verificar`), con `uri` igual a la ruta del logout.

### `GET /api/iam/auth/verificar` (RF-09, ForwardAuth)

Lo llama el middleware ForwardAuth de Traefik antes de reenviar cada petición protegida. Es público: la validación es el propio endpoint. Lee `Authorization: Bearer <token>` y valida la firma RS256, el emisor, la expiración (con 10 s de margen), `typ = access` y la revocación en Valkey (por `jti` y por usuario). En el camino feliz no consulta PostgreSQL.

| HTTP | `code` | Causa |
|---|---|---|
| 200 | — | Token válido. Cuerpo vacío con `X-Usuario-Id` (el `sub`), `X-Usuario-Rol` (`Turista`, `Prestador`, `Entidad` o `Admin`) y `Cache-Control: no-store` |
| 401 | `TOKEN_INVALIDO` | Sin token, mal formado, firma de otra llave, expirado, `typ` distinto o revocado. Mismo cuerpo siempre, con `WWW-Authenticate: Bearer` |
| 503 | `SERVICIO_NO_DISPONIBLE` | Valkey no responde (falla cerrado) |

Cada `401` inserta en la bitácora, en una transacción propia, una fila `ACCESS_DENIED` / `Denegado` con:

* `usuario_id`: solo si la firma del token era válida (motivos `expirado`, `tipo` y `revocado`); queda nulo sin token o con una firma que no es válida.
* `ip_origen`: la IP real del cliente (vía `--proxy-headers`).
* `detalles`: `{"motivo", "metodo", "uri"}`. El motivo (`sin_token`, `invalido`, `expirado`, `revocado` o `tipo`) es interno y nunca sale en la respuesta. `metodo` y `uri` son los `X-Forwarded-Method` y `X-Forwarded-Uri` que envía Traefik (`null` si faltan); a la `uri` se le quita el query string.

Si la bitácora no se puede escribir, se registra un log de error y la respuesta sigue siendo `401`, nunca `500`.

#### Revocación por usuario

`RevocacionTokens.revocar_usuario(usuario_id, desde)` guarda `iam:revocado-desde:<usuario_id>` con el segundo del cambio y TTL igual a la vida del token más el margen (15 min + 10 s). Un token queda revocado si su `jti` está en `iam:revoked:<jti>` o si su `iat <= revocado-desde`; las dos llaves se leen en un solo `MGET`. Se usa `<=` porque `iat` va en segundos: un token emitido en el mismo segundo del cambio también queda revocado (el usuario vuelve a iniciar sesión). La usarán el cambio de rol y la desactivación de cuentas.

### RBAC en los endpoints del IAM: `require_role`

```python
@router.get("/admin/usuarios")
async def listar(claims: Annotated[ClaimsToken, Depends(require_role(Rol.ADMIN))]): ...
```

`require_role(*roles)` (en `app/api/dependencies.py`) aplica las mismas reglas que `verificar` sobre el Bearer de la petición y devuelve los `ClaimsToken` para que el endpoint sepa quién es el usuario.

| HTTP | `code` | Causa | `detalles` en la bitácora |
|---|---|---|---|
| 401 | `TOKEN_INVALIDO` | Igual que en `verificar` | `{"motivo", "metodo", "uri"}` (método y ruta de la propia petición) |
| 403 | `ROL_INSUFICIENTE` | El rol del token no está en la lista | `{"rol", "requeridos", "metodo", "ruta", "plantilla"}`; `plantilla` es la ruta declarada (p. ej. `/api/iam/admin/usuarios/{usuario_id}`) para agrupar por endpoint |

### Administración de usuarios: `/api/iam/admin/usuarios` (UC27)

Solo `Admin`. El endpoint temporal `/api/iam/admin/ping` ya no existe (C-33).

* `GET /api/iam/admin/usuarios?rol=&activo=&q=&pagina=1&tamano=20`: `{items, total, pagina, tamano}`. `q` busca en el nombre y en el correo, sin distinguir mayúsculas y tomando `%` y `_` literalmente; `tamano` va de 1 a 100.
* `GET /api/iam/admin/usuarios/{id}`: la cuenta, incluidas las inactivas.
* `PATCH /api/iam/admin/usuarios/{id}/rol` con `{"rol": "Entidad", "motivo": "..."}`.
* `PATCH /api/iam/admin/usuarios/{id}/estado` con `{"activo": false, "motivo": "..."}`.

Cada cuenta se devuelve como `{id, email, nombre_completo, rol, activo, email_verificado, idioma, creado_en, actualizado_en}`. Un cambio que sí cambia algo:

1. Se guarda junto con su fila `ROLE_CHANGE` o `USER_STATUS_CHANGE` en la bitácora: `usuario_id` es el Admin; `detalles` lleva `{usuario_afectado, antes, despues, motivo}`, con el motivo recortado a 500 caracteres.
2. Si un Prestador activo deja de estarlo (lo desactivan o le cambian el rol), agrega `prestador.suspendido` al outbox. El evento **no** lleva el motivo (C-41). Reactivar o pasar a Prestador no publica nada hasta el bloque 5 (C-42).
3. Si cambió el rol o se desactivó la cuenta, revoca los tokens del usuario antes y después del commit (C-21): sus peticiones siguientes reciben 401.

Un cambio sin efecto (mismo rol o mismo estado) responde `200` sin auditar, revocar ni publicar.

| HTTP | `code` | Causa |
|---|---|---|
| 404 | `USUARIO_NO_ENCONTRADO` | La cuenta no existe |
| 409 | `AUTOGESTION_NO_PERMITIDA` | El Admin intenta cambiar su propio rol o desactivarse |
| 409 | `ULTIMO_ADMIN` | La plataforma quedaría sin Admins activos |
| 422 | `VALIDACION` | Rol inexistente, `activo` no booleano, `motivo` de más de 2000 caracteres, UUID mal formado |
| 503 | `SERVICIO_NO_DISPONIBLE` | Valkey no responde: no se pudo revocar y **no se cambió nada** |

### `GET /api/iam/admin/bitacora` (UC33)

Solo `Admin`. Consulta la bitácora inmutable (RNF-10): las filas propias del IAM y las que llegan de los demás módulos por `auditoria.registrada`. Se ordena por `fecha` descendente, que es el momento del hecho (C-39). Cada consulta deja una fila `AUDIT_VIEW` con el Admin, los filtros usados y la página, nunca los resultados; se escribe después de leer y, si falla, la consulta responde igual (C-43).

| Parámetro | Valor |
|---|---|
| `usuario_id` | UUID |
| `accion` | Nombre exacto: `ROLE_CHANGE`, `ACCESS_DENIED`, `ZONA_CREADA`… (C-19) |
| `resultado` | `Exito`, `Denegado` o `Error` |
| `servicio_origen` | Exacto: `iam-service`, `catalog-service`… |
| `desde` / `hasta` | ISO 8601 **con zona horaria**; `desde` incluido, `hasta` excluido. En la URL, el `+` de un desfase va como `%2B` (o usar `Z`) |
| `pagina` / `tamano` | Desde 1 / de 1 a 100 (20 por defecto) |

```json
{
  "items": [
    {
      "id": "3f0c...",
      "fecha": "2026-10-30T04:12:45.120Z",
      "usuario_id": "b13fd0e3-efc5-43b5-83db-ffb94c2d70dd",
      "accion": "USER_STATUS_CHANGE",
      "resultado": "Exito",
      "servicio_origen": "iam-service",
      "ip_origen": "190.24.10.5",
      "detalles": {"usuario_afectado": "d24f...", "antes": {"activo": true}, "despues": {"activo": false}, "motivo": "RNT vencido"},
      "correlation_id": "a5f33072-1848-4071-b2d7-715cb2723ef6",
      "event_id": null
    }
  ],
  "total": 1,
  "pagina": 1,
  "tamano": 20
}
```

`event_id` solo aparece en las filas de otros servicios. Errores: 401 y 403 como en todo `require_role`; 422 `VALIDACION` (filtro mal formado o fecha sin zona) y 422 `RANGO_FECHAS_INVALIDO` (`desde` no es anterior a `hasta`).

### `GET /internal/usuarios/{usuario_id}/contacto` (C-15)

Ruta **interna** ([`contracts/openapi/iam-interno.yaml`](../../contracts/openapi/iam-interno.yaml)): sin `/api`, nunca expuesta por Traefik y fuera de `/docs`. La llama el worker de catalog para enviar sus correos; la NetworkPolicy solo deja llegar desde catalog-service.

`200`, también para un usuario inactivo:

```json
{
  "usuario_id": "8fa88503-29e2-4ff7-b47e-bc22f8856bce",
  "nombre": "María Pérez",
  "email": "maria.perez@example.com",
  "idioma": "es"
}
```

| HTTP | `code` | Causa |
|---|---|---|
| 404 | `USUARIO_NO_ENCONTRADO` | El usuario no existe, **o** la petición trae `X-Forwarded-For` / `X-Forwarded-Host` (llegó por Traefik), aunque el usuario exista |
| 422 | `VALIDACION` | `usuario_id` no es un UUID (por Traefik, igual 404) |

No escribe en la bitácora: cada consulta deja una línea de log con `usuario_id`, `resultado` y `correlation_id` (nunca el correo) y suma a `iam_contacto_consultas_total{resultado}` (`ok`, `no_encontrado`, `rechazado_proxy`).

### `GET /api/iam/.well-known/jwks.json`

Público. Devuelve las llaves públicas (`{"keys": [{"kty", "n", "e", "kid", "use": "sig", "alg": "RS256"}]}`) para que el Gateway y los demás servicios verifiquen los tokens. Responde `200` con `Cache-Control: public, max-age=300`.

Imagen de contenedor (multi-stage):

```bash
docker build -t iam-service:dev .
docker run --env-file .env -p 8001:8001 iam-service:dev
```

Las llaves JWT (`keys/private.pem`, `keys/public.pem`) no se versionan ni se copian en la imagen; se montan en tiempo de ejecución.

## Decisiones y riesgos conocidos

El registro completo y actualizado está en [`docs/cambios-frente-al-srs.md`](docs/cambios-frente-al-srs.md): ahí se documenta, con su causa, su efecto y su estado, todo lo que este servicio hace distinto, adicional o pendiente frente al SRS, el Plan, el Laboratorio 3 y `contracts/`. Resumen de lo que más afecta al uso del servicio:

* **El Gateway valida con `verificar` y no con el JWKS** (C-16): así se ven la revocación y los 401 quedan en la bitácora (ESC-04).
* **Identidad con `X-Usuario-Id` y `X-Usuario-Rol`** (C-13). **Riesgo:** en las rutas sin ForwardAuth un cliente puede enviarlos falsos; el gateway debe eliminarlos y ningún servicio debe leerlos en sus rutas públicas.
* **Cada 401 y 403 escribe una fila `ACCESS_DENIED`** (C-23, C-34, C-35), también en el logout, contenida por el rate limiting de Traefik (C-26). Un fallo de la bitácora nunca convierte el rechazo en un 500.
* **401 para token inválido y 403 `ROL_INSUFICIENTE` para rol insuficiente** (C-36).
* **Revocación por `jti` y por usuario en Valkey, fallando cerrado** (C-21, C-22): con Valkey caído, `verificar` y las rutas protegidas responden 503.
* **IP de origen solo desde proxies de confianza** (C-37).
* **Tokens de acceso de 15 minutos, sin refresh token** (C-20).
* **Enumeración de cuentas en el registro** (C-24): el `409` revela si un correo existe; el login no.
* **Bitácora inmutable y usuarios que se desactivan en lugar de borrarse** (C-01, C-03, C-27).
* **Auditoría de los demás servicios en un worker aparte, idempotente en la base** (C-04, C-31): un `event_id` repetido no duplica la fila.
* **Un evento válido nunca se descarta**: con un usuario desconocido o una IP inválida se guarda igual y la anomalía queda en `detalles` (C-38). `fecha` es el `occurred_at` del evento (C-39).
* **La DLQ no se reprocesa sola** (C-40): se revisa a mano en la consola de RabbitMQ.
* **Eventos del IAM por outbox, con entrega "al menos una vez"** (C-09): un evento nunca se pierde entre el commit y RabbitMQ.
* **UC27 revoca dos veces y falla cerrado** (C-21, C-29): sin Valkey no se cambia ningún rol ni estado.
* **El motivo de una suspensión no viaja por el bus** (C-41), y **un Prestador reactivado sigue oculto en catalog hasta el bloque 5** (C-42).
* **Readiness y liveness en `/health/live`, sin dependencias** (C-32, distinto del Plan §7.3): una caída de PostgreSQL o Valkey no saca a todas las réplicas a la vez; `/health` sigue mostrando la falla al monitoreo.
* **Contacto interno con 404 si llega por Traefik** (C-15). **Riesgo:** catalog todavía no envía `X-Correlation-ID` en esa llamada, así que su log no se cruza con el evento.
* **El 500 de una excepción no controlada sale sin `X-Correlation-ID`** (C-05).
