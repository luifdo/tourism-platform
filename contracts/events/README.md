# Eventos asíncronos

Todos los eventos se publican en el exchange **`turismo.eventos`** (tipo *topic*) de RabbitMQ, con la clave de enrutamiento igual a `event_type` (por ejemplo `reserva.confirmada`). Cada mensaje sigue el sobre común [`envelope.v1.json`](./envelope.v1.json) y su `payload` se valida con el esquema del evento.

Cada servicio consumidor declara **su propia cola** (`<servicio>.<propósito>`) y la enlaza a las claves que le interesan; así un consumidor caído no afecta a los demás.

## Catálogo de eventos

| Evento | Productor | Consumidores | Caso de uso |
|---|---|---|---|
| [`reserva.solicitada.v1`](./reserva.solicitada.v1.json) | booking-service | analytics-service | UC11 |
| [`reserva.confirmada.v1`](./reserva.confirmada.v1.json) | booking-service | analytics-service (correo UC36, métricas), recommendation-service | UC20 |
| [`reserva.rechazada.v1`](./reserva.rechazada.v1.json) | booking-service | analytics-service (correo, métricas) | UC20 |
| [`reserva.cancelada.v1`](./reserva.cancelada.v1.json) | booking-service | analytics-service (correo, métricas) | UC12 |
| [`resena.publicada.v1`](./resena.publicada.v1.json) | review-service | recommendation-service | UC15 |
| [`prestador.aprobado.v1`](./prestador.aprobado.v1.json) | iam-service | catalog-service | UC28 |
| [`auditoria.registrada.v1`](./auditoria.registrada.v1.json) | todos | iam-service (bitácora) | UC33 |
