# iam-service

**Módulo 1: Seguridad & IAM** · Responsable: Valentina Sarait Nieves Hernandez (@nievesita)

Autenticación JWT (RS256), verificación de tokens para el API Gateway (ForwardAuth), control de acceso por roles (RBAC), verificación de prestadores (RNT, RUT), consentimiento de datos personales (Ley 1581) y bitácora de auditoría inmutable.

| Aspecto | Valor |
|---|---|
| Casos de uso | UC1, UC2, UC3, UC4, UC6, UC27, UC28, UC32, UC33, UC37 |
| Requerimientos funcionales | RF-08, RF-09, RF-12 |
| Requerimientos no funcionales | RNF-04, RNF-10 |
| Escenarios de calidad | ESC-04 |
| Persistencia | PostgreSQL — base lógica `iam_db`; documentos en SeaweedFS (bucket `documentos-verificacion`); tokens revocados y de recuperación en Valkey |
| Lenguaje / framework | Python 3.12 + FastAPI (orientado a objetos, arquitectura hexagonal) |
| Puerto interno | `8001` |
| Prefijo en el Gateway (Traefik) | `/api/iam` |
| Réplicas en k3s | 2 (HPA hasta 4) |
| Contrato REST | [`contracts/openapi/iam.yaml`](../../contracts/openapi/) |

## Eventos

**Publica** (mediante el outbox, ver abajo):
* `prestador.suspendido.v1`: un Prestador activo deja de estarlo (UC27), C-17
* `prestador.aprobado.v1`: el Admin aprueba los documentos de un Prestador activo (UC28), o rehabilita a uno ya verificado (C-42)

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

## Integración con otros módulos

Estado comprobado el 2026-10-30 con `infra/docker-compose.yml` (arranque desde volúmenes vacíos y flujo de punta a punta, con la identidad enviada a mano porque aún no hay Traefik). ✅ conectado y probado · ⏳ pendiente.

| Necesita | De | Para qué | Estado |
|---|---|---|---|
| `auditoria.registrada` | catalog, booking y review | Bitácora (UC33) | ✅ de los tres |
| `ip_origen` en `auditoria.registrada` | booking | ESC-04 | ⏳ booking no la envía; catalog y review sí |
| `X-Correlation-ID` al pedir el contacto | catalog | Cruzar el log con el evento (C-15) | ✅ |
| Cola `catalog.prestadores` | catalog | Recibir `prestador.aprobado` y `prestador.suspendido` | ✅ |
| Rutas, ForwardAuth y borrado de `X-Usuario-*` | Traefik (Juan Francisco) | ForwardAuth y borrado de identidad (C-13) | ⏳ `gateway/config` no existe; sin él no hay acceso desde fuera del clúster |
| Borrar el perfil en `catalog_db` al suprimir datos | catalog | Ley 1581 (C-27) | ⏳ falta acordar el evento |
| Rol, bucket, identidad S3 y llaves JWT en local | `infra/` | Levantar el servicio | ✅ ver "Con el compose del monorepo" |
| Lo mismo en k3s | `infra/k8s/` | Desplegar | ⏳ `infra/k8s/` no existe |

| Ofrece | A | Estado |
|---|---|---|
| `prestador.aprobado` y `prestador.suspendido` | catalog | ✅ incluida la rehabilitación |
| `GET /internal/usuarios/{id}/contacto` | worker de catalog | ✅ los correos llegan a Mailpit |
| `GET /api/iam/auth/verificar` | Traefik | ✅ devuelve la identidad; ⏳ falta conectarlo a Traefik |

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
uv run pytest -m s3                       # SeaweedFS de docker-compose.dev.yml (se omite si no responde)
uv run python -m scripts.crear_bucket     # crea el bucket documentos-verificacion (idempotente)
uv run ruff check . && uv run ruff format --check .
uv run alembic upgrade head               # aplicar migraciones
```

> En Windows, Smart App Control puede bloquear `uvicorn.exe` del `.venv`; `python -m uvicorn` evita el problema.

> **Pruebas:** las de integración comparten la base de desarrollo. En el bloque 6 apareció una falla que dependía de su estado: un evento que quedó pendiente en el outbox (por usar el servicio sin el worker) le cambiaba el resultado a `test_outbox_pg.py`, y otra prueba del mismo archivo lo marcaba como publicado con un commit real, de modo que la corrida siguiente ya pasaba. Se corrigió con la fixture `sin_pendientes_ajenos`. Puede ser también la causa de la falla intermitente del bloque 5, pero no se puede confirmar porque de esa no se guardó la salida. Si aparece otra, guardar la salida completa (`uv run pytest -q > salida.log 2>&1`) e identificar la prueba.

Mailpit (SMTP de pruebas en `localhost:1025`, interfaz en http://localhost:8025) recibe los correos de recuperación sin enviarlos. `scripts/smoke_test.py` lee de ahí el enlace (`http://localhost:8025/api/v1/messages`), así que necesita Mailpit, SeaweedFS y el bucket.

