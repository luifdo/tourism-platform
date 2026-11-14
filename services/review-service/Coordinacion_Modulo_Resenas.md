# Coordinación con el Módulo 4: Reseñas & Moderación

**Qué espera review-service de los demás módulos** · Plataforma Digital de Turismo, Santa Marta

> Documento de trabajo interno del equipo. Lista lo que review-service (Módulo 4) necesita de cada módulo para funcionar completo en el clúster, y lo que ofrece a cambio. Los contratos de [`contracts/`](../../contracts/) mandan: si algo de aquí no coincide con un contrato, vale el contrato y se corrige este documento. Responsable del Módulo 4: Luis Fernando Barraza Sanchez (@luifdo).

## 1. Estado del Módulo 4

review-service está terminado para el prototipo: API REST completa según [`review.yaml`](../../contracts/openapi/review.yaml) (UC15, UC21, UC29 y UC39), worker de eventos, despliegue en compose y en Kubernetes, y pruebas de contrato. La prueba del escenario ESC-01 está lista y queda por medir en el clúster del equipo (ver el punto 12). Detalle técnico y guía de uso en el [README del servicio](./README.md).

Review **no llama a ningún otro servicio por REST** y nadie lo llama en el camino crítico (ESC-01): todo lo que necesita de los demás le llega por eventos. Si un módulo todavía no existe, review no se cae; solo le falta ese dato (ver la columna "Si no está").

## 2. Resumen

| Módulo | Responsable | Lo más importante | Si no está |
|---|---|---|---|
| booking-service | Andrés (@AFGamero) | Publicar `reserva.finalizada`; desplegarse después del worker de review | Nadie puede reseñar (403 `NO_ELEGIBLE`) |
| catalog-service | Luis Fernando (@luifdo) | `servicio.publicado` con `prestador_usuario_id` y `version` (ya lo hace); consumir `resena.*` (ya lo hace) | Los prestadores no pueden responder ni su reporte cuenta como del dueño; el promedio del catálogo no cambia |
| iam-service | Valentina (@nievesita) | Cola `iam.auditoria`; valores de `X-Usuario-Rol` | La auditoría de review (accesos denegados y moderación) se pierde |
| Gateway (Traefik) | Juan Francisco (@JuanFranG) | `/api/reviews` sin quitar el prefijo; 3 rutas públicas; ForwardAuth; encabezados de identidad e IP | Review no es accesible desde fuera del clúster |
| Frontend (PWA) | Juan Francisco (@JuanFranG) | Mostrar el texto de los usuarios como texto; `Idempotency-Key`, `ETag`/`If-Match`, `Retry-After` | — |
| recommendation-service | Alvaro (@alvaroospino) | La tool `resenas_servicio` usa las rutas públicas; etiqueta de sus pods | El chatbot no puede citar reseñas |
| Observabilidad (`infra/`) | Juan Francisco (@JuanFranG) | Prometheus en `observabilidad` con su etiqueta estándar | No se ven las métricas de review |

## 3. Reglas comunes de los eventos

