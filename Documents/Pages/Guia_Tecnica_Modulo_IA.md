# Guía Técnica del Módulo 5: IA & Recomendación

**Chatbot turístico con Gemini y tools** · Plataforma Digital de Turismo, Santa Marta

> Documento de trabajo interno del equipo (guion de implementación). El nivel de detalle de arquitectura vive en el [Plan de Implementación](./Plan_de_Implementacion.md) y los requerimientos en el [SRS](./Requirements_docIEEE.md); si algo cambia, se actualiza primero allí.

## 1. Propósito

Ofrecer al turista un **chatbot** al que puede consultar en lenguaje natural (español e inglés) sobre la oferta turística de Santa Marta y recibir recomendaciones personalizadas y explicables (RF-06, UC14, RNF-08).

El chatbot usa la **API de Gemini** como modelo de lenguaje. Cuando para responder necesita información de otros sistemas de la plataforma (catálogo y analítica, reservas, reseñas), el modelo la solicita mediante **tools** y el servicio las ejecuta. No se entrena ni se mantiene un modelo propio.

## 2. Principios

* **El modelo decide cuándo consultar.** El turista pregunta; si el modelo necesita un dato que no tiene, llama a una tool. Si no lo necesita, responde directamente.
* **Respuestas ancladas en datos reales.** Lo que el chatbot afirma sobre servicios, precios, disponibilidad o reseñas viene de las tools, no de la memoria del modelo.
* **Solo lectura.** El chatbot no reserva, no modifica ni publica nada; orienta al turista hacia las pantallas de la plataforma para hacerlo.
* **Acotado al turismo.** Responde sobre turismo en Santa Marta y sobre la plataforma; rechaza con cortesía lo demás.
* **Explicable (RNF-08).** Cada recomendación va acompañada de su justificación basada en los datos consultados.
* **Identidad controlada por el servidor.** El `turista_id` sale del token JWT; el modelo nunca lo decide.
* **Modelo configurable.** El nombre del modelo de Gemini se define por variable de entorno, de modo que se puede cambiar sin tocar el código.
* **Desacoplado.** Si Gemini no está disponible, solo falla el chatbot; el resto de la plataforma sigue funcionando (ESC-01).

## 3. Alcance

**Incluye:**
* conversación en español e inglés (RF-10);
* recomendaciones personalizadas con justificación;
* preguntas sobre atractivos, precios, disponibilidad, reseñas y alertas oficiales;
* indicar al turista cómo continuar en la plataforma (por ejemplo, abrir la ficha del servicio para solicitar la reserva);
* memoria de la conversación dentro de una sesión.

**No incluye:** crear, modificar o cancelar reservas desde el chat, temas ajenos al turismo, voz, imágenes ni entrenamiento de modelos.

## 4. Arquitectura

* **Lenguaje y framework:** Python 3.12 con FastAPI, igual que los demás servicios, con la estructura hexagonal de la plantilla del monorepo.
* **Despliegue:** Contenedor en Kubernetes (k3s) con al menos una réplica siempre activa (RNF-12) y HPA para escalar con la demanda.
* **Modelo:** API de Gemini, usando su capacidad de llamada a funciones (function calling). La clave se guarda en una variable de entorno y nunca en el repositorio.
* **Interacción:** el turista envía un mensaje por el API Gateway y recibe la respuesta; la respuesta puede entregarse en streaming para que el texto aparezca mientras se genera.
* **Sesión:** la conversación reciente (últimos 10 mensajes) se guarda en Valkey con un TTL de 24 horas.
* **Registro:** las recomendaciones entregadas se guardan en la tabla `recomendacion_log` de la base propia `recommendation_db` (PostgreSQL), con la justificación, las herramientas usadas y la versión del modelo (RNF-08). No se guarda el texto completo de la conversación.
* **Endpoints:** `POST /api/recommendations/chat` para enviar un mensaje y `GET /health` para el estado del servicio.
* **Configuración:** `GEMINI_API_KEY` y `GEMINI_MODEL` (como `Secret` y `ConfigMap` de Kubernetes), `VALKEY_URL`, `DB_URL` y las URLs internas de catalog, booking y review.

## 5. Tools

Las tools son funciones que el servicio declara a Gemini y ejecuta cuando el modelo las solicita. Todas son de solo lectura y consumen los contratos REST de cada servicio.