SeaweedFS de desarrollo (`chrislusf/seaweedfs:3.80`, puerto 8333) no tiene archivo de identidades: acepta cualquier credencial (incluso vacía) y no comprueba las firmas. Antes de cargar documentos hay que crear el bucket con `scripts.crear_bucket`. En k3s, el bucket y las credenciales los provee `infra/` (C-46).

## Endpoints

Operativos:

* `GET /health`: `200` si PostgreSQL (`SELECT 1`) y Valkey (`PING`) responden, `503` si alguno falla. Lo usan Prometheus y Blackbox para medir la disponibilidad (RNF-01).
* `GET /health/live`: `200 {"status": "ok"}` sin consultar nada. Es la sonda del `HEALTHCHECK` de Docker y, en k8s, de readiness y liveness (C-32).
* `GET /metrics`: métricas Prometheus (prometheus-fastapi-instrumentator), más `iam_contacto_consultas_total{resultado}` de la ruta interna de contacto e `iam_recuperacion_solicitudes_total{resultado}` de la recuperación de contraseña.

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
| 503 | `SERVICIO_OCUPADO` | Demasiadas peticiones calculando contraseñas; incluye `Retry-After: 2` (C-53). No crea la cuenta |

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
| 503 | `SERVICIO_OCUPADO` | Demasiadas peticiones calculando contraseñas; incluye `Retry-After: 2` (C-53). No deja fila `LOGIN_FAIL` |

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
2. Si un Prestador activo deja de estarlo (lo desactivan o le cambian el rol), agrega `prestador.suspendido` al outbox. El evento **no** lleva el motivo (C-41). Reactivar a un Prestador o devolverle el rol publica `prestador.aprobado` solo si sus dos documentos están aprobados (C-42).
3. Si cambió el rol o se desactivó la cuenta, revoca los tokens del usuario antes y después del commit (C-21): sus peticiones siguientes reciben 401.

Un cambio sin efecto (mismo rol o mismo estado) responde `200` sin auditar, revocar ni publicar.

| HTTP | `code` | Causa |
|---|---|---|
| 404 | `USUARIO_NO_ENCONTRADO` | La cuenta no existe |
| 409 | `AUTOGESTION_NO_PERMITIDA` | El Admin intenta cambiar su propio rol o desactivarse |
| 409 | `ULTIMO_ADMIN` | La plataforma quedaría sin Admins activos |
| 422 | `VALIDACION` | Rol inexistente, `activo` no booleano, `motivo` de más de 2000 caracteres, UUID mal formado |
| 503 | `SERVICIO_NO_DISPONIBLE` | Valkey no responde: no se pudo revocar y **no se cambió nada** |

### Documentos de verificación (UC37) y revisión de prestadores (UC28)

**El prestador** (solo rol `Prestador`):

* `POST /api/iam/prestador/documentos`, en `multipart/form-data` con `tipo` (`RNT` o `RUT`), `archivo` y, con el RUT, `razon_social` (de 2 a 200 caracteres, C-07). Responde `201` con el documento `Pendiente`.
  * Solo PDF, JPG o PNG **reales**: el tipo se reconoce por la firma de bytes, no por la extensión ni por el `Content-Type` del cliente. Hasta 5 MB (C-30).
  * Un archivo nuevo reemplaza al pendiente o al rechazado del mismo tipo (el anterior se conserva con `vigente: false`). Si el vigente ya está aprobado, `409 DOCUMENTO_APROBADO`.
* `GET /api/iam/prestador/documentos`: `{usuario_id, razon_social, estado, documentos}`, con los vigentes, su estado y el `motivo_rechazo`. `estado` es `incompleto`, `pendiente`, `rechazado` o `aprobado`.

