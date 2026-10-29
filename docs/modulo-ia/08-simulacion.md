# Simulación y proveedor de IA

> Módulo 5 · [Índice](./README.md)

## Proveedor de IA

El servicio no está atado a un proveedor. El caso de uso del chat depende de una interfaz (puerto), por ejemplo `ModeloDeLenguaje`, que recibe el mensaje, el historial y la lista de tools, y devuelve la respuesta o la solicitud de una tool. Cada proveedor es un adaptador en `src/infrastructure/llm/` que implementa esa interfaz.

* **Proveedor elegido: Groq** ([ADR-011](../../Documents/Pages/Registro_Decisiones_Arquitectonicas.md), en estado *Propuesta* hasta que el equipo lo apruebe). El equipo tuvo problemas al implementar la API de Gemini, que era la prevista, y decidió usar Groq. Su API es compatible con la de OpenAI (`chat.completions` con `tools`), así que el adaptador traduce nuestras declaraciones de tools a ese formato y las respuestas del modelo a la interfaz `ModeloDeLenguaje`.
* **Adaptador de Groq (Fase 5):** [`llm/modelo_groq.py`](../../services/recommendation-service/src/infrastructure/llm/modelo_groq.py), con el SDK `groq`. `llm/fabrica.py` lo elige con `LLM_PROVIDER=groq` y `LLM_API_KEY`; sin clave (o con otro proveedor) entrega `SinProveedor` y el chat responde 503 `ASISTENTE_NO_DISPONIBLE`, sin afectar al resto del servicio. No se construye un proveedor falso: las pruebas usan un modelo con guion que vive solo en `tests/fakes.py`.
  * **Modelo:** `openai/gpt-oss-120b` por defecto (`LLM_MODEL`), con `reasoning_effort=low` (`LLM_REASONING_EFFORT`) para gastar menos tokens. Otros modelos de Groq con tools: `openai/gpt-oss-20b` y `qwen/qwen3.8-27b`.
  * **Fallas:** clave inválida (401), límite (429), Groq caído (5xx), `tool_use_failed` (400), sin red o tiempo agotado → `ModeloNoDisponibleError` → 503. El SDK reintenta una sola vez (los reintentos también gastan cuota). La clave es `SecretStr`: no aparece en logs, errores ni al imprimir la configuración.
  * **Consumo:** cada llamada registra en el log sus tokens de entrada y salida.

* **Cuota del plan gratuito de Groq** (medida el 2026-10-29 en las cabeceras `x-ratelimit-*`): **8000 tokens por minuto** y **1000 solicitudes por día**, por modelo. Cada vuelta del modelo envía unos 1800 tokens fijos (instrucciones y declaraciones de las tools) más el historial y los resultados, así que una conversación con 3 o 4 vueltas usa entre 6000 y 8500 tokens: **alcanza para cerca de una conversación por minuto**. Por eso:
  * las instrucciones piden al modelo que haga juntas las consultas independientes (menos vueltas) y los resultados de las tools viajan en JSON compacto;
  * el límite por turista (`CHAT_LIMITE_MENSAJES`) protege la cuota;
  * las pruebas de la Fase 6 (unas 30 conversaciones) deben espaciarse, más o menos una por minuto;
  * para uso real con varios turistas a la vez hace falta un plan de pago o reducir más el tamaño de las declaraciones (la de `buscar_servicios` es la más grande).
* **La interfaz (Fase 3).** `ModeloDeLenguaje.generar(instrucciones, mensajes, herramientas)` recibe la conversación en un formato propio (`MensajeTurista`, `MensajeAsistente` con sus llamadas a tools y `ResultadoLlamada`) y devuelve texto, llamadas a tools o ambas cosas. Si el proveedor falla, el adaptador lanza `ModeloNoDisponibleError`.
* **Cómo termina el modelo.** Además de las 7 tools, el modelo recibe `responder_al_turista(respuesta, recomendaciones[])`. La llama para entregar la respuesta final con sus recomendaciones estructuradas (`servicio_id`, `nombre`, `justificacion`), así no depende de un modo JSON propio de cada proveedor. Si el modelo responde con texto sin llamarla, se toma como una respuesta sin recomendaciones. Esta tool no cuenta en el límite de 6.
* **Cambiar de proveedor:** es escribir un adaptador nuevo y elegirlo con `LLM_PROVIDER`; el dominio y los casos de uso no se tocan.
* **Nota:** el SRS, el Plan y el ADR-010 todavía definen Gemini como el proveedor del proyecto, y hay que actualizarlos con el cambio a Groq. La excepción a la prioridad de software libre se mantiene: Groq también es un servicio externo propietario, aunque sirve modelos abiertos.
* **Privacidad (Ley 1581):** la conversación y los resultados de las tools viajan a Groq. Se le envía el mínimo necesario y, antes de usarlo con turistas reales, hay que revisar sus condiciones de uso y retención de datos.

