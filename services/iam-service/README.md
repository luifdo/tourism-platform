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

**Publica:**
* `prestador.aprobado.v1`

**Consume:**
* `auditoria.registrada.v1` (de catalog, booking y review)

Esquemas en [`contracts/events/`](../../contracts/events/).

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
    ├── routers/
    ├── schemas/         # modelos Pydantic de request/response
    └── dependencies.py  # cableado de casos de uso con sus adaptadores
migrations/              # Alembic (async)
tests/
```

## Ejecución

Requiere [uv](https://docs.astral.sh/uv/) y Python 3.12.

```bash
uv sync                                   # instala dependencias (incluye dev)
cp .env.example .env                      # ajustar DATABASE_URL y demás
uv run python -m uvicorn app.main:app --reload --port 8001
uv run pytest                             # pruebas (las marcadas db se omiten si PostgreSQL no responde)
uv run ruff check . && uv run ruff format --check .
uv run alembic upgrade head               # aplicar migraciones
```

> En Windows, Smart App Control puede bloquear `uvicorn.exe` del `.venv`; `python -m uvicorn` evita el problema.

## Endpoints

Operativos:

* `GET /health`: `200` si PostgreSQL responde a `SELECT 1`, `503` si no.
* `GET /metrics`: métricas Prometheus (prometheus-fastapi-instrumentator).

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
  "es_mayor_de_edad": true
}
```

`201 Created`: nunca incluye la contraseña ni su hash.

```json
{
  "id": "8fa88503-29e2-4ff7-b47e-bc22f8856bce",
  "email": "maria.perez@example.com",
  "nombre_completo": "María Pérez",
  "rol": "Turista",
  "email_verificado": false,
  "creado_en": "2026-10-23T07:17:49.145181Z"
}
```

Errores, con cuerpo `{"detail": "<mensaje>", "code": "<code>"}`:

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
| 403 | `ROL_INSUFICIENTE` | El rol del token no está en la lista | `{"rol", "requeridos", "metodo", "ruta", "plantilla"}`; `plantilla` es la ruta declarada (p. ej. `/api/iam/admin/usuarios/{id}`) para agrupar por endpoint |

`GET /api/iam/admin/ping` (solo `Admin`, responde `{"ok": true}`) es **temporal**: existe para probar el RBAC hasta que estén los endpoints de administración.

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
