# Guía Técnica del Módulo 3: Reservas & Cupos

**booking-service: cupos en tiempo real y ciclo de vida de la reserva** · Plataforma Digital de Turismo, Santa Marta

> Documento de trabajo interno del equipo (guion de implementación). El nivel de detalle de arquitectura vive en el [Plan de Implementación](./Plan_de_Implementacion.md) y los requerimientos en el [SRS](./Requirements_docIEEE.md); si algo cambia, se actualiza primero allí. El contrato REST acordado está en [`contracts/openapi/booking.yaml`](../../contracts/openapi/booking.yaml).

## 1. Propósito

Permitir que el turista consulte cupos y solicite reservas sin sobreventa, y que el prestador administre su calendario y responda las solicitudes (RF-03, RF-04, RF-05; UC10, UC11, UC12, UC13, UC19, UC20).

El módulo es el **dueño de los cupos y del estado de cada reserva**. Los demás módulos se enteran de lo que pasa mediante eventos (`reserva.*`) y nunca leen `booking_db`.

## 2. Principios

* **Nunca sobrevender.** Todo cambio de cupos ocurre dentro de una transacción con bloqueo de la fila de disponibilidad (Plan §2.3).
* **La máquina de estados manda.** Solo se permiten las transiciones de la §4; cualquier otra responde HTTP 409 (RF-04).
* **Sin pagos.** El módulo no cobra ni retiene dinero (SRS §1.2.1); las reglas de cancelación no generan penalidades económicas.
* **Identidad controlada por el servidor.** El turista o prestador sale del encabezado `X-Usuario-Id` que agrega Traefik tras validar el JWT; nunca del cuerpo de la petición.
* **Eventos después del `COMMIT`.** Un evento solo se publica cuando la transacción ya se confirmó; nunca se anuncia algo que pudo deshacerse.
* **Requiere conexión.** Solicitar, modificar, cancelar, confirmar y rechazar reservas dependen de cupos en tiempo real (SRS §3.6.6). Solo el calendario del prestador (UC19) se puede editar sin conexión.

## 3. Alcance

**Incluye:**
* consulta pública de disponibilidad por servicio y rango de fechas (UC10);
* solicitud, modificación y cancelación de reservas por el turista (UC11, UC12) y su historial (UC13);
* calendario de cupos y tarifa del día del prestador (UC19);
* panel de solicitudes del prestador: confirmar, rechazar y cancelar (UC20);
* expiración automática de solicitudes sin respuesta y finalización de reservas vencidas;
* publicación de los eventos `reserva.*`, `disponibilidad.actualizada` y `auditoria.registrada`.

**No incluye:** pagos ni depósitos, envío de correos (lo hace el Módulo 2 al consumir los eventos), reseñas, listas de espera ni reservas por horas (la unidad es el día).

## 4. Máquina de estados y reglas de negocio

![Máquina de estados de la reserva](./Diagrama_Maquina_Estados_Reserva.svg)

| Transición | Quién | Condición | Cupos | Evento |
|---|---|---|---|---|
| (inicio) → `SOLICITADA` | Turista (UC11) | Cupos suficientes; fecha a partir de mañana | Descuenta | `reserva.solicitada` |
| `SOLICITADA` → `SOLICITADA` (modificación) | Turista (UC12) | Ver §4.2 | Ajusta | `reserva.modificada` |
| `SOLICITADA` → `CONFIRMADA` | Prestador dueño (UC20) | Antes de `expira_en` | — | `reserva.confirmada` |
| `SOLICITADA` → `RECHAZADA` | Prestador dueño (UC20) | Motivo obligatorio | Libera | `reserva.rechazada` |
| `SOLICITADA` → `RECHAZADA` | Sistema | Venció `expira_en` | Libera | `reserva.rechazada` (motivo: plazo vencido) |
| `SOLICITADA` → `CANCELADA` | Turista (UC12) | Siempre | Libera | `reserva.cancelada` |
| `CONFIRMADA` → `CANCELADA` | Turista (UC12) | Hasta el día anterior a la reserva (§4.3) | Libera | `reserva.cancelada` |
| `CONFIRMADA` → `CANCELADA` | Prestador dueño | Siempre, con motivo obligatorio | Libera | `reserva.cancelada` |
| `CONFIRMADA` → `FINALIZADA` | Sistema | Ya pasó `fecha_reserva` | — | `reserva.finalizada` |