Las mismas del [documento de catalog](../catalog-service/Coordinacion_Modulo_Catalogo.md#3-reglas-comunes-de-los-eventos), en corto:

* **Sobre común** `envelope.v1.json` y payload según su esquema. Review valida cada evento que consume: uno que no cumple va directo a `turismo.dead-letter`, sin reintentos.
* **`event_id` estable** en los reintentos del productor: review descarta los repetidos por ese campo (`evento_procesado`, guardado 30 días).
* **Publicar después del `COMMIT`**, idealmente con outbox (review y catalog lo hacen).
* **El orden de llegada no importa:** review se queda con la visita más reciente y con la `version` mayor de cada servicio.
* **Cambiar un esquema se coordina:** las pruebas de review validan contra `contracts/events/` lo que imitan de booking y catalog, y lo que el propio review publica.
* **Topología:** exchange `turismo.eventos` (topic). Review declara sus colas `review.elegibilidad` y `review.servicios`.

### Orden de despliegue

RabbitMQ **descarta** un mensaje si ninguna cola está enlazada a su clave. Por eso el **worker de review se despliega antes o junto con catalog y booking**: si catalog publicara servicios o booking finalizara reservas antes de que existan las colas de review, esos eventos se perderían para review. Una vez declaradas, las colas son durables y guardan los mensajes aunque el worker esté caído: el riesgo existe solo en el primer despliegue. En una plataforma nueva no hay datos previos.

## 4. booking-service (Módulo 3)

**Andres Felipe Gamero Sanchez (@AFGamero)**

1. **Publicar `reserva.finalizada`** según su esquema cuando pase la fecha de una reserva confirmada. Review usa `turista_id`, `servicio_id` y `fecha_reserva`: con ese evento el turista puede reseñar el servicio (RF-14) y el servicio aparece en sus pendientes. Sin él, toda reseña responde 403 `NO_ELEGIBLE`.
2. **`fecha_reserva` es la fecha de la visita:** de ahí sale el mes que muestra la reseña ("Turista verificado · noviembre de 2026").
3. **Desplegar después del worker de review** (o a la vez) la primera vez, por el orden de despliegue de arriba.

## 5. catalog-service (Módulo 2)

**Luis Fernando Barraza Sanchez (@luifdo)** — ya cumple todo; queda como referencia.

1. **`servicio.publicado`** siempre con `prestador_usuario_id` (el id del usuario que llega en `X-Usuario-Id`) y `version`. Review lo usa para saber quién es dueño de cada servicio: solo él responde sus reseñas (UC21) y su reporte las pasa a revisión (UC39). Review ignora `activo`: un servicio desactivado conserva sus reseñas y su dueño.
2. **Consumir `resena.publicada` y `resena.ocultada`** (cola `catalog.calificaciones`) para el promedio de cada servicio. Review publica `resena.publicada` al crear, editar y volver a publicar desde `OCULTA`, y `resena.ocultada` al ocultar; mientras una reseña está `EN_REVISION`, su nota sigue contando y no se publica nada. `occurred_at` es el momento real del cambio.
3. **Desplegar después del worker de review** (o a la vez) la primera vez.

## 6. iam-service (Módulo 1)

**Valentina Sarait Nieves Hernandez (@nievesita)**

1. **Cola de auditoría:** la misma cola durable `iam.auditoria` enlazada a `auditoria.registrada` que pide catalog. Review publica:
   * `ACCESS_DENIED` (resultado `DENEGADO`) en cada 403 por rol (`ROL_NO_PERMITIDO`) y cuando un turista intenta reseñar sin reserva finalizada (`NO_ELEGIBLE`). `detalles` lleva `motivo`, `rol`, `roles_permitidos` o `servicio_id`, `metodo` y `ruta`; `ip_origen` sale de `X-Forwarded-For`;
   * `MODERACION` (resultado `EXITO`) en cada decisión del Administrador (UC29), también cuando no cambia nada. `detalles` lleva `resena_id`, `servicio_id`, `decision`, `motivo`, `estado_anterior`, `estado_nuevo` y `reportes_resueltos`.
2. **Roles en `X-Usuario-Rol`:** exactamente `Turista`, `Prestador`, `Entidad` y `Admin`. En review escribe y edita el `Turista`; responde el `Prestador`; reportan los dos; modera el `Admin`. La `Entidad` no tiene rutas propias en review.

## 7. Gateway: Traefik

**Juan Francisco (@JuanFranG)**

1. **Ruta `/api/reviews` hacia `review-service:8004` sin StripPrefix:** el servicio atiende bajo `/api/reviews/...`, igual que catalog bajo `/api/catalog`.
2. **Públicas (sin ForwardAuth):** `GET /api/reviews/servicios/{id}/resenas`, `GET /api/reviews/servicios/{id}/resumen` y `GET /api/reviews/resenas/{id}`. Todo lo demás pasa por ForwardAuth, también las lecturas de `/turista`, `/prestador` y `/moderacion` (detalle por operación en `review.yaml`: `security: []` = pública).
3. **Encabezados:** borrar las `X-Usuario-*` que mande el cliente y poner las de iam; reenviar `X-Correlation-ID` y `X-Forwarded-For`, sin confiar en uno que venga de fuera (`forwardedHeaders.trustedIPs` sin rangos públicos): review toma el primer IP para la auditoría.
4. **Etiqueta de Traefik:** la NetworkPolicy de review deja entrar a los pods de `kube-system` con `app.kubernetes.io/name: traefik` (la de k3s), por el 8004.

## 8. Frontend (PWA)

**Juan Francisco (@JuanFranG)**

1. **El texto de los usuarios se muestra como texto, nunca como HTML** (comentario de la reseña, respuesta del prestador, detalle del reporte). Review lo guarda tal cual, sin quitar etiquetas: "precio < 50 mil" es un texto legítimo. Mostrarlo como HTML abriría un XSS.
2. **Autor anónimo:** la API ya devuelve "Turista verificado" (o "Verified tourist") y el mes de la visita; no hay nombre ni foto que mostrar.
3. **`Idempotency-Key`** (un UUID por intento) en `POST /resenas`, para el envío diferido sin conexión (RNF-13): un reintento devuelve la misma respuesta con `Idempotent-Replayed: true`.
4. **`ETag` / `If-Match`** al editar la reseña, responderla y moderarla. Un 409 `VERSION_DISTINTA` trae el `ETag` actual: recargar y volver a intentar.
5. **429 `DEMASIADOS_REPORTES`:** respetar `Retry-After` (segundos) antes de dejar reportar otra vez; el límite es de 10 reportes por hora.
6. **Pendientes:** `GET /turista/pendientes` da solo `servicio_id` y `ultima_visita`; el nombre del servicio se toma del catálogo.
7. **Etiquetas:** estados, aspectos y motivos llegan con su etiqueta en el idioma de `Accept-Language` (`*_etiqueta`, `aspectos_etiquetas`); no hace falta traducirlos en la PWA.
8. **Mensajes al usuario:** una reseña reportada sigue visible; pasa a "En revisión" (oculta al público) al tercer reporte o con el del prestador dueño. El autor la sigue viendo en "Mis reseñas" con su estado.

## 9. recommendation-service (Módulo 5)

**Alvaro (@alvaroospino)**

1. **Tool `resenas_servicio`:** usar las rutas públicas `GET /api/reviews/servicios/{id}/resumen` (promedio, distribución y aspectos) y `GET /api/reviews/servicios/{id}/resenas?orden=recientes|mejores|peores` (comentarios visibles). No requieren identidad.
2. **El promedio de review y el de catalog coinciden** (los dos cuentan las publicadas y en revisión, no las ocultas).
3. **Etiqueta de los pods:** la NetworkPolicy de review deja entrar a `app.kubernetes.io/name: recommendation-service` en `turismo-app`, por el 8004.

## 10. Kubernetes y observabilidad

* **Prometheus** en el namespace `observabilidad` con `app.kubernetes.io/name: prometheus`: es lo que deja entrar la NetworkPolicy de review al 8004 (API) y al 9104 (worker). Descubre los pods por las anotaciones `prometheus.io/scrape|port|path`.
* **Plan §7.3:** review corre con 1 réplica y HPA hasta 3 al 75 % de CPU, sin PodDisruptionBudget (con 1 réplica bloquearía el drenado del nodo). Su caída no afecta a catálogo ni a reservas: review no llama a nadie y nadie lo llama en el camino crítico (ESC-01; medición pendiente, punto 12).

## 11. Lo que review ofrece a los demás

| Para | Qué | Cómo |
|---|---|---|
| catalog | Puntuación de cada reseña que cuenta en el promedio | `resena.publicada` / `resena.ocultada` |
| iam | Accesos denegados y decisiones de moderación para la bitácora | `auditoria.registrada` (`ACCESS_DENIED`, `MODERACION`) |
| PWA y chatbot | Reseñas visibles, resumen de calificación, reseña por id | Rutas públicas de `review.yaml` |
| PWA | Escribir, editar, responder, reportar y moderar | Rutas protegidas de `review.yaml` |

## 12. Pendientes del propio Módulo 4

* **Medir ESC-01 en el clúster k3s del equipo:** la prueba (k6 más el script que tumba review) está lista, pero en un PC con el compose y el clúster a la vez no hubo CPU para medir: catalog no respondía ni antes de tumbar review. Detalle y cómo retomarlo en [`k6/README.md`](./k6/README.md).
* **Notificar al turista** cuando el prestador responde o el Administrador oculta su reseña: no está en el alcance del prototipo; sería un evento nuevo que consumiría quien envíe los correos.