**El Admin:**

* `GET /api/iam/admin/prestadores?estado=pendiente&pagina=1&tamano=20`: la cola de revisión, de la cuenta más antigua a la más nueva, con los documentos vigentes de cada uno.
* `GET /api/iam/admin/prestadores/{usuario_id}/documentos`: el historial completo, incluidos los reemplazados.
* `GET /api/iam/admin/documentos/{documento_id}/url`: `{url, expira_en}`, una URL de SeaweedFS que vale **5 minutos** y muestra el archivo como `RUT.pdf` con su tipo real. Cada consulta queda como `DOCUMENT_VIEW`; si la bitácora no responde, no hay URL.
* `POST /api/iam/admin/prestadores/{usuario_id}/aprobar`: aprueba el RNT y el RUT vigentes (`PROVIDER_APPROVED`). Si la cuenta está activa, publica `prestador.aprobado` con la razón social; si está inactiva, el evento sale al reactivarla (C-42).
* `POST /api/iam/admin/prestadores/{usuario_id}/rechazar` con `{"documentos": [{"tipo": "RUT", "motivo": "El RUT está ilegible."}]}`: rechaza esos documentos (`PROVIDER_REJECTED`). El prestador ve el motivo y carga otro.

Las respuestas nunca incluyen la llave del objeto en SeaweedFS. Ver C-30, C-44, C-45 y C-47.

| HTTP | `code` | Causa |
|---|---|---|
| 404 | `USUARIO_NO_ENCONTRADO` / `DOCUMENTO_NO_ENCONTRADO` | La cuenta o el documento no existen, o no hay un vigente de ese tipo para rechazar |
| 409 | `DOCUMENTO_APROBADO` | Carga sobre un documento vigente ya aprobado (la renovación queda fuera, C-45) |
| 409 | `DOCUMENTOS_INCOMPLETOS` | Aprobar sin el RNT o el RUT |
| 409 | `DOCUMENTO_YA_REVISADO` | Aprobar con un documento rechazado, o rechazar uno ya revisado |
| 409 | `NO_ES_PRESTADOR` | La cuenta no tiene el rol Prestador |
| 413 | `ARCHIVO_DEMASIADO_GRANDE` | Más de 5 MB |
| 422 | `TIPO_ARCHIVO_NO_PERMITIDO` | No es PDF, JPG ni PNG |
| 422 | `RAZON_SOCIAL_INVALIDA` | RUT sin razón social válida |
| 422 | `VALIDACION` | Formulario o cuerpo mal formado (tipo inexistente, motivo vacío o de más de 500 caracteres, tipo repetido) |
| 503 | `SERVICIO_NO_DISPONIBLE` | SeaweedFS no responde: no se registró nada |

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

Ruta **interna** ([`contracts/openapi/iam-interno.yaml`](../../contracts/openapi/iam-interno.yaml)): sin `/api`, nunca expuesta por Traefik y fuera de `/docs`. La llama el worker de catalog para enviar sus correos; de los demás servicios, la NetworkPolicy solo deja llegar a ese worker (C-54).

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
| 404 | `USUARIO_NO_ENCONTRADO` | El usuario no existe o suprimió sus datos (C-27), **o** la petición trae `X-Forwarded-For` / `X-Forwarded-Host` (llegó por Traefik), aunque el usuario exista |
| 422 | `VALIDACION` | `usuario_id` no es un UUID (por Traefik, igual 404) |

No escribe en la bitácora: cada consulta deja una línea de log con `usuario_id`, `resultado` y `correlation_id` (nunca el correo) y suma a `iam_contacto_consultas_total{resultado}` (`ok`, `no_encontrado`, `rechazado_proxy`).

### Perfil: `/api/iam/perfil` (UC4)

Cualquier rol autenticado, con la validación de token de `require_role`.

* `GET /api/iam/perfil`: `{id, email, nombre, rol, idioma, razon_social, creado_en}`, con `ETag` a partir de la versión.
* `PATCH /api/iam/perfil` con `{"nombre"?, "idioma"?}`: las reglas del registro. El correo y la razón social no se editan (C-51). `If-Match` es opcional; si no coincide, `409 VERSION_CONFLICTO`. Repetir el mismo `PATCH` responde `200`, también con el `If-Match` viejo, por eso no usa `Idempotency-Key` (C-49). Audita `PROFILE_UPDATE` con los nombres de los campos, nunca los valores.
* `POST /api/iam/perfil/contrasena` con `{"password_actual", "password_nueva"}`: `204` sin token nuevo; todas las sesiones se revocan y la PWA debe iniciar sesión otra vez (C-21, C-52).

