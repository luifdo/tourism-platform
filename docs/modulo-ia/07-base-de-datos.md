# Base de datos

> Módulo 5 · [Índice](./README.md)

`recommendation_db` tiene una sola tabla, `recomendacion_log` (SRS, modelo de datos):

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | uuid, PK | Identificador del registro. |
| `conversacion_id` | uuid | Sesión del chatbot. |
| `turista_id` | uuid | Viene del encabezado `X-Usuario-Id`. |
| `servicio_id` | uuid | Servicio recomendado (referencia lógica a `catalog_db`; sin llave foránea entre bases). |
| `justificacion` | texto | Motivo mostrado al turista (RNF-08). |
| `herramientas_usadas` | jsonb | Tools que se consultaron. |
| `modelo` | texto | Proveedor y versión del modelo que generó la respuesta. |
| `fecha_generacion` | timestamp | Marca temporal. |

No se guarda el texto de las conversaciones (privacidad, Ley 1581).

En nuestro compose, la imagen de PostgreSQL crea la base a partir de `POSTGRES_DB` y el script [`db/01-recomendacion-log.sql`](../../services/recommendation-service/db/01-recomendacion-log.sql), montado en `docker-entrypoint-initdb.d`, crea la tabla y sus índices (`conversacion_id`, `turista_id`). Solo se ejecuta la primera vez que se crea el volumen: si el script cambia, hay que borrar el volumen con `docker compose down -v`. Más adelante se puede sustituir por migraciones (Alembic). `recommendation_db` ya está en `infra/postgres/init/01-create-databases.sql` (la agregó @luifdo en `develop`), así que al integrar con el resto no hay que añadirla. La tabla `recomendacion_log` sí la creamos nosotros.

Además de los tipos, la tabla rechaza justificaciones vacías (`CHECK`), como segunda barrera de RNF-08 después del dominio.

El esquema es interno del servicio y puede ampliarse (por ejemplo, latencia, tokens consumidos, proveedor aparte, o separar conversación y recomendación). Si cambia, se actualizan el modelo de datos del SRS y la tabla del Plan. En la Fase 1 se dejó tal como está en el SRS.

## Sesiones en Valkey

Cada conversación es una llave `recommendation:conversacion:<conversacion_id>` con un JSON que guarda el turista dueño y sus últimos 10 mensajes (`turista` o `asistente`). Dura 24 horas y cada mensaje nuevo renueva el plazo. Guardar el turista permite responder 404 si otro turista intenta continuar esa conversación (contrato, `ConversacionNoEncontrada`).

---
[← Variables de entorno](./06-variables-entorno.md) · [Simulación y proveedor de IA →](./08-simulacion.md)