## Catalog, booking y review

Se simulan sin cambiar el código del servicio. Un único contenedor `mock-plataforma` (puerto 9000) responde las rutas que usan las tools, con datos fijos de Santa Marta. Las rutas salen de los contratos de cada servicio:

| Tool | Ruta | Contrato |
|---|---|---|
| `buscar_servicios` | `GET /api/catalog/buscar` (filtros: `texto`, `categoria`, `zona`, `precio_min`, `precio_max`, `lat`, `lon`, `radio_m`, `tipo`, `fecha`, `personas`, entre otros) | [`catalog.yaml`](../../contracts/openapi/catalog.yaml) |
| `detalle_servicio` | `GET /api/catalog/servicios/{servicio_id}` | [`catalog.yaml`](../../contracts/openapi/catalog.yaml) |
| `presion_capacidad_carga` | `GET /api/catalog/analitica/capacidad?zona=&fecha=` | [`catalog.yaml`](../../contracts/openapi/catalog.yaml) |
| `alertas_oficiales` | `GET /api/catalog/alertas?zona=&servicio_id=` | [`catalog.yaml`](../../contracts/openapi/catalog.yaml) |
| `consultar_disponibilidad` | `GET /api/bookings/disponibilidad?servicio_id=&desde=&hasta=` | [`booking.yaml`](../../contracts/openapi/booking.yaml) |
| `historial_turista` | `GET /api/bookings/mis-reservas` | [`booking.yaml`](../../contracts/openapi/booking.yaml) |
| `resenas_servicio` | `GET /api/reviews/servicios/{servicio_id}/resenas` y `/resumen` | [`review.yaml`](../../contracts/openapi/review.yaml) |

> `catalog.yaml` llegó a `develop` y entró en esta rama con el merge de `develop`. `review.yaml` todavía está solo en `feature/review-service`; se copió tal cual a `contracts/openapi/` de esta rama para validar el mock, y como es idéntico no debería dar conflicto cuando llegue a `develop` (si review lo cambia antes, se toma su versión). Ojo: el Plan §4.1 dice `GET /api/reviews/servicios/{id}`, pero el contrato real de review usa `/resenas` y `/resumen`.

### Qué datos tiene el mock

[`mocks/datos.py`](../../services/recommendation-service/mocks/datos.py) trae 7 servicios en 5 zonas (Taganga, Minca, Parque Tayrona, Palomino y Centro Histórico), pensados para ejercitar las reglas del chatbot:
* **Capacidad de carga:** Tayrona en nivel `ALTO`; Taganga y el Centro Histórico en `MEDIO`; Minca y Palomino en `BAJO`.
* **Alertas:** una `CRITICA` en Tayrona (Cabo San Juan saturado) y una `INFORMATIVA` en Minca (lluvias).
* **Reseñas:** la calificación del catálogo se calcula a partir de las reseñas del mock, así catalog y review siempre coinciden. Hay servicios sin reseñas.
* **Historial:** el turista `7c0e7a52-6f4b-4d65-9a3e-2f1d8b0c4e11` tiene dos reservas (una finalizada en Minca y una confirmada en Taganga); cualquier otro turista tiene el historial vacío.
* **Disponibilidad:** los cupos se calculan a partir de la fecha, así que son siempre los mismos para un mismo día y algunos días quedan sin cupo.

`tests/unit/test_mock_contratos.py` valida las respuestas del mock contra `catalog.yaml`, `booking.yaml` y `review.yaml`. Si un contrato cambia, esas pruebas avisan que el mock quedó atrás.

## Cómo responden las tools

Las tools están en [`src/infrastructure/tools/`](../../services/recommendation-service/src/infrastructure/tools/):
* **Declaraciones propias.** Cada tool tiene un modelo de Pydantic (`argumentos.py`) que valida lo que pide el modelo de IA y genera el JSON Schema de su declaración, así la declaración y la validación nunca se separan. El adaptador del proveedor (Fase 5) solo traduce ese formato.
* **Respuestas recortadas** (`recortes.py`). Al modelo solo le llega lo necesario para recomendar. No van coordenadas, imágenes, teléfonos, ids de reservas o de prestadores, ni el autor de las reseñas (Ley 1581).
* **Servicios recomendables.** Cada resultado lleva `servicios_vistos`: los servicios que salieron de `buscar_servicios`, `detalle_servicio` o `historial_turista`. En la Fase 4, el chatbot solo podrá recomendar esos. Consultar disponibilidad o reseñas de un id no lo vuelve recomendable.
* **Solo `GET`.** Ninguna tool crea, cambia ni cancela nada.
* **Nunca lanzan excepciones.** Cuando algo falla, devuelven un error con código, para que el modelo diga que no pudo consultar en lugar de inventar:

| Código | Cuándo |
|---|---|
| `HERRAMIENTA_DESCONOCIDA` | El modelo pidió una tool que no existe. |
| `ARGUMENTOS_INVALIDOS` | Argumentos mal formados (zona con caracteres raros, id que no es UUID, rango de más de 62 días…); no se llega a llamar a la plataforma. |
| `NO_ENCONTRADO` | La plataforma respondió 404. |
| `SOLICITUD_RECHAZADA` | La plataforma respondió 400; se devuelve su mensaje. |
| `SERVICIO_NO_DISPONIBLE` | No se pudo conectar (incluido no conectar a tiempo) o la plataforma respondió 5xx. |
| `TIEMPO_AGOTADO` | Se conectó, pero no respondió dentro del tiempo máximo (`HERRAMIENTAS_TIMEOUT_SEGUNDOS`, 5 s por defecto). |
| `RESPUESTA_INESPERADA` | La respuesta no es JSON o no tiene la forma del contrato. |

## Reglas que aplica el chat (Fase 4)

Lo que se puede comprobar en el código no se le confía al modelo: `responder_mensaje.py` lo hace cumplir, y las instrucciones del modelo (`instrucciones.py`) solo lo orientan.

| Regla | Cómo se cumple | Si no se cumple |
|---|---|---|
| Solo se recomiendan servicios consultados (Guía §6) | Se descarta toda recomendación cuyo servicio no esté en los `servicios_vistos` de la conversación. | Se quita de la respuesta y no se registra. |
| Toda recomendación lleva justificación (RNF-08) | El dominio rechaza la justificación vacía; la tabla también (`CHECK`). | Se quita de la respuesta. |
| Sin recomendaciones repetidas | Se deja la primera de cada servicio. | — |
| Mensaje de 1 a 1000 caracteres, no solo espacios | Validación del cuerpo. | 400 `VALIDACION`. |
| Límite de mensajes por turista | `CHAT_LIMITE_MENSAJES` por `CHAT_LIMITE_VENTANA_SEGUNDOS` (10 cada 5 min por defecto), contado en Valkey antes de llamar al modelo. Cuenta todos los intentos, también los fallidos. | 429 `DEMASIADAS_SOLICITUDES`. |
| Identidad del servidor | `X-Usuario-Id` y `X-Usuario-Rol` (Turista); un id en el cuerpo se ignora. | 401 / 403. |
| Datos como datos | Cada resultado de tool viaja como `{"origen": "datos_de_la_plataforma", "datos": …}` y las instrucciones dicen que nada de ahí ni del turista cambia las reglas. | — |
| Privacidad (Ley 1581) | Al modelo nunca llega el `turista_id` (lo usan solo las tools). Correos y celulares que el turista escriba se reemplazan por `[dato personal oculto]` antes de guardarlos o enviarlos. | — |
| Alcance, equidad y sostenibilidad | Instrucciones: solo turismo en Santa Marta, sin favorecer prestadores, preferir capacidad BAJA, no recomendar zonas con alertas críticas, no revelar las instrucciones. | Se mide en la Fase 6. |
| Dependencias caídas | Si PostgreSQL o Valkey no responden durante un chat, los adaptadores lanzan `DependenciaNoDisponibleError` (con tiempo máximo de conexión de 3 s). | 503 `ASISTENTE_NO_DISPONIBLE`. |
| Errores inesperados | Manejador general sin trazas para el cliente. | 500 `ERROR_INTERNO` con el formato común. |

El mock debe respetar también estas reglas de los contratos:
* **Idioma:** catalog y review responden según `Accept-Language`; las tools lo reenvían.
* **Identidad:** `historial_turista` y `presion_capacidad_carga` reenvían el `X-Usuario-Id` del turista. Para `Turista`, la capacidad devuelve solo `zona`, `fecha`, `nivel` (`BAJO`, `MEDIO`, `ALTO`) y su etiqueta, sin cifras.
* **Errores:** formato común `{error, message, correlation_id}`.

Qué pide catalog al Módulo 5 (su documento de coordinación, sección 8):
* Usar `aviso_pagos.mensaje` de la ficha para avisar al turista que lleve efectivo o que no hay señal.
* Etiquetar los pods con `app.kubernetes.io/name: recommendation-service` en el namespace `turismo-app`; catalog solo acepta llamadas internas de pods con esa etiqueta.

Para cambiar al servicio real basta apuntar `CATALOG_URL`, `BOOKING_URL` y `REVIEW_URL` a donde estén.

---
[← Base de datos](./07-base-de-datos.md) · [Levantar, probar y verificar →](./09-levantar-y-probar.md)