Todas las horas se calculan en la zona horaria `America/Bogota`. La unidad de reserva es el **día** (`fecha_reserva`), igual que en el modelo de datos (SRS §3.7).

### 4.1 Solicitud (UC11)

* `numero_personas` entre 1 y `cupos_totales` del día.
* `fecha_reserva` debe ser al menos **mañana**. Así el prestador siempre tiene tiempo para responder.
* **Plazo de respuesta:** `expira_en = mín(ahora + 48 h, 00:00 del día de la reserva)`. Una solicitud para pasado mañana vence a medianoche de mañana, no después de la fecha del servicio.
* Un turista no puede tener dos reservas activas (`SOLICITADA` o `CONFIRMADA`) para el mismo servicio y la misma fecha; en ese caso debe modificar la que ya tiene (HTTP 409 `RESERVA_DUPLICADA`).
* La petición acepta `Idempotency-Key` para que un doble clic o un reintento de red no cree dos reservas (§6.3).

### 4.2 Modificación (UC12)

* Solo en estado `SOLICITADA` (SRS §3.6.1); en cualquier otro estado, HTTP 409.
* Se pueden cambiar **el número de personas, la fecha o ambos**.
* Si cambia la fecha, se bloquean las dos filas de disponibilidad (la antigua y la nueva) en orden ascendente de fecha, se liberan los cupos de la antigua y se descuentan los de la nueva en la misma transacción.
* Como el prestador recibe en la práctica una solicitud distinta, **el plazo de respuesta se reinicia** con la regla de la §4.1.
* La modificación usa `If-Match` con la versión de la reserva para no pisar un cambio simultáneo (por ejemplo, una confirmación que llegó mientras el turista editaba).

### 4.3 Cancelación

* **Turista, reserva `SOLICITADA`:** siempre.
* **Turista, reserva `CONFIRMADA`:** hasta las 23:59 del día anterior a `fecha_reserva`. El modelo de datos maneja días, no horas, así que la regla de "24 horas antes" se expresa como "hasta el día anterior". Pasado ese límite responde HTTP 409 `FUERA_DE_PLAZO` y la interfaz sugiere contactar al prestador.
* **Prestador, reserva `CONFIRMADA`:** siempre, con motivo obligatorio (clima, cierre del parque, alerta oficial, etc.). El motivo viaja en `reserva.cancelada` y llega al turista en el correo.
* Esta es la **regla base de la plataforma** y es la que aplica el servicio. La `politica_cancelacion` que cada prestador publica en su perfil (Módulo 2, UC9) es informativa: puede ser más flexible, pero no más restrictiva que la regla base.
* Catalog muestra esta regla en la ficha del servicio (UC9) como `regla_base_cancelacion`, copiada de esta sección. **Si la regla cambia, hay que avisarle a catalog (@luifdo) para que actualice el texto.**

### 4.4 Calendario del prestador (UC19)

* Cada fila de `DISPONIBILIDAD_CUPO` representa un servicio en un día: `cupos_totales`, `cupos_disponibles` y una `tarifa_dia` opcional. Si la tarifa del día es nula, aplica la `tarifa_base` del catálogo.
* El prestador puede abrir un rango de días de una vez (por ejemplo, "lunes a sábado de noviembre, 20 cupos") o editar un día puntual.
* Reducir `cupos_totales` por debajo de lo ya reservado (`cupos_totales - cupos_disponibles`) responde HTTP 409 `CUPOS_COMPROMETIDOS`; primero hay que rechazar o cancelar reservas.
* Solo el prestador dueño del servicio, según la proyección `servicio_ref` (§8), gestiona su calendario. Si el servicio no está en la proyección, está inactivo o es de otro prestador, responde 404.
* `cupos_totales` no puede superar la `capacidad_aforo_diario` oficial del servicio (capacidad de carga, §2.4.4 del SRS), que también llega en `servicio_ref`.
* Cerrar un día es poner `cupos_totales` en lo ya reservado; no se borran filas que tengan reservas.
* Es un formulario que la PWA puede enviar sin conexión (RNF-13, ESC-09): acepta `Idempotency-Key` y usa `If-Match` con la versión de la fila para detectar conflictos (Plan §6.8).

