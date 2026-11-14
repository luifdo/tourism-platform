# Coordinación con el Módulo 2: Catálogo

**Qué espera catalog-service de los demás módulos** · Plataforma Digital de Turismo, Santa Marta

> Documento de trabajo interno del equipo. Lista lo que catalog-service (Módulo 2) necesita de cada módulo para funcionar completo en el clúster, y lo que ofrece a cambio. Los contratos de [`contracts/`](../../contracts/) mandan: si algo de aquí no coincide con un contrato, vale el contrato y se corrige este documento. Responsable del Módulo 2: Luis Fernando Barraza Sanchez (@luifdo).

## 1. Estado del Módulo 2

catalog-service está terminado para el prototipo: API REST completa según [`catalog.yaml`](../../contracts/openapi/catalog.yaml), worker de eventos, correos de reservas, analítica para la Entidad, despliegue en compose y en Kubernetes, y pruebas de contrato y de carga. Detalle técnico y guía de uso en el [README del servicio](./README.md).

Mientras los demás módulos no existan, catalog **no se cae**: los eventos que no llegan simplemente no actualizan nada y las rutas protegidas funcionan con los encabezados de identidad que pondrá Traefik. Un correo cuyo destinatario no se puede consultar en iam se reintenta tres veces (a los 1, 5 y 25 s) y luego queda en la cola de errores `turismo.dead-letter`, desde donde se puede reprocesar.

## 2. Resumen

| Módulo | Responsable | Lo más importante | Si no está |
|---|---|---|---|
| iam-service | Valentina (@nievesita) | Ruta interna de contacto; `prestador.aprobado`/`suspendido`; cola de auditoría | Los prestadores no pueden publicar servicios; no salen correos; la auditoría de catalog se pierde |
| booking-service | Andrés (@AFGamero) | Publicar `reserva.*` y `disponibilidad.actualizada`; consumir `servicio.publicado` | No hay analítica de demanda, ni cupos en el catálogo, ni correos de reservas |
| Gateway (Traefik) | Juan Francisco (@JuanFranG) | Rutas `/api/catalog` sin quitar el prefijo; ForwardAuth; encabezados de identidad e IP | El catálogo no es accesible desde fuera del clúster |
| Frontend (PWA) | Juan Francisco (@JuanFranG) | Formularios por `tipo` y `atributos`; ETag/If-Match; botón "Cómo llegar" | — |
| recommendation-service | Alvaro (@alvaroospino) | Usar los filtros nuevos y el aviso de pagos en las tools; etiqueta de sus pods | El chatbot responde con menos detalle |
| Plantillas (`templates/`) | Alvaro (@alvaroospino) | Revisar la plantilla de Kubernetes que se agregó | — |
| Observabilidad (`infra/observabilidad/`) | Juan Francisco (@JuanFranG) | Prometheus en `observabilidad` con su etiqueta estándar | No se ven las métricas del catálogo |

## 3. Reglas comunes de los eventos

Valen para todo módulo que publique un evento que catalog consume (ver [`contracts/events/`](../../contracts/events/) y el ADR-008):

* **Sobre común** `envelope.v1.json` y payload según `<evento>.v<versión>.json`. Catalog valida cada evento: uno que no cumple su esquema va directo a la cola de errores `turismo.dead-letter` y no se reintenta.
* **`event_id` estable:** si el productor reintenta, debe mandar el mismo `event_id`. Catalog descarta los repetidos por ese campo (tabla `evento_procesado`), así que un `event_id` nuevo en cada reintento se contaría dos veces.
* **Publicar después del `COMMIT`**, idealmente con outbox (como catalog): nunca se anuncia algo que se deshizo.
* **El orden de llegada no está garantizado.** Los eventos que pueden llegar desordenados llevan un campo para ordenarlos (`version`, fechas); catalog guarda solo el más reciente.
* **Cambiar un esquema se coordina.** Las pruebas de catalog validan los eventos de ejemplo de cada consumidor contra el esquema del repositorio: si alguien cambia un esquema, esas pruebas fallan y hay que hablarlo antes de desplegar. Un cambio incompatible es una versión nueva (`v2`), no una edición de la `v1`. Recomendado para cada productor: validar en sus propias pruebas lo que publica contra `contracts/events/` (catalog lo hace con `jsonschema`; ver `services/catalog-service/tests/conftest.py`).
* **Topología:** exchange `turismo.eventos` (topic). Catalog declara sus propias colas (`catalog.prestadores`, `catalog.demanda`, `catalog.disponibilidad`, `catalog.calificaciones`, `catalog.notificaciones`); cada consumidor declara las suyas.