| Tool | Servicio | Caso de uso | Cuándo la usa el modelo |
|---|---|---|---|
| `buscar_servicios(texto, categoria, zona, precio_max, cerca_de)` | catalog | UC8 | El turista pide opciones o actividades |
| `detalle_servicio(id)` | catalog | UC9 | Necesita descripción, ubicación o tarifa de un servicio |
| `consultar_disponibilidad(servicio_id, fecha)` | booking | UC10 | El turista menciona una fecha o pregunta por cupos |
| `historial_turista()` | booking | UC13 | Quiere personalizar según lo que el turista ya reservó |
| `resenas_servicio(id)` | review | UC15 | Necesita opiniones o calificación de un servicio |
| `presion_capacidad_carga(zona)` | catalog | UC24 | Prioriza destinos con menor aforo |
| `alertas_oficiales()` | catalog | UC26 | Verifica avisos activos antes de recomendar una zona |

`historial_turista` no recibe `turista_id` como parámetro: el servicio lo toma del encabezado `X-Usuario-Id` que agrega el gateway tras validar el JWT, de modo que el modelo no puede consultar datos de otro turista.

> El Módulo 2 absorbió la antigua analítica (Módulo 6), por lo que las tools de capacidad de carga y alertas consultan a catalog-service.

## 6. Respuesta y validaciones

La respuesta incluye el texto del chatbot y, cuando recomienda, la lista de servicios con su justificación:

```json
{
  "conversacion_id": "uuid",
  "respuesta": "Texto del chatbot",
  "recomendaciones": [
    {
      "servicio_id": "uuid",
      "nombre": "Nombre del servicio",
      "justificacion_explicabilidad": "Texto legible para el turista"
    }
  ]
}
```

Antes de entregar la respuesta, el servicio valida que:

* cada servicio recomendado haya aparecido en el resultado de una tool (se descartan los inventados);
* cada recomendación tenga su justificación;
* el mensaje del turista no supere los 1000 caracteres y la tasa de mensajes esté dentro del límite;
* el modelo no haya excedido las 6 llamadas a tools ni el tiempo máximo de la consulta.

Los resultados de las tools y los mensajes del turista se tratan como datos, nunca como instrucciones del sistema.

## 7. Sostenibilidad, equidad y privacidad

* **Sostenibilidad:** el chatbot prioriza destinos con baja presión de capacidad de carga y evita zonas con alertas oficiales (§2.4.4).
* **Equidad (§2.4.6):** las instrucciones del modelo prohíben favorecer a un operador sobre otro; se verifica con pruebas.
* **Privacidad:** la conversación y los resultados de las tools viajan a la API de Gemini, un servicio externo. Por eso al modelo se le envía el mínimo necesario: nunca nombre, correo ni documento del turista, solo el contenido de la conversación y los datos públicos del catálogo. Se deben revisar las condiciones de uso de datos del plan de Gemini que se utilice antes de enviar información de turistas reales (Ley 1581).
* **Uso del servicio externo:** la API de Gemini es la única dependencia propietaria del sistema; el SRS (§2.4.1, §3.6.4) y el ADR-010 recogen esta excepción a la prioridad de software libre.

## 8. Pruebas

* Conjunto de unas 30 conversaciones tipo con resultado esperado (búsqueda, disponibilidad, reseñas, alertas, preguntas ambiguas y preguntas que no requieren tools), para medir si el modelo decide bien cuándo consultar.
* Pruebas de la validación de salida (servicios no consultados, recomendación sin justificación).
* Pruebas de seguridad: intentos de inyección de instrucciones, de pedir datos de otro turista, de salirse del tema y de extraer las instrucciones internas.
* Pruebas de equidad: el mismo perfil no debe favorecer sistemáticamente a un operador.
* Pruebas en español e inglés.
* Pruebas de integración con `pytest`, con la API de Gemini y los demás servicios simulados.
* Datos sintéticos solo para probar el chatbot, no para entrenar.

## 9. Qué se necesita de los demás módulos

* **catalog:** endpoint de búsqueda con filtros y texto libre, y endpoint de detalle.
* **booking:** endpoints de disponibilidad e historial del turista.
* **review:** endpoint de reseñas y puntuación promedio por servicio.
* **catalog (analítica):** endpoints de capacidad de carga y alertas.
* **iam:** verificación del token para el gateway (ForwardAuth) y forma de consultar el consentimiento del turista.
* **gateway (Traefik):** ruta `/api/recommendations/chat` protegida con ForwardAuth, con tiempos de espera suficientes para la respuesta del modelo y, si se usa streaming, sin almacenamiento intermedio.
* **infra:** política de red que permita a recommendation-service llamar a catalog, booking y review.
* **frontend:** ventana de chat que muestre la respuesta, las recomendaciones con su justificación y el enlace a la ficha de cada servicio.