| HTTP | `code` | Causa |
|---|---|---|
| 401 | `TOKEN_INVALIDO` | Sin token, o token inválido, expirado o revocado |
| 409 | `VERSION_CONFLICTO` | `If-Match` no coincide con la versión actual |
| 422 | `NOMBRE_INVALIDO`, `VALIDACION` | Nombre, idioma o campo no editable |
| 422 | `PASSWORD_ACTUAL_INCORRECTA` | Contraseña actual incorrecta (no 401: no es una sesión vencida) |
| 422 | `PASSWORD_INVALIDA` | La contraseña nueva no cumple la política |
| 503 | `SERVICIO_NO_DISPONIBLE` | Valkey no responde |
| 503 | `SERVICIO_OCUPADO` | Solo al cambiar la contraseña: demasiadas peticiones calculando contraseñas; incluye `Retry-After: 2` (C-53). No cambia nada |

El cambio de contraseña y la supresión no se hacen sin conexión: exigen confirmación en línea (C-49).

### Recuperación de contraseña: `/api/iam/auth/recuperar` y `/restablecer` (UC3)

Rutas públicas (C-28).

* `POST /api/iam/auth/recuperar` con `{"email"}`: `202` de inmediato y siempre con el mismo cuerpo, exista o no el correo. El resto corre en segundo plano: ni el tiempo ni un `503` revelan si existe (C-50). El enlace vale 30 minutos, es de un solo uso y una solicitud nueva invalida la anterior. Entre dos correos a un usuario pasan al menos 60 s.
* `POST /api/iam/auth/restablecer` con `{"token", "password"}`, ignorando campos extra como `confirmacion`: `204`, y las sesiones anteriores quedan revocadas.

| HTTP | `code` | Causa |
|---|---|---|
| 400 | `TOKEN_INVALIDO` | Enlace inválido, vencido o ya usado, o cuenta desactivada o suprimida después de pedirlo |
| 422 | `PASSWORD_INVALIDA` | No cumple la política; el enlace **no** se gasta |
| 503 | `SERVICIO_NO_DISPONIBLE` | Valkey no responde al restablecer |
| 503 | `SERVICIO_OCUPADO` | Demasiadas peticiones calculando contraseñas; incluye `Retry-After: 2`. El enlace **no** se gasta (C-53) |

Si el SMTP o Valkey fallan al recuperar, el usuario recibe `202` igual y solo le queda volver a pedirlo: queda un log de error, sin el correo, y `iam_recuperacion_solicitudes_total{resultado}` (C-50). Variables: `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_USUARIO`, `SMTP_PASSWORD`, `SMTP_TLS` y `PWA_URL`.

### Supresión de datos: `DELETE /api/iam/perfil` (Ley 1581)

Con `{"password"}` en el cuerpo. **Irreversible.** Reemplaza el correo, el nombre y la razón social por valores neutros, desactiva la cuenta y borra sus documentos de SeaweedFS; la fila y la bitácora se conservan (C-27). Orden y fallos en C-48.

| HTTP | `code` | Causa |
|---|---|---|
| 204 | | Datos suprimidos |
| 401 | `CREDENCIALES_INVALIDAS` | La contraseña no coincide |
| 401 | `TOKEN_INVALIDO` | Token inválido, expirado o revocado |
| 409 | `ULTIMO_ADMIN` | Es el último Admin activo |
| 503 | `SERVICIO_NO_DISPONIBLE` | Valkey o SeaweedFS no responden. **Los tokens ya se revocaron:** hay que iniciar sesión y repetir la petición |
| 503 | `SERVICIO_OCUPADO` | Demasiadas peticiones calculando contraseñas; incluye `Retry-After: 2`. No se borró ni se revocó nada: basta con repetir la petición (C-53) |

Después: login e `recuperar` se comportan como si la cuenta no existiera, el contacto interno y la URL de los documentos responden `404`, la cola de prestadores la excluye, y el Admin recibe `409 CUENTA_SUPRIMIDA` si intenta reactivarla, cambiarle el rol o revisarla.

