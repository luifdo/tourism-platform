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
4. **Un contrato debe ser válido para las herramientas**, no solo legible en Swagger: OpenAPI 3.0.3 sin sintaxis de 3.1 (`example`, no `examples`, dentro de un esquema) y JSON Schema 2020-12 en los eventos. En OpenAPI 3.0 `nullable` no se aplica a un `$ref`: un campo que puede ser nulo y apunta a otro esquema se escribe `anyOf: [{ $ref: ... }, { $ref: '#/components/schemas/Nulo' }]`. Cuidado con las comas dentro de `{ ... }` en YAML: una descripción sin comillas con comas se parte en propiedades falsas.
5. **Cada servicio prueba contra el contrato**: valida sus respuestas REST con el OpenAPI y lo que publica y consume con `events/`, así un cambio de esquema rompe las pruebas antes que la integración. Ejemplo completo (respuestas, Schemathesis y eventos) en [`services/catalog-service/tests/conftest.py`](../services/catalog-service/tests/conftest.py).
