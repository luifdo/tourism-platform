# Guía de uso de recommendation-service

> Módulo 5 · [Índice](./README.md)

Esta guía explica cómo levantar el chatbot turístico y cómo usarlo desde otras partes de la plataforma. Está pensada para quien integra el frontend (PWA), configura el gateway o necesita probar el servicio. El detalle de diseño está en los documentos 00 a 10 de esta carpeta; el contrato oficial es [`contracts/openapi/recommendation.yaml`](../../contracts/openapi/recommendation.yaml).

## 1. Qué hace

El turista escribe en lenguaje natural (español o inglés) y el servicio responde con un texto y, cuando corresponde, una lista de servicios recomendados, cada uno con su justificación.

Para responder, el modelo de IA (Groq) consulta datos reales de la plataforma: catálogo, capacidad de carga, alertas oficiales, disponibilidad, reseñas y el historial del turista. Nunca recomienda un servicio que no haya salido de esas consultas.

**Lo que no hace:** no crea, modifica ni cancela reservas. Orienta al turista para que abra la ficha del servicio y reserve desde la plataforma.

## 2. Levantarlo en local

**Requisitos:** Docker Desktop (con Docker Compose) y una clave de API de Groq ([console.groq.com](https://console.groq.com) → API Keys).

```bash
cd services/recommendation-service
cp .env.example .env
# Edita .env y pon tu clave: LLM_API_KEY=gsk_...
docker compose up --build -d
```

Esto levanta cuatro contenedores:

| Contenedor | Puerto en tu equipo | Para qué |
|---|---|---|
| `recommendation-service` | `8005` | El microservicio. |
| `postgres` | `5434` | Base `recommendation_db` con la tabla `recomendacion_log`. |
| `valkey` | `6380` | Sesiones del chat y límite de mensajes. |
| `mock-plataforma` | `9000` | Simula catalog, booking y review con datos fijos de Santa Marta. |

Comprueba que todo está bien:

```bash
curl localhost:8005/health
# {"status":"ok","checks":{"database":"up","valkey":"up"}}
```

> **La clave de Groq nunca se sube al repositorio.** `.env` está en `.gitignore`. Si no pones clave, el servicio arranca igual, pero el chat responde 503.

Para apagarlo: `docker compose down` (conserva los datos) o `docker compose down -v` (los borra).

## 3. Enviar un mensaje

**`POST /api/recommendations/chat`**

### Encabezados

| Encabezado | Obligatorio | Valor |
|---|---|---|
| `Content-Type` | Sí | `application/json` (en UTF-8). |
| `X-Usuario-Id` | Sí | UUID del turista. **En la plataforma lo pone el gateway** (Traefik) después de validar el JWT; el frontend no lo envía. |
| `X-Usuario-Rol` | Sí | `Turista`. También lo pone el gateway. |
| `Accept-Language` | No | `es` (por defecto) o `en`. Define el idioma de la respuesta y de los errores. |
| `X-Correlation-Id` | No | Si lo envías, se devuelve en los errores para rastrear la petición. |

En local, sin gateway, tú pones `X-Usuario-Id` y `X-Usuario-Rol` a mano. El turista `7c0e7a52-6f4b-4d65-9a3e-2f1d8b0c4e11` tiene historial de reservas en el mock; cualquier otro UUID sirve, con el historial vacío.

### Cuerpo

```json
{
  "mensaje": "Quiero un plan tranquilo de naturaleza para el 20 de noviembre",
  "conversacion_id": "86ab7ba9-a8dc-427d-814e-c2bb0d6a6cc0"
}
```

| Campo | Obligatorio | Descripción |
|---|---|---|
| `mensaje` | Sí | De 1 a 1000 caracteres; no puede ser solo espacios. |
| `conversacion_id` | No | Para continuar una conversación. Si falta, el servicio crea una nueva y devuelve su id. |

Cualquier otro campo se ignora. En particular, **el cuerpo nunca define al turista**: un `turista_id` en el cuerpo no tiene efecto.

### Respuesta (200)

```json
{
  "conversacion_id": "86ab7ba9-a8dc-427d-814e-c2bb0d6a6cc0",
  "respuesta": "Para un día tranquilo de naturaleza el 20 de noviembre te sugiero el avistamiento de aves en Minca...",
  "recomendaciones": [
    {
      "servicio_id": "3f2a1b6c-1d4e-4f8a-9b2c-5e6d7f8a9b03",
      "nombre": "Avistamiento de aves en Minca",
      "justificacion_explicabilidad": "Zona con nivel de capacidad bajo, sin alertas críticas, calificación 5.0 y cupos para el 20-11-2026."
    }
  ]
}
```

* `respuesta`: el texto para mostrar al turista, en su idioma. Es **texto plano** (sin Markdown ni tablas): se muestra tal cual, respetando los saltos de línea.
* `recomendaciones`: puede venir vacía (saludos, preguntas generales, nada que recomendar). Cada `servicio_id` es un servicio del catálogo.
* El encabezado `Content-Language` dice en qué idioma salió la respuesta.

### Ejemplo con curl

```bash
curl -X POST localhost:8005/api/recommendations/chat \
  -H "X-Usuario-Id: 7c0e7a52-6f4b-4d65-9a3e-2f1d8b0c4e11" \
  -H "X-Usuario-Rol: Turista" \
  -H "Content-Type: application/json" \
  -d '{"mensaje":"What can I do in Palomino?"}'
```

> **En Windows (Git Bash o PowerShell),** `curl -d` puede enviar tildes y `¿` en una codificación que no es UTF-8, y el servicio responde 400. Guarda el cuerpo en un archivo UTF-8 y envíalo con `--data-binary @pregunta.json`.

### Continuar la conversación

Guarda el `conversacion_id` de la primera respuesta y envíalo en los mensajes siguientes. El servicio recuerda los **últimos 10 mensajes** durante **24 horas** desde el último mensaje, y los servicios que ya se consultaron siguen siendo recomendables («¿y el primero que me dijiste?»).

Una conversación pertenece a un solo turista: si otro intenta continuarla, recibe 404, igual que si no existiera.

## 4. Errores

Todos los errores tienen el mismo formato, con el mensaje en el idioma de `Accept-Language`:

```json
{ "error": "ASISTENTE_NO_DISPONIBLE", "message": "El asistente no está disponible en este momento. Puedes seguir usando el catálogo.", "correlation_id": "b98fde95-..." }
```

| HTTP | `error` | Cuándo | Qué debe hacer el cliente |
|---|---|---|---|
| 400 | `VALIDACION` | Mensaje vacío, de más de 1000 caracteres o solo espacios; `conversacion_id` que no es UUID; JSON mal formado o que no es UTF-8. | Corregir la petición. Conviene validar el largo en el formulario. |
| 401 | `NO_AUTENTICADO` | Faltan `X-Usuario-Id` o `X-Usuario-Rol`, o el id no es un UUID. | Pedir que el turista inicie sesión. |
| 403 | `PROHIBIDO` | El rol no es `Turista`. | Ocultar el chat a otros roles. |
| 404 | `CONVERSACION_NO_ENCONTRADA` | La conversación no existe, expiró o es de otro turista. | Olvidar el `conversacion_id` y empezar una conversación nueva. |
| 429 | `DEMASIADAS_SOLICITUDES` | El turista superó el límite de mensajes (10 cada 5 minutos por defecto). | Mostrar el mensaje y pedir que espere unos minutos. |
| 503 | `ASISTENTE_NO_DISPONIBLE` | Groq no respondió, superó su cuota o tardó más de 45 s; o PostgreSQL o Valkey no responden. | Mostrar el mensaje e invitar a seguir con el catálogo. Se puede reintentar más tarde. |
| 500 | `ERROR_INTERNO` | Error inesperado (sin detalles internos). | Mostrar un error genérico; revisar los logs con el `correlation_id`. |

Si el asistente falla, **el resto de la plataforma sigue funcionando** (ESC-01): ningún otro servicio depende de él.

## 5. Para el frontend (PWA)

* **Tiempo de respuesta:** normalmente entre 3 y 15 segundos. El servicio corta a los 45 s con un 503, así que el `fetch` debe esperar al menos 50 s y mostrar un indicador de «escribiendo…».
* **Mostrar la respuesta:** el texto de `respuesta` como mensaje del asistente y, debajo, una **tarjeta por recomendación** con `nombre` y `justificacion_explicabilidad`, que abra la ficha del servicio (`servicio_id`) para que el turista reserve. El texto no trae ids: la tarjeta es la que enlaza.
* **Idioma:** enviar `Accept-Language` con el idioma de la interfaz.
* **Conversación:** guardar `conversacion_id` mientras el chat esté abierto; ante un 404, borrarlo y reenviar el mensaje sin él.
* **Límites en el formulario:** máximo 1000 caracteres y no enviar mensajes vacíos.
* **Identidad:** el frontend solo envía su `Authorization: Bearer <JWT>`; el gateway agrega `X-Usuario-Id` y `X-Usuario-Rol`.

Ejemplo:

```js
async function enviarAlAsistente(mensaje, conversacionId, idioma, token) {
  const respuesta = await fetch('/api/recommendations/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept-Language': idioma,
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(conversacionId ? { mensaje, conversacion_id: conversacionId } : { mensaje }),
    signal: AbortSignal.timeout(50_000),
  })
  const cuerpo = await respuesta.json()
  if (!respuesta.ok) throw Object.assign(new Error(cuerpo.message), { codigo: cuerpo.error, estado: respuesta.status })
  return cuerpo // { conversacion_id, respuesta, recomendaciones }
}
```

## 6. Para el gateway (Traefik)

* **Ruta:** `PathPrefix(/api/recommendations)` → `recommendation-service:8005`, **sin quitar el prefijo** (el servicio lo espera).
* **Autenticación:** ForwardAuth contra `GET /api/iam/auth/verificar`, reenviando `X-Usuario-Id` y `X-Usuario-Rol`. El servicio confía en esos encabezados, así que **no deben poder llegar desde afuera**: el gateway debe reemplazar cualquier valor que mande el cliente.
* **Tiempo de espera:** al menos 50 s para esta ruta, porque la respuesta del modelo puede tardar hasta 45 s.
* `/health` y `/metrics` están en la raíz (sin prefijo) y son para Kubernetes y Prometheus; no hace falta exponerlos al público.

## 7. Configuración

Todas las variables están en [`.env.example`](../../services/recommendation-service/.env.example) y explicadas en [06-variables-entorno.md](./06-variables-entorno.md). Las que más se tocan:

| Variable | Por defecto | Para qué |
|---|---|---|
| `LLM_PROVIDER` / `LLM_API_KEY` | `groq` / vacía | Proveedor de IA y su clave. Sin clave, el chat responde 503. |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Modelo de Groq; debe admitir tools. |
| `CATALOG_URL`, `BOOKING_URL`, `REVIEW_URL` | el mock | A dónde llaman las tools. Para usar los servicios reales basta cambiar estas tres. |
| `CHAT_LIMITE_MENSAJES` / `CHAT_LIMITE_VENTANA_SEGUNDOS` | `10` / `300` | Límite de mensajes por turista. |
| `CHAT_TIMEOUT_SEGUNDOS` | `45` | Tiempo máximo de una consulta completa. |
| `LOG_LEVEL` | `INFO` | `INFO` muestra cada llamada a Groq con sus tokens, y cada consulta a la plataforma. |

**Al conectar los servicios reales:** las tools llaman a catalog, booking y review con las rutas de sus contratos. `historial_turista` y la capacidad de carga reenvían `X-Usuario-Id` y `X-Usuario-Rol: Turista`. Catalog solo acepta llamadas internas de pods con la etiqueta `app.kubernetes.io/name: recommendation-service`.

## 8. Cuota de Groq (plan gratuito)

El plan gratuito permite **8000 tokens por minuto y 1000 solicitudes por día**. Una conversación típica hace 2 o 3 llamadas al modelo y usa unos 7000 tokens, así que alcanza para **más o menos una conversación por minuto**. Suficiente para desarrollo, demos y la sustentación. Con varios turistas a la vez empezarán a salir 503: para uso real hace falta un plan de pago. Detalle en [08-simulacion.md](./08-simulacion.md).

## 9. Operación y pruebas

| Para | Comando |
|---|---|
| Ver los logs | `docker compose logs -f recommendation-service` |
| Estado | `curl localhost:8005/health` (200 o 503 con el detalle de PostgreSQL y Valkey) |
| Métricas | `curl localhost:8005/metrics` (formato Prometheus) |
| Ver las recomendaciones registradas | `docker compose exec postgres psql -U turismo -d recommendation_db -c "SELECT * FROM recomendacion_log ORDER BY fecha_generacion DESC LIMIT 10"` |
| Pruebas (no gastan cuota) | `uv run pytest` |
| Pruebas con Groq real (gastan cuota) | `uv run pytest -m groq -s` |

La tabla `recomendacion_log` guarda qué se recomendó, a quién, con qué justificación, qué tools se usaron y con qué modelo, pero **nunca el texto de la conversación** (Ley 1581). Los correos y celulares que el turista escriba se ocultan antes de guardarse o enviarse a Groq.

---
[← Plan por fases](./10-plan-por-fases.md)
