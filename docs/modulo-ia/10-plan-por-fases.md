# Plan de implementación por fases

> Módulo 5 · [Índice](./README.md)

Este plan divide la construcción de `recommendation-service` en fases ordenadas. Cada fase dice qué se hace, qué carpetas toca, qué pruebas la validan y cuándo se considera cerrada. No lleva fechas: el orden y los criterios de cierre son lo que manda.

## Reglas del plan

1. **No se avanza si una fase falla.** Una fase se cierra solo cuando todas sus pruebas pasan y se cumple su criterio de cierre. Si algo falla, se corrige en esa fase antes de empezar la siguiente.
2. **Las pruebas se escriben con el código**, no al final. Cada fase entrega su código y sus pruebas juntos.
3. **Las pruebas de fases anteriores se vuelven a ejecutar** en cada fase. Si una fase nueva rompe una anterior, no se cierra.
4. **El contrato va primero.** `contracts/openapi/recommendation.yaml` se define antes de implementar los endpoints.
5. **Un commit por cambio con sentido**, en `feature/modulo-ia-dev`; lo estable pasa a `feature/modulo-ia`.

## Estructura que se usa

Se mantiene la estructura hexagonal que ya tiene el proyecto en `services/recommendation-service/` (`domain`, `application/ports`, `infrastructure`, `tests`) y se le añade lo que el módulo necesita:

| Cambio | Motivo |
|---|---|
| Agregar `src/main.py` | Composición de la app |
| Agregar `src/infrastructure/llm/` | Adaptadores del proveedor de IA |
| Agregar `src/infrastructure/tools/` | Clientes HTTP hacia catalog, booking y review |
| Agregar `mocks/` | Contenedor `mock-plataforma` |
| Agregar `Dockerfile`, `docker-compose.yml`, `pyproject.toml` y `uv.lock` | Empaquetado y dependencias (`uv`, como catalog e IAM) |
| Quitar `src/infrastructure/messaging/` | El módulo no usa RabbitMQ |

Detalle en [04-estructura.md](./04-estructura.md).

## Resumen

| Fase | Nombre | Necesita proveedor de IA |
|---|---|---|
| 0 | Contrato y andamiaje | No |
| 1 | Persistencia y sesiones | No |
| 2 | Tools y mock de la plataforma | No |
| 3 | Núcleo del chat | No |
| 4 | Validaciones y reglas | No |
| 5 | Proveedor de IA real | Sí |
| 6 | Pruebas de calidad | Sí |
| 7 | Cierre e integración | Sí |

---

## Fase 0: Contrato y andamiaje

> **Estado: construida y verificada** (`pytest` 3 pruebas en verde con 100 % de cobertura, `ruff` sin errores, contenedor `healthy`, `/health` y `/metrics` responden, usuario sin privilegios). **Falta** la revisión del contrato por el equipo: `contracts/` es de @luifdo y el criterio de cierre la exige.

**Objetivo.** Tener el contrato acordado y un servicio vacío que arranca en un contenedor.

**Qué se hace**
* Escribir `contracts/openapi/recommendation.yaml`: `POST /chat` con su petición y su respuesta (`conversacion_id`, `respuesta`, `recomendaciones[]`), `GET /health`, `GET /metrics` y el formato común de errores. Sigue las convenciones de [`contracts/openapi/README.md`](../../contracts/openapi/README.md).
* Crear la estructura de carpetas (ver arriba) y `src/main.py` con la app FastAPI.
* Implementar `GET /health` y `GET /metrics`.
* Escribir `pyproject.toml`, `uv.lock`, `Dockerfile` y `.dockerignore` ([05-dockerfile.md](./05-dockerfile.md)).
* Escribir `docker-compose.yml` del servicio y corregir `.env.example` ([06-variables-entorno.md](./06-variables-entorno.md)).

**Carpetas que toca:** `contracts/openapi/`, raíz de `services/recommendation-service/`, `src/`.

**Pruebas**
* Unitaria: `GET /health` responde 200 con el cliente de pruebas de FastAPI.
* Contrato: el `/openapi.json` que genera FastAPI es compatible con `recommendation.yaml`.
* Manual: `docker compose up --build` levanta sin errores y `curl localhost:8005/health` responde 200; `/metrics` devuelve formato Prometheus.
* La imagen corre con un usuario sin privilegios (se comprueba dentro del contenedor).

