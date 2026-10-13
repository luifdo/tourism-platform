# Eventos asíncronos

Todos los eventos se publican en el exchange **`turismo.eventos`** (tipo *topic*) de RabbitMQ, con la clave de enrutamiento igual a `event_type` (por ejemplo `reserva.confirmada`). Cada mensaje sigue el sobre común [`envelope.v1.json`](./envelope.v1.json) y su `payload` se valida con el esquema del evento.

Cada servicio consumidor declara **su propia cola** (`<servicio>.<propósito>`) y la enlaza a las claves que le interesan; así un consumidor caído no afecta a los demás. Los consumidores descartan duplicados por `event_id` y, tras 3 intentos fallidos, el mensaje va a la DLQ `turismo.dead-letter` (Plan de Implementación §4.3).

Los eventos solo llevan identificadores; los datos personales (por ejemplo, el correo del turista) se consultan por REST al servicio dueño.

## Catálogo de eventos

| Evento | Productor | Consumidores | Caso de uso |
|---|---|---|---|
| [`reserva.solicitada.v1`](./reserva.solicitada.v1.json) | booking-service | catalog-service (aviso al prestador, demanda) | UC11 |
| [`reserva.confirmada.v1`](./reserva.confirmada.v1.json) | booking-service | catalog-service (correo UC36, métricas) | UC20 |
| [`reserva.rechazada.v1`](./reserva.rechazada.v1.json) | booking-service | catalog-service (correo, métricas) | UC20 / expiración |
| [`reserva.cancelada.v1`](./reserva.cancelada.v1.json) | booking-service | catalog-service (correo, métricas) | UC12 |
| [`reserva.finalizada.v1`](./reserva.finalizada.v1.json) | booking-service | review-service (habilita la reseña), catalog-service (ocupación) | RF-14 |
| [`resena.publicada.v1`](./resena.publicada.v1.json) | review-service | catalog-service (calificación promedio, UC22) | UC15, UC29 |
| [`prestador.aprobado.v1`](./prestador.aprobado.v1.json) | iam-service | catalog-service (crea el perfil, habilita UC17) | UC28 |
| [`auditoria.registrada.v1`](./auditoria.registrada.v1.json) | catalog, booking y review | iam-service (bitácora) | UC33 |

recommendation-service (Módulo 5) no publica ni consume eventos: consulta los demás servicios por REST mediante sus herramientas.