## 5. Arquitectura

* **Lenguaje y framework:** Python 3.12 con FastAPI y SQLAlchemy 2 (asíncrono), con la estructura hexagonal de la plantilla del monorepo.
* **Despliegue:** Deployment en k3s con 2 réplicas mínimas y HPA hasta 6 (Plan §7.3). El bloqueo por fila permite escalar sin perder consistencia, porque la exclusión la garantiza PostgreSQL y no la memoria de una réplica.
* **Tareas programadas:** dos `CronJob` de Kubernetes que usan la misma imagen del servicio con otro comando (§6.4).
* **Persistencia:** base lógica `booking_db` en el clúster CloudNativePG, con usuario propio.
* **Valkey:** solo para las claves de idempotencia de las peticiones (`idem:booking:{key}`, TTL de 48 h).
* **RabbitMQ al arrancar:** booking declara su cola durable `booking.servicios` y la enlaza a la clave `servicio.publicado` del exchange `turismo.eventos`. Tiene que existir antes de que catalog publique, porque RabbitMQ descarta los mensajes que no tienen una cola enlazada.
* **Consumo de `servicio.publicado.v1`:** se valida el sobre y el payload contra el contrato. Un mensaje inservible (JSON roto, otro tipo o versión, payload fuera de contrato) va directo a la DLQ; un fallo pasajero se reintenta a los 1, 5 y 25 s (colas `booking.servicios.reintento.<espera>`, cabecera `x-intentos`) y, si sigue fallando, va a `turismo.dead-letter` con la cola, los intentos y el error. Es la misma convención y la misma DLX (`turismo.dlx`, tipo topic) que declara catalog. No hace falta deduplicar por `event_id` en Valkey: el evento trae el estado completo con su `version` y solo se aplica si es mayor (§8).
* **Endpoints:** resumen en la §7; detalle en [`booking.yaml`](../../contracts/openapi/booking.yaml).
* **Configuración:** `DB_URL`, `VALKEY_URL`, `RABBITMQ_URL`, `EVENTS_EXCHANGE`, `TZ=America/Bogota`, `PLAZO_RESPUESTA_HORAS=48`.

### 5.1 Capas

| Capa | Contenido |
|---|---|
| `domain/` | Entidades `Reserva` y `DisponibilidadCupo`, enum `EstadoReserva`, reglas de la §4 y errores de dominio (`TransicionInvalida`, `CuposInsuficientes`, `FueraDePlazo`). Sin FastAPI ni SQLAlchemy. |
| `application/` | Un caso de uso por clase: `SolicitarReserva`, `ModificarReserva`, `CancelarReserva`, `ConfirmarReserva`, `RechazarReserva`, `ExpirarSolicitudes`, `FinalizarReservas`, `GestionarCalendario`, `ConsultarDisponibilidad`, `ConsultarHistorial`. |
| `application/ports/` | `RepositorioReservas`, `RepositorioDisponibilidad`, `UnidadDeTrabajo`, `PublicadorEventos`, `AlmacenIdempotencia`, `Reloj` (para probar plazos sin esperar). |
| `infrastructure/` | Routers FastAPI, repositorios SQLAlchemy, publicador aio-pika y consumidor de `servicio.publicado` para la proyección `servicio_ref` (§8). |

## 6. Concurrencia y consistencia

### 6.1 Bloqueo de cupos

Toda operación que mueve cupos sigue el mismo patrón dentro de una transacción (Plan §6.3):

```sql
SELECT cupos_disponibles FROM disponibilidad_cupo
WHERE servicio_id = $1 AND fecha = $2
FOR UPDATE;
-- validar en dominio y luego:
UPDATE disponibilidad_cupo SET cupos_disponibles = cupos_disponibles - $3, secuencia = secuencia + 1 ...;
```

* Mover cupos no sube la `version` del día. La `version` solo cambia cuando el prestador edita los cupos totales o la tarifa (UC19); así una reserva no provoca un conflicto falso cuando la PWA sincroniza una edición hecha sin conexión (ESC-09).
* La fila lleva además una `secuencia`, que sube con **cada** cambio (reservas y ediciones del prestador). Es la que viaja como `version` en `disponibilidad.actualizada` (§6.5), porque catalog descarta los eventos con un número menor o igual al que ya tiene y necesita ver también los cambios por reservas.