**Criterio de cierre.** El contenedor arranca, `/health` y `/metrics` responden, y el contrato está escrito y revisado por el equipo.

> **Requisito previo:** Docker y Docker Compose instalados en el equipo.

---

## Fase 1: Persistencia y sesiones

**Objetivo.** El servicio guarda y recupera lo que necesita: el registro de recomendaciones y las sesiones de chat.

**Qué se hace**
* Script de inicialización que crea la tabla `recomendacion_log` en `recommendation_db` (la base ya existe en el init SQL de `infra/`; en nuestro compose la creamos con nuestra propia instancia) ([07-base-de-datos.md](./07-base-de-datos.md)).
* Puerto y adaptador del registro de recomendaciones (SQLAlchemy sobre PostgreSQL), en `application/ports/` y `infrastructure/persistence/`.
* Puerto y adaptador de sesiones sobre Valkey: guarda los últimos 10 mensajes por conversación con TTL de 24 horas.
* Entidades del dominio: conversación, mensaje y recomendación.
* `/health` pasa a verificar la conexión con PostgreSQL y Valkey.

**Carpetas que toca:** `src/domain/`, `src/application/ports/`, `src/infrastructure/persistence/`, script SQL.

**Pruebas**
* Unitarias del dominio (sin base de datos): reglas de la conversación, límite de 10 mensajes.
* Integración con PostgreSQL y Valkey reales: se inserta y se lee un registro de `recomendacion_log`; se guarda una sesión, se recupera y expira con el TTL.
* Verificar que no se guarda el texto completo de las conversaciones en PostgreSQL.
* Reiniciar los contenedores y comprobar que el registro persiste y que una sesión caducada ya no existe.

**Criterio de cierre.** Registro y sesión se guardan y se recuperan correctamente, y las pruebas de las fases 0 y 1 pasan.

---

## Fase 2: Tools y mock de la plataforma

**Objetivo.** Las 7 tools funcionan contra servicios simulados.

**Qué se hace**
* Contenedor `mock-plataforma` con datos fijos de Santa Marta ([08-simulacion.md](./08-simulacion.md)). Booking sigue `booking.yaml`. Las rutas de catalog y review se definen aquí y se acuerdan con @luifdo.
* Puerto y clientes HTTP (`httpx`) para cada tool, en `infrastructure/tools/`:
  `buscar_servicios`, `detalle_servicio`, `consultar_disponibilidad`, `historial_turista`, `resenas_servicio`, `presion_capacidad_carga` y `alertas_oficiales`.
* `historial_turista` toma el turista del encabezado `X-Usuario-Id`, no de un parámetro. `presion_capacidad_carga` también reenvía la identidad y recibe solo el nivel (`BAJO`, `MEDIO`, `ALTO`).
* Las tools reenvían `Accept-Language` (catalog y review responden según el idioma) y usan las rutas de los contratos reales (ver [08-simulacion.md](./08-simulacion.md)).
* `buscar_servicios` aprovecha los filtros del contrato de catalog (tipo, atributos, fecha, personas) y se usa `aviso_pagos.mensaje` de la ficha para avisar de efectivo o falta de señal.
* Manejo de errores: tiempo máximo, servicio caído, respuesta inesperada.
* Declaración de las tools (nombre, descripción y parámetros) en un formato propio, independiente del proveedor.

**Carpetas que toca:** `mocks/`, `src/application/ports/`, `src/infrastructure/tools/`.

**Pruebas**
* Unitarias de cada tool con el cliente HTTP simulado.
* Integración contra el `mock-plataforma`: cada tool devuelve los datos esperados.
* Casos de error: servicio caído, tiempo agotado, respuesta mal formada, y la tool devuelve un error controlado en lugar de romper.
* `historial_turista` nunca acepta un identificador de turista que no venga del encabezado.
* Las respuestas del mock de booking se validan contra `booking.yaml`.

**Criterio de cierre.** Las 7 tools funcionan contra el mock y los casos de error están cubiertos.

---

## Fase 3: Núcleo del chat

**Objetivo.** El flujo completo del chat funciona de punta a punta, sin proveedor real.