## 4. iam-service (Módulo 1)

**Valentina Sarait Nieves Hernandez (@nievesita)**

1. **Ruta interna de contacto** (para los correos de reservas, UC36). `GET /internal/usuarios/{usuario_id}/contacto` según [`iam-interno.yaml`](../../contracts/openapi/iam-interno.yaml): devuelve `usuario_id`, `nombre`, `email` e `idioma` (`es` o `en`); 404 si el usuario no existe. Es la única llamada REST entre catalog e iam (Plan §4.1): no pasa por el gateway.
2. **NetworkPolicy de iam:** permitir la entrada a esa ruta desde los pods con `app.kubernetes.io/name: catalog-service` (el worker de catalog es quien la llama).
3. **`prestador.aprobado`** siempre con `razon_social`: es el nombre que muestra el catálogo. Sin este evento, el prestador no puede registrar servicios (catalog responde 403).
4. **`prestador.suspendido`** según su contrato: catalog oculta los servicios del prestador suspendido. Si la suspensión llega antes que la aprobación, catalog la respeta igual.
5. **Cola de auditoría:** declarar la cola durable `iam.auditoria` enlazada a `auditoria.registrada` **antes** de que catalog empiece a publicar; si no existe, RabbitMQ descarta esos eventos. Catalog publica:
   * `ACCESS_DENIED` en cada 403 por rol, con usuario, ruta, método e IP;
   * `ZONA_CREADA`, `ZONA_EDITADA` y `ZONA_DESACTIVADA`;
   * `ALERTA_PUBLICADA`, `ALERTA_EDITADA` y `ALERTA_RETIRADA`;
   * `EXPORT` cuando la Entidad descarga el reporte de demanda (UC38), con los filtros usados.
6. **Roles en `X-Usuario-Rol`:** exactamente `Turista`, `Prestador`, `Entidad` y `Admin`.

## 5. booking-service (Módulo 3)

**Andres Felipe Gamero Sanchez (@AFGamero)**

1. **Consumir `servicio.publicado`** con una cola durable propia. Para validar que un prestador es dueño de un servicio, usar `prestador_usuario_id` (el id del usuario que llega en `X-Usuario-Id`), no `prestador_id`. Descartar los mensajes con `version` menor o igual a la que ya se tiene.
2. **Publicar `disponibilidad.actualizada.v1`** cada vez que cambie una fila de cupos (calendario del prestador UC19, solicitar, modificar, rechazar, cancelar o expirar una reserva), con el estado completo del día (`cupos_totales`, `cupos_disponibles`) y la `version` de la fila. Un día cerrado se informa con `cupos_totales: 0`. Catalog no llama a booking: con este evento muestra los cupos en búsquedas y fichas sin depender de que booking esté arriba.
3. **Publicar los `reserva.*`** según sus esquemas. Catalog los usa para la analítica de demanda (por fecha de la visita) y para los correos, así que hacen falta:
   * `motivo` en `reserva.rechazada` y `reserva.cancelada`, y `cancelada_por` en `reserva.cancelada` (decide a quién se avisa). Ojo: según el esquema, `cancelada_por` es el **rol** (`"Turista"` o `"Prestador"`), no el id del usuario;
   * `fecha_anterior`, `numero_personas_anterior` y `expira_en` en `reserva.modificada`.