* Cuando se bloquean dos filas (modificación con cambio de fecha), se bloquean **siempre en orden ascendente de fecha** para evitar interbloqueos (*deadlocks*).
* Restricción en la base: `CHECK (cupos_disponibles BETWEEN 0 AND cupos_totales)`, como segunda barrera si el código fallara.
* Nivel de aislamiento `READ COMMITTED` (el predeterminado); el `FOR UPDATE` es el que serializa el acceso a cada fila.

### 6.2 Transiciones sin carreras

Las transiciones se aplican con una actualización condicionada al estado actual, de modo que una confirmación del prestador y la expiración automática no pueden ganar las dos:

```sql
UPDATE solicitud_reserva
SET estado = 'CONFIRMADA', version = version + 1, actualizado_en = now()
WHERE id = $1 AND prestador_usuario_id = $2 AND estado = 'SOLICITADA' AND expira_en > now()
RETURNING *;
```

Si no devuelve filas, el servicio consulta el estado actual y responde 404 (no existe o no es del prestador) o 409 (ya cambió de estado o venció).

### 6.3 Idempotencia de peticiones

* `POST /api/bookings` y los formularios del calendario aceptan `Idempotency-Key`.
* La primera respuesta se guarda en Valkey (`idem:booking:{usuario_id}:{key}`, 48 h); un reintento con la misma clave devuelve la misma respuesta sin repetir la operación.
* Las transiciones (`confirmar`, `rechazar`, `cancelar`) ya son idempotentes por la §6.2: repetirlas devuelve 409 con el estado actual, sin efectos.

### 6.4 Tareas programadas

| CronJob | Frecuencia | Qué hace |
|---|---|---|
| `expirar-solicitudes` | Cada 15 min | `SOLICITADA` con `expira_en < now()` → `RECHAZADA` (motivo "Plazo de respuesta vencido"); libera cupos. |
| `finalizar-reservas` | Cada 15 min | `CONFIRMADA` con `fecha_reserva < hoy` → `FINALIZADA`. |

* Procesan en lotes de 100 con `FOR UPDATE SKIP LOCKED`, de modo que no chocan con las peticiones de los usuarios.
* `concurrencyPolicy: Forbid` evita dos ejecuciones simultáneas del mismo CronJob.
* Los eventos de cada lote se guardan en el outbox dentro de la transacción del lote (§6.5).

### 6.5 Publicación de eventos

* **`disponibilidad.actualizada`** (acordado con @luifdo el 23 de octubre): cada vez que cambia una fila de disponibilidad se publica el **estado completo del día** (`servicio_id`, `fecha`, `cupos_totales`, `cupos_disponibles` y `version` = `secuencia`), no la diferencia. Sale al solicitar, modificar, rechazar, cancelar o expirar, y cuando el prestador abre o edita su calendario. Un día cerrado sale con `cupos_totales = 0`. Si una operación toca un día varias veces (un lote del CronJob), sale un solo evento con el estado final. Confirmar y finalizar no mueven cupos, así que no lo publican. Catalog lo usa solo para filtrar la búsqueda y el mapa por fecha: el cupo lo sigue garantizando el bloqueo al reservar.
* **Patrón outbox (adoptado en el Sprint 5):** los eventos se guardan en la tabla `evento_outbox` **en la misma transacción** que el cambio que los produjo, así no puede quedar una reserva creada cuyo evento se perdió porque el proceso se cayó justo después del `COMMIT` (el riesgo que el ADR-008 dejaba aceptado; aquí el impacto era alto, porque `reserva.finalizada` habilita la reseña y `reserva.confirmada` dispara el correo).
* **Relay:** una tarea de fondo en cada réplica toma los pendientes en orden, de a 100, con `FOR UPDATE SKIP LOCKED` (dos réplicas nunca toman el mismo), los publica con *publisher confirms* y mensajes persistentes, y marca `publicado_en`. Si RabbitMQ no confirma, suma un intento, guarda el error, corta el lote para no desordenar y reintenta en la siguiente vuelta; desde el tercer intento fallido deja un registro de nivel error (Plan §4.3). Si RabbitMQ está caído, booking sigue atendiendo y los eventos esperan en el outbox.
* **Al menos una vez:** si el relay se cae después de publicar y antes de marcar, el evento sale de nuevo. Cada mensaje lleva `message_id` = `event_id` para que los consumidores lo descarten.