### `GET /api/iam/.well-known/jwks.json`

Público. Devuelve las llaves públicas (`{"keys": [{"kty", "n", "e", "kid", "use": "sig", "alg": "RS256"}]}`) para que el Gateway y los demás servicios verifiquen los tokens. Responde `200` con `Cache-Control: public, max-age=300`.

## Contrato OpenAPI

[`contracts/openapi/iam.yaml`](../../contracts/openapi/iam.yaml) se genera desde la app, con las rutas públicas y protegidas, los esquemas y los errores de cada ruta (C-57):

```bash
uv run python -m scripts.exportar_openapi
```

Una prueba falla si quedó desactualizado: después de cambiar una ruta, un esquema o un error, hay que volver a generarlo. `/internal`, `/health`, `/health/live` y `/metrics` no aparecen.

## Despliegue

### Imagen

La misma imagen sirve para la API, el worker (`python -m app.worker`) y las migraciones (`alembic upgrade head`). Corre como usuario 1000, con el sistema de archivos de solo lectura; lo único que escribe va a `/tmp`. Las llaves JWT no van en la imagen: se montan en `/srv/keys`.

```bash
docker build -t iam-service:local .
docker run --read-only --tmpfs /tmp --env-file .env -v "$PWD/keys:/srv/keys:ro" -p 8001:8001 iam-service:local
```

### Manifiestos (k3s)

`k8s/base` tiene la API, el worker, el Service, el HPA (2 a 4 réplicas), el PDB, el ConfigMap y las NetworkPolicy. `k8s/overlays/local` lo adapta al Kubernetes de Docker Desktop, con la infraestructura de `docker-compose.dev.yml`. El namespace es `turismo-app`.

```bash
# 1. Variables secretas: el overlay genera `iam-secretos` desde este archivo, que no se sube.
cp k8s/overlays/local/secretos.env.example k8s/overlays/local/secretos.env

# 2. Imagen
docker build -t iam-service:local .

# 3. Namespace y llaves JWT (ver abajo)
kubectl create namespace turismo-app
kubectl create secret generic iam-jwt-keys -n turismo-app \
  --from-file=private.pem=keys/private.pem --from-file=public.pem=keys/public.pem

# 4. Aplicar
kubectl apply -k k8s/overlays/local
kubectl -n turismo-app rollout status deploy/iam-service
```

Sin `secretos.env`, `kubectl kustomize` y `kubectl apply -k` fallan.

| Secret | Claves | Quién lo usa |
|---|---|---|
| `iam-secretos` | `DATABASE_URL`, `VALKEY_URL`, `RABBITMQ_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `SMTP_USUARIO`, `SMTP_PASSWORD` | API, worker y migraciones |
| `iam-jwt-keys` | `private.pem`, `public.pem` | Solo la API, en `/srv/keys` con modo `0440` |

El usuario de `DATABASE_URL` debe coincidir con `DB_APP_ROLE` del ConfigMap (`iam_user`): la migración inicial le revoca permisos y falla si ese rol no existe.

#### Generar `iam-jwt-keys`

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out private.pem
openssl rsa -in private.pem -pubout -out public.pem
kubectl create secret generic iam-jwt-keys -n turismo-app \
  --from-file=private.pem=private.pem --from-file=public.pem=public.pem
rm private.pem public.pem
```

Las réplicas comparten el par. Se crea aparte y no con `secretGenerator` para no copiar llaves dentro de `k8s/`. Por eso, al cambiarlas hay que reiniciar los pods (`kubectl -n turismo-app rollout restart deploy/iam-service`), y los tokens ya emitidos dejan de valer.

Valores **por confirmar** antes de producción, marcados en `k8s/base/configmap.yaml`: `FORWARDED_ALLOW_IPS` (C-56), `S3_ENDPOINT_URL`, `S3_ENDPOINT_PUBLICO` y `PWA_URL`. Y la etiqueta de Blackbox en `k8s/base/networkpolicy.yaml` (C-54).

### Para Juan Francisco (`gateway/`)

Ejemplo, **solo como documentación**: el IngressRoute y los middlewares reales son de `gateway/`.