4. **Regla base de cancelación:** catalog la muestra en cada ficha junto a la política del prestador. Si booking cambia la regla, avisar para cambiar el texto.
5. **Pequeña corrección en la Guía Técnica del Módulo 3:** donde dice `demanda_diaria`, en catalog la tabla se llama `reserva_proyeccion`.
6. **ESC-08:** la parte de reservas de la prueba de escalado es de booking (su propio script de k6); la del catálogo está en `services/catalog-service/k6/escalado.js`.

## 6. Gateway: Traefik

**Juan Francisco Gonzalez Pacheco (@JuanFranG)**

1. **Prefijo:** catalog atiende bajo `/api/catalog`. Enrutar al Service `catalog-service:8002` **sin** `StripPrefix`.
2. **Identidad:** en las rutas protegidas, ForwardAuth contra iam. Traefik debe **borrar** cualquier `X-Usuario-Id` o `X-Usuario-Rol` que mande el cliente y poner los suyos; catalog confía en esos encabezados.
3. **Rutas públicas** (sin token): consultas del catálogo, búsqueda, mapa, zonas, alertas y `POST /api/catalog/servicios/{id}/intencion-visita` (botón "Cómo llegar"). **Con ForwardAuth:** todo lo del prestador, la Entidad y `/api/catalog/analitica/*`. La lista exacta, por operación, está en `catalog.yaml` (`security: []` = pública).
4. **IP del cliente:** reenviar `X-Forwarded-For`, y **no** confiar en uno que mande el cliente (`forwardedHeaders.trustedIPs` sin rangos públicos). Catalog toma el primer IP para la auditoría y para contar una intención de visita por persona al día.
5. **Correlación:** reenviar o generar `X-Correlation-ID`; catalog lo propaga a sus logs y eventos.
6. **NetworkPolicy:** catalog solo deja entrar a los pods de Traefik en `kube-system` con la etiqueta `app.kubernetes.io/name: traefik` (la que trae k3s). Si se instala Traefik con otra etiqueta, avisar.

## 7. Frontend (PWA)

**Juan Francisco Gonzalez Pacheco (@JuanFranG)**

1. **Formulario del prestador:** se elige el `tipo` de servicio (la categoría sale del tipo y no se envía), la `unidad_tarifa` y los bloques de `atributos` que corresponden a ese tipo (README del servicio, sección "Tipos de servicio y atributos").
2. **Edición segura:** al editar, mandar `If-Match` con el `ETag` recibido (sin él, 428; si otro editó antes, 409 `VERSION_DISTINTA`: recargar y volver a intentar) y una `Idempotency-Key` al crear, para que un doble clic no duplique.
3. **Ficha del servicio:** mostrar `aviso_pagos` (destacado si `importante`: sin señal, solo efectivo o sin cajeros cerca) y `regla_base_cancelacion` junto a la política del prestador.
4. **Búsqueda y mapa:** los filtros nuevos (tipo, unidad de tarifa, idioma de atención, accesible, mascotas, apto para niños, opción dietaria, nivel físico, pago digital, crédito, fecha y personas) son los mismos en `/buscar` y `/mapa/servicios`, para que la lista y el mapa muestren lo mismo.
5. **"Cómo llegar":** al pulsarlo, `POST /api/catalog/servicios/{id}/intencion-visita` (responde 204, sin cuerpo). Alimenta la analítica de la Entidad.
6. **Panel de la Entidad:** alertas (`GET /entidad/alertas`, publicar, editar con `If-Match`, retirar), zonas, tablero, mapa de calor y descarga del reporte de demanda en CSV (para Excel en español).
7. **Imágenes:** el prestador pide una URL firmada (`POST /prestador/imagenes`) y sube el archivo directo a SeaweedFS con el mismo `Content-Type` y tamaño que declaró.
8. **Generar el cliente desde el contrato:** `catalog.yaml` es OpenAPI 3.0.3 válido y se verifica en cada prueba, así que se puede generar un cliente tipado (por ejemplo con `openapi-typescript`). Los campos que pueden ser nulos y apuntan a otro esquema usan `anyOf: [{$ref: X}, {$ref: Nulo}]` (en OpenAPI 3.0 `nullable` no se aplica a un `$ref`). Todo error, incluso un JSON mal formado o una ruta inexistente, llega con el formato `Error` (`error`, `message`, `correlation_id`).

