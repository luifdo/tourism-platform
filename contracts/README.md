# Contratos entre servicios

Esta carpeta es el **único punto de acoplamiento** entre microservicios. Ningún servicio importa código de otro: se comunican por REST (a través del API Gateway) o por eventos (RabbitMQ), y ambos canales se definen aquí.

| Carpeta | Contenido |
|---|---|
| [`openapi/`](./openapi/) | Contrato REST de cada servicio (OpenAPI 3.0, RNF-03). |
| [`events/`](./events/) | Esquemas JSON versionados de los eventos asíncronos (SRS §3.3.3). |

## Reglas

1. **El contrato se cambia antes que el código.** Todo cambio en esta carpeta va en un PR propio, revisado por el servicio que produce el dato y por los que lo consumen.
2. **Los contratos se versionan.** Un cambio incompatible (quitar o renombrar un campo, cambiar un tipo) crea una versión nueva (`.v2`) y la anterior se mantiene hasta que todos los consumidores migren. Agregar un campo opcional no requiere versión nueva.
3. **Los consumidores son tolerantes:** ignoran los campos que no conocen y descartan eventos duplicados usando `event_id`.