**Qué se hace**
* Puerto `ModeloDeLenguaje`: recibe mensaje, historial y tools, y devuelve una respuesta o la solicitud de una tool.
* Caso de uso del chat ([flujo 6 del Plan](../../Documents/Pages/Plan_de_Implementacion.md#66-flujo-6-consulta-al-chatbot-de-recomendaciones-con-gemini-y-herramientas)):
  1. Recuperar historial de Valkey.
  2. Llamar al modelo con el mensaje, el historial y las tools.
  3. Mientras el modelo pida una tool (máximo 6), ejecutarla y devolverle el resultado.
  4. Obtener la respuesta final.
  5. Registrar en `recomendacion_log` y guardar la sesión.
* Endpoint `POST /api/recommendations/chat` según el contrato.
* Para probar sin proveedor: un doble de pruebas del puerto, escrito solo dentro de `tests/` (no es parte del servicio).

**Carpetas que toca:** `src/application/`, `src/infrastructure/http/`, `tests/`.

**Pruebas**
* Unitarias del caso de uso con el modelo y las tools simulados en las pruebas:
  * respuesta directa sin tools;
  * una tool y varias tools encadenadas;
  * el modelo pide una tool inexistente;
  * se llega al límite de 6 llamadas y el servicio corta con un mensaje claro;
  * el modelo falla o no responde a tiempo.
* Integración: una petición `POST /chat` recorre todo el flujo con PostgreSQL, Valkey y el mock reales, y deja el registro y la sesión.
* Contrato: la respuesta cumple `recommendation.yaml`.
* Una segunda petición con el mismo `conversacion_id` conserva el contexto.

**Criterio de cierre.** Una conversación completa funciona de punta a punta y los límites (6 tools, tiempo máximo) se respetan.

---

## Fase 4: Validaciones y reglas

**Objetivo.** El servicio cumple las reglas de negocio y de seguridad antes de entregar una respuesta.

**Qué se hace**
* **Validación de salida:** se descartan los servicios recomendados que no aparecieron en el resultado de una tool, y toda recomendación debe llevar su justificación (RNF-08).
* **Validación de entrada:** mensaje de hasta 1000 caracteres, límite de tasa y mensaje vacío.
* **Identidad:** `turista_id` solo desde `X-Usuario-Id`; sin encabezado, se rechaza.
* **Instrucciones del sistema:** acotar al turismo en Santa Marta y la plataforma, solo lectura, sin favorecer a ningún operador, priorizar destinos con baja presión de capacidad y evitar zonas con alertas oficiales.
* **Datos como datos:** los mensajes del turista y los resultados de las tools se tratan como datos, no como instrucciones.
* **Privacidad:** al proveedor nunca se le envía nombre, correo ni documento.
* **Errores:** el formato común `{error, message, correlation_id}` y mensajes claros cuando el proveedor o una tool fallan, sin inventar datos.

**Carpetas que toca:** `src/domain/`, `src/application/`, `src/infrastructure/http/`.

**Pruebas**
* Servicio recomendado que no salió de una tool: se descarta.
* Recomendación sin justificación: se rechaza o se corrige.
* Mensaje de 1001 caracteres, mensaje vacío y exceso de tasa: se rechazan con el error del contrato.
* Petición sin `X-Usuario-Id`: se rechaza; con un identificador en el cuerpo, se ignora.
* La cobertura de pruebas unitarias llega al **70 % mínimo** (Plan §8).
* Se verifica que el contenido enviado al proveedor no incluye datos personales.

**Criterio de cierre.** Todas las validaciones tienen prueba y pasan, y la cobertura es de al menos el 70 %.

---

## Fase 5: Proveedor de IA real (Groq)

**Objetivo.** Conectar Groq como proveedor de IA real sin cambiar el dominio ni los casos de uso.

**Qué se hace**
* Obtener la clave de Groq (el equipo la proporciona) y elegir un modelo de Groq que admita llamada a funciones. Groq reemplaza a Gemini, que preveía el SRS, por los problemas que tuvo el equipo al integrar su API.
* Escribir el adaptador de Groq en `infrastructure/llm/` con el SDK `groq`: implementa `ModeloDeLenguaje` y traduce las tools al formato de `chat.completions` (compatible con OpenAI).
* Configurar `LLM_PROVIDER=groq`, `LLM_API_KEY` y `LLM_MODEL` por variables de entorno; la clave nunca va al repositorio.
* Manejar los errores del proveedor: límite de solicitudes, tiempo agotado y no disponible.

**Carpetas que toca:** `src/infrastructure/llm/`, `.env.example`.

**Pruebas**
* Unitarias del adaptador con el SDK simulado: traducción de tools y de respuestas.
* Prueba manual con Groq: una conversación que dispare una tool y devuelva una recomendación válida.
* Errores del proveedor (clave inválida, límite superado, sin red): el servicio responde con un error controlado y `/health` sigue funcionando.
* Se vuelven a ejecutar las pruebas de las fases 0 a 4: ninguna debe romperse.
* Verificar que la clave no aparece en logs ni en el repositorio.

**Criterio de cierre.** Una conversación real funciona de punta a punta y el cambio de proveedor solo depende del adaptador y de las variables de entorno.

---

## Fase 6: Pruebas de calidad

**Objetivo.** Comprobar que el chatbot se comporta bien en conversaciones reales y ante abusos.

**Qué se hace** (según la [Guía Técnica](../../Documents/Pages/Guia_Tecnica_Modulo_IA.md), §8)
* Conjunto de unas **30 conversaciones tipo** con resultado esperado: búsqueda, disponibilidad, reseñas, alertas, preguntas ambiguas y preguntas que no requieren tools.
* **Seguridad:** intentos de inyección de instrucciones, de pedir datos de otro turista, de salirse del tema y de extraer las instrucciones internas.
* **Equidad:** el mismo perfil no debe favorecer sistemáticamente a un operador.
* **Idiomas:** las mismas pruebas en español y en inglés.
* **Justificación (RNF-08):** cada recomendación tiene una justificación que referencia los datos consultados.

**Carpetas que toca:** `tests/` y un informe de resultados.

**Pruebas y criterios**
* El modelo decide bien cuándo usar tools en las conversaciones tipo.
* Ningún intento de ataque consigue datos de otro turista, sale del tema ni revela las instrucciones.
* No se detecta sesgo hacia un operador.
* Resultados equivalentes en ambos idiomas.
* Se documentan los fallos encontrados y se corrigen; las pruebas que fallen se repiten tras el ajuste.

**Criterio de cierre.** El informe de pruebas está completo, todos los casos críticos de seguridad pasan y los fallos restantes están documentados y aceptados por el equipo.

---

## Fase 7: Cierre e integración

**Objetivo.** Dejar el servicio listo para integrarse con el resto de la plataforma.

**Qué se hace**
* Manifiestos de Kubernetes en `k8s/`, a partir de la plantilla `templates/service-template/k8s/` (existe en la rama `feature/catalog-service`, aún no en `develop`): Deployment (mínimo una réplica, `RollingUpdate` con `maxUnavailable: 0` y `maxSurge: 1`), Service, HPA (hasta 3 réplicas, objetivo del 75 % de CPU), sondas de `/health`, `Secret` para la clave y `ConfigMap` para el modelo.
* Los pods llevan la etiqueta `app.kubernetes.io/name: recommendation-service` en el namespace `turismo-app`: catalog solo acepta llamadas internas de pods con esa etiqueta.
* NetworkPolicy que permita al servicio llamar a catalog, booking y review.
* `startupProbe` además de las sondas de `/health` (una app FastAPI tarda de 10 a 20 s en arrancar).
* Pipeline de CI que ejecuta las pruebas, construye la imagen y la publica en GitHub Container Registry con la etiqueta del commit.
* Integración: apuntar las URLs a los servicios reales. `recommendation_db` ya está en el init SQL de `infra/`.
* Pasar lo estable a una rama `feature/recommendation-<tarea>` creada desde `develop` para abrir el PR (el equipo usa Git Flow: las features salen de `develop` y vuelven por PR; `main` solo recibe desde `release/*`).

**Pruebas**
* Los manifiestos se aplican en un clúster de prueba y el pod queda listo.
* **ESC-05:** actualizar la imagen mientras se hace una prueba de carga sobre el núcleo: 0 errores 5xx en catálogo y reservas.
* **ESC-01:** apagar el servicio (o el proveedor) y comprobar que catálogo y reservas siguen funcionando.
* Pruebas de integración contra los servicios reales, cuando existan.
* La CI pasa en verde antes de unir cambios.

**Criterio de cierre.** El servicio se despliega desde los manifiestos, pasa ESC-01 y ESC-05 y está listo para el PR.

---
[← Levantar, probar y verificar](./09-levantar-y-probar.md) · [Guía de uso →](./11-guia-de-uso.md)