## 7. Endpoints

Prefijo en Traefik: `/api/bookings`. Errores con el formato común `{ "error", "message", "correlation_id" }`.

| Método y ruta | Rol | Caso de uso | Notas |
|---|---|---|---|
| `GET /disponibilidad?servicio_id&desde&hasta` | Público | UC10 | Rango máximo de 62 días. La usa la tool `consultar_disponibilidad` del Módulo 5. |
| `POST /` | Turista | UC11 | `Idempotency-Key`. Responde 201 con la reserva en `SOLICITADA`. |
| `GET /mis-reservas?estado` | Turista | UC13 | Paginado. La usa la tool `historial_turista` del Módulo 5. |
| `GET /{id}` | Turista o prestador dueño | UC13, UC20 | 404 si no es suya. |
| `PATCH /{id}` | Turista | UC12 | `If-Match`. Fecha y/o número de personas. |
| `POST /{id}/cancelar` | Turista o prestador dueño | UC12 | Motivo obligatorio para el prestador. |
| `POST /{id}/confirmar` | Prestador dueño | UC20 | |
| `POST /{id}/rechazar` | Prestador dueño | UC20 | Motivo obligatorio. |
| `GET /prestador/solicitudes?estado&servicio_id&desde&hasta` | Prestador | UC20 | Panel del prestador; por defecto, las `SOLICITADA` ordenadas por `expira_en`. |
| `GET /prestador/calendario/{servicio_id}?desde&hasta` | Prestador dueño | UC19 | Días con totales, disponibles, reservados, tarifa y versión. |
| `POST /prestador/calendario/{servicio_id}/rango` | Prestador dueño | UC19 | Abre varios días. `Idempotency-Key`. Omite los días que ya existen. |
| `PUT /prestador/calendario/{servicio_id}/{fecha}` | Prestador dueño | UC19 | Crea o edita un día. `If-Match` para editar. |
| `GET /health`, `GET /metrics` | Interno | — | Sondas de Kubernetes y Prometheus. |

## 8. Datos

Nivel arquitectónico; el DDL detallado se escribe en la Fase 4 (Plan §5).

* **`servicio_ref`** (proyección local): `servicio_id`, `prestador_id`, `prestador_usuario_id`, `capacidad_aforo_diario`, `tarifa_base`, `activo`, `version`. La alimenta el evento `servicio.publicado.v1` de catalog-service (cola `booking.servicios`); se aplica solo si su `version` es mayor que la guardada, así un mensaje viejo o repetido no pisa uno nuevo. Permite validar al dueño, el aforo y si el servicio está activo sin llamar al Módulo 2.
* **`disponibilidad_cupo`**: `id`, `servicio_id`, `fecha`, `cupos_totales`, `cupos_disponibles`, `tarifa_dia` (nula = `tarifa_base` de `servicio_ref`), `version` (ediciones del prestador, `ETag`) y `secuencia` (cada cambio, evento a catalog). Única por (`servicio_id`, `fecha`). El dueño sale de `servicio_ref`.
* **`solicitud_reserva`**: `id`, `turista_id`, `servicio_id`, `prestador_id`, `prestador_usuario_id`, `fecha_reserva`, `numero_personas`, `estado`, `expira_en`, `motivo`, `cancelada_por`, `version`, `creado_en`, `actualizado_en`. Los dos ids del prestador se copian de `servicio_ref` al solicitar. Índices por (`turista_id`, `estado`), (`prestador_usuario_id`, `estado`, `expira_en`) y (`estado`, `fecha_reserva`) para los CronJobs.
* **Ids de usuario y de perfil:**
  * `turista_id` y `prestador_usuario_id` son ids de usuario de iam-service, los mismos de `X-Usuario-Id`. Con ellos se decide quién puede ver y cambiar cada reserva.
  * `prestador_id` es el id del **perfil** del prestador en el catálogo. Es el que viaja en los eventos `reserva.*` y en las respuestas de la API.
* Si un servicio pasa a inactivo (lo desactiva el prestador o iam suspende al prestador), no acepta solicitudes nuevas ni cambios de calendario. Las solicitudes pendientes siguen su curso: el prestador las responde o vencen a las 48 h.