```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata: { name: iam-forward-auth, namespace: turismo-app }
spec:
  forwardAuth:
    address: http://iam-service.turismo-app.svc:8001/api/iam/auth/verificar
    # Reemplazan lo que traiga el cliente (C-13). Sin trustForwardHeader: Traefik fija él mismo
    # X-Forwarded-Method y X-Forwarded-Uri, que van a la bitácora (C-34).
    authResponseHeaders: [X-Usuario-Id, X-Usuario-Rol]
---
# En TODAS las rutas de la plataforma, también en las públicas (C-13).
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata: { name: quitar-identidad, namespace: turismo-app }
spec:
  headers:
    customRequestHeaders:
      X-Usuario-Id: ""
      X-Usuario-Rol: ""
---
# Login y recuperación (UC32, C-26, C-50).
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata: { name: iam-rate-limit, namespace: turismo-app }
spec:
  rateLimit: { average: 5, period: 1m, burst: 5 }
---
# La carga de documentos: el IAM rechaza más de 5 MB, pero aquí se corta antes de recibir todo (C-30).
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata: { name: iam-limite-documentos, namespace: turismo-app }
spec:
  buffering: { maxRequestBodyBytes: 6291456 } # 6 MB
---
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata: { name: iam-service, namespace: turismo-app }
spec:
  entryPoints: [websecure]
  routes:
    # Públicas con límite de peticiones
    - match: Path(`/api/iam/login`) || Path(`/api/iam/auth/recuperar`)
      kind: Rule
      priority: 100
      middlewares: [{ name: quitar-identidad }, { name: iam-rate-limit }]
      services: [{ name: iam-service, port: 8001 }]
    # Públicas
    - match: Path(`/api/iam/register`) || Path(`/api/iam/auth/restablecer`) || Path(`/api/iam/.well-known/jwks.json`)
      kind: Rule
      priority: 100
      middlewares: [{ name: quitar-identidad }]
      services: [{ name: iam-service, port: 8001 }]
    # Carga de documentos
    - match: Method(`POST`) && Path(`/api/iam/prestador/documentos`)
      kind: Rule
      priority: 100
      middlewares: [{ name: quitar-identidad }, { name: iam-limite-documentos }, { name: iam-forward-auth }]
      services: [{ name: iam-service, port: 8001 }]
    # Todo lo demás. Solo este prefijo: /internal, /health y /metrics no se enrutan nunca.
    - match: PathPrefix(`/api/iam`)
      kind: Rule
      priority: 10
      middlewares: [{ name: quitar-identidad }, { name: iam-forward-auth }]
      services: [{ name: iam-service, port: 8001 }]
```

También hace falta:

* Omitir el query string de `/restablecer-contrasena` en los logs de acceso: lleva el token de recuperación (C-28).
* Que Traefik vea la IP real del cliente: `externalTrafficPolicy: Local` en su Service o `forwardedHeaders.trustedIPs` si hay otro proxy delante. Confirmar también el rango de pods de `FORWARDED_ALLOW_IPS` (C-56).
* Que el Blackbox consulte directamente `http://iam-service.turismo-app.svc:8001/health`, porque el gateway no lo enruta, y confirmar su etiqueta `app.kubernetes.io/name` (C-54).
* Definir los dominios de `PWA_URL` y `S3_ENDPOINT_PUBLICO`. Este último debe llegar a SeaweedFS desde el navegador del Admin, porque va dentro de la firma de la URL (C-30).

### Con el compose del monorepo

`infra/docker-compose.yml` ya incluye el servicio, desde la carpeta `infra/`:

```bash
cp .env.example .env
docker compose up -d --build
```

Con servicios de un solo uso que no repiten lo ya hecho, y que también funcionan con un volumen existente:

* `postgres-preparar`: crea el rol `iam_user`, con la contraseña `IAM_DB_PASSWORD`, y le da `iam_db`.
* `iam-migraciones`: aplica las migraciones.
* `iam-llaves`: genera las llaves JWT en el volumen `iam-llaves`, solo si no existen.
* `iam-admin`: crea el primer Admin con `ADMIN_EMAIL`, `ADMIN_PASSWORD` y `ADMIN_NOMBRE`.
* `seaweedfs-init`: crea el bucket `documentos-verificacion`.

Identidades de SeaweedFS en `infra/seaweedfs/s3.json`: `iam` solo en su bucket y `anonymous` solo en `catalogo-imagenes`, así que un RUT sin firma responde 403 (C-46). `-volume.max` subió a 30 (F-10). Prometheus ya tiene `iam-service` e `iam-worker`.