## 8. recommendation-service (Módulo 5)

**Alvaro David Ospino Sanchez (@alvaroospino)**

1. **Tool `buscar_servicios`:** puede usar los mismos filtros de tipo y atributos que la búsqueda.
2. **Dinero y señal:** usar `aviso_pagos.mensaje` de la ficha para avisar al turista que lleve efectivo o que no hay señal.
3. **Tool `presion_capacidad_carga`:** `GET /api/catalog/analitica/capacidad?zona=&fecha=` con la identidad del turista; recibe solo el nivel (`BAJO`, `MEDIO`, `ALTO`) y su etiqueta, nunca cifras de la Entidad.
4. **Tool `alertas_oficiales`:** sigue con `GET /api/catalog/alertas`, sin cambios.
5. **Etiqueta de los pods:** catalog solo acepta llamadas internas de pods con `app.kubernetes.io/name: recommendation-service` en el namespace `turismo-app`.

## 9. Plantilla de Kubernetes y observabilidad

* **`templates/service-template/k8s/` (Alvaro):** se agregó una plantilla de manifiestos (Deployment, Service, HPA, PodDisruptionBudget, NetworkPolicy, ConfigMap y un overlay para probar en el Kubernetes de Docker Desktop), sacada de la de catalog y probada en un clúster. Pide revisión de Alvaro como responsable de `templates/`. Lecciones que ya trae: `startupProbe` (una app FastAPI tarda de 10 a 20 s en importar) y compilar la biblioteca estándar en el Dockerfile.
* **Prometheus (`infra/observabilidad/`, Juan Francisco):** en el namespace `observabilidad`, con la etiqueta `app.kubernetes.io/name: prometheus`, y con descubrimiento de pods por anotaciones (`prometheus.io/scrape`, `prometheus.io/port`, `prometheus.io/path`). Catalog expone la API en `:8002/metrics` y el worker en `:9102/metrics`.
* **`infra/k8s/` (Luis):** namespaces `turismo-app`, `turismo-datos` y `observabilidad`, y la infraestructura compartida; queda para cuando se monte el clúster k3s.

## 10. Lo que catalog ofrece a los demás

| Para | Qué | Dónde |
|---|---|---|
| booking | `servicio.publicado` con dueño, aforo, tarifa, estado y `version` | `contracts/events/servicio.publicado.v1.json` |
| iam | `auditoria.registrada` de los eventos críticos del catálogo | `contracts/events/auditoria.registrada.v1.json` |
| recommendation | Búsqueda, fichas, alertas y nivel de presión de capacidad | `catalog.yaml` |
| frontend | Toda la API del catálogo, mapas en GeoJSON `[lon, lat]`, textos en español e inglés | `catalog.yaml` |
| Todos | Plantilla de Kubernetes y guía para usar el clúster local | `templates/service-template/k8s/` y README de catalog |

## 11. Pendientes del propio Módulo 2

* **Reporte de demanda en PDF** (RF-13, *Could*): hoy solo CSV.
* **Correo al finalizar una visita:** se dejó para después, para concentrarse en lo esencial.
* **Pruebas de carga completas** (ESC-02 a 500 rps y ESC-08 a 1000 rps): los scripts están listos; se miden en el clúster k3s del Escenario A, no en un PC.