## 9. Seguridad y auditoría

* RBAC por endpoint con `X-Usuario-Rol` (`Turista`, `Prestador`); un rol incorrecto responde 403 y publica `auditoria.registrada` con `accion = ACCESS_DENIED`.
* Un prestador solo ve y gestiona reservas y calendarios de sus propios servicios (filtro por `prestador_usuario_id` en la consulta, no después).
* Cada cambio de estado publica `auditoria.registrada` (`RESERVA_SOLICITADA`, `RESERVA_CONFIRMADA`, `RESERVA_CANCELADA`, etc.) con el usuario, el `reserva_id` y el `correlation_id` (Plan §4.4).
* Los eventos solo llevan identificadores; el correo y el nombre del turista no se guardan en `booking_db`.

## 10. Pruebas

* **Unitarias del dominio:** todas las transiciones válidas e inválidas de la §4, cálculo de `expira_en` en los bordes (solicitud para mañana, para dentro de 2 días, cambio de día a medianoche) y la regla de cancelación del día anterior, con un `Reloj` simulado.
* **Concurrencia (la más importante):** 50 turistas solicitan a la vez el último cupo; debe haber exactamente 1 reserva creada, 49 respuestas 409 y `cupos_disponibles = 0`. Se repite con confirmación del prestador contra expiración simultánea.
* **Interbloqueo:** dos modificaciones cruzadas (A pasa de día 1 a día 2 y B de día 2 a día 1) terminan sin *deadlock*.
* **Idempotencia:** la misma `Idempotency-Key` enviada dos veces crea una sola reserva; el calendario enviado sin conexión se sincroniza sin duplicados (ESC-09).
* **Integración con `pytest`:** PostgreSQL y RabbitMQ reales en contenedores (Testcontainers); se verifica que cada transición publica su evento con el esquema de `contracts/events/`.
* **Contrato:** el `/openapi.json` que genera FastAPI se compara con `booking.yaml`.
* **Carga (ESC-08):** escenario k6 de solicitudes sobre pocos servicios y fechas populares para medir la contención del bloqueo con el HPA activo.
* **Recuperación (ESC-06):** simulacro de restauración de `booking_db` con RTO ≤ 30 min.

## 11. Qué se necesita de los demás módulos

* **catalog (acordado con @luifdo):** publica `servicio.publicado.v1` al crear, editar, desactivar o reactivar un servicio y al suspender o rehabilitar a su prestador, con los dos ids del prestador, el aforo, la tarifa base, `activo` y `version`. booking lo consume para `servicio_ref`.
* **catalog (disponibilidad):** consume `disponibilidad.actualizada` en su propia proyección para filtrar `/buscar` y el mapa por fecha y personas, sin llamar a booking (Plan §4.1). Si un día aún no tiene evento, lo muestra como "disponibilidad sin confirmar".
* **catalog (consumidor) — listo:** consume todos los `reserva.*`, incluido `reserva.modificada`, en la cola `catalog.demanda`. Guarda el estado de cada reserva en su proyección `reserva_proyeccion` y suma por día; ya no usa contadores en una tabla `demanda_diaria`, porque un evento repetido o desordenado descuadraba el total. La regla base de cancelación ya sale en la ficha (UC9).
* **catalog (correos):** en su paso 16 avisa al prestador cuando se modifica una reserva e incluye el `motivo` en los correos de rechazo y cancelación. Para eso, `reserva.rechazada` y `reserva.cancelada` **tienen que seguir trayendo `motivo`** como dice el contrato.
* **review:** sin cambios; consume `reserva.finalizada` como está.
* **recommendation:** usar `GET /disponibilidad` y `GET /mis-reservas`; ambos ya existen en este contrato.
* **iam:** `X-Usuario-Rol` con los valores `Turista` y `Prestador`, y el id de usuario en `X-Usuario-Id`.
* **gateway (Traefik):** `GET /api/bookings/disponibilidad` público y el resto con ForwardAuth (Plan §4.1).
* **frontend:**
  * flujo de solicitud en 4 pasos (RNF-11);
  * botones de reservar, modificar, cancelar, confirmar y rechazar deshabilitados sin conexión, con la explicación;
  * calendario del prestador editable sin conexión;
  * mostrar el plazo de respuesta (`expira_en`) al turista y al prestador.