**Falta en k3s:** el Secret `iam-secretos`, la identidad y el bucket en `turismo-datos`, y confirmar el nombre del Service de SeaweedFS. También conviene agregar alertas sobre `iam_recuperacion_solicitudes_total{resultado="fallo_smtp"}` y `iam_eventos_consumidos_total{resultado="dlq"}` (C-40, C-50).

## Verificación

La matriz de cumplimiento, los hallazgos y los resultados están en [`docs/verificacion-fase4.md`](docs/verificacion-fase4.md); las salidas, en [`docs/evidencias/`](docs/evidencias/).

Para repetir las pruebas punta a punta detrás de Traefik, en un clúster k3d temporal (no toca tu kubeconfig, y las llaves JWT se generan en cada corrida):

```bash
uv run python -m scripts.e2e_k3d
```

Es un entorno de prueba, no de producción; requisitos y opciones en [`e2e/README.md`](e2e/README.md). El reporte queda en `docs/evidencias/e2e-k3d.txt`.

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
* **El motivo de una suspensión no viaja por el bus** (C-41). **Rehabilitar a un Prestador publica `prestador.aprobado` solo si sus dos documentos están aprobados** (C-42).
* **Los documentos pasan por el IAM y se validan por su contenido** (C-30). **Sin antivirus** (C-44), con las mitigaciones listadas en el registro. **Un documento aprobado no se renueva** (C-45).
* **El bucket y las credenciales del IAM en k3s los provee `infra/`** (C-46).
* **La supresión anonimiza y borra los documentos, pero no alcanza a todo** (C-27, C-48): el texto libre y la IP de la bitácora inmutable y la razón social del outbox hasta su purga no se pueden borrar. **Riesgo:** catalog conserva `razon_social`, `telefono` y `direccion` del perfil en `catalog_db`; falta coordinar su borrado.
* **Recuperación sin enumeración de cuentas** (C-28, C-50): todo corre después de responder `202`. **Costo:** si el correo no sale, el usuario no se entera; solo queda el log y la métrica.
* **El perfil usa `If-Match` sin `Idempotency-Key`** (C-49), y **el correo y la razón social no se editan** (C-51). **`POST /perfil/contrasena` y el 422** difieren de lo comunicado al frontend (C-52).
* **Readiness y liveness en `/health/live`, sin dependencias** (C-32, distinto del Plan §7.3): una caída de PostgreSQL o Valkey no saca a todas las réplicas a la vez; `/health` sigue mostrando la falla al monitoreo.
* **Argon2 en un hilo, con cupos por réplica y sin ocupar conexiones** (C-53). En k3s, 1 cupo para proteger a `verificar` (medido en el registro; una sola corrida en Docker Desktop, se repite en la Fase 5). **Costo:** tras 10 s de espera, los logins válidos reciben `503 SERVICIO_OCUPADO` con `Retry-After: 2` y deben reintentar.
* **S3 con tope de 9 s e hilos propios** (C-59): si SeaweedFS no responde, la carga y la supresión dan `503` a tiempo y el login sigue. Variables: `S3_HILOS_MAXIMOS` y `S3_TIEMPO_MAXIMO_SEGUNDOS`. **Costo:** cada hilo sigue ocupado unos segundos después del `503`, y una carga puede completarse después de responderlo.
* **Almacenamiento sin cifrar, propuesta por decidir** (C-58): cifrado en reposo en la infraestructura y TLS en tránsito. Cifrar en el servicio rompería las URL firmadas.
* **Salida de red sin restringir, y Blackbox entra directo a `/health`** (C-54). **Migraciones en el initContainer, con candado** y con las mismas credenciales de la app (C-55). **`FORWARDED_ALLOW_IPS` en k3s, por confirmar** (C-56). **`iam.yaml` generado, en OpenAPI 3.1** (C-57).
* **`anonymous` limitado a `catalogo-imagenes` en `infra/seaweedfs/s3.json`** (C-46): un documento sin firma responde 403. Hay que mantenerlo igual en k3s.
* **Contacto interno con 404 si llega por Traefik** (C-15). catalog envía `X-Correlation-ID` en esa llamada, así que su log se cruza con el evento.
* **El 500 de una excepción no controlada sale sin `X-Correlation-ID`** (C-05).
