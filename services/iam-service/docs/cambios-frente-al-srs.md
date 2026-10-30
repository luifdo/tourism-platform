# iam-service: cambios frente a la documentación base

Registro de todo lo que el Módulo 1 implementa de forma distinta, adicional o pendiente respecto a:

- **SRS** v1.1 (ISO/IEC/IEEE 29148).
- **Plan** de Implementación y Funcionamiento Interno (`Documents/Pages/Plan_de_Implementacion.md`).
- **Lab** 3: Documentación de Arquitecturas de Software.
- **Contratos** de `contracts/` en `develop`.

Cada entrada dice qué fija el documento, qué se hizo, **por qué** (la causa) y **para qué** (el
efecto que se busca), con su estado. Se actualiza en el mismo commit que introduce el cambio.

**Estados:** ✅ Implementado (commit) · 🔨 En curso (bloque) · 📅 Planeado (bloque) · ⏸ Pendiente o fuera de alcance

**Para el informe de la Fase 5:** las entradas marcadas con ★ contradicen el texto del SRS o
del laboratorio y conviene reflejarlas en una versión 1.2 del SRS o en un ADR del IAM.

---

## 1. Modelo de datos (`iam_db`)

### C-01 · Campos adicionales en `USUARIO`
- **Referencia:** SRS §3.7, Tabla XVII.
- **El documento fija:** `id`, `email`, `password_hash`, `rol`, `email_verificado`, `habeas_data_aceptado`, `creado_en`.
- **Se hizo:** se agregaron `nombre_completo`, `activo`, `habeas_data_aceptado_en` y `actualizado_en`.
- **Por qué:** el SRS no prevé cómo nombrar al usuario en el panel y en los correos (UC36), ni cómo desactivarlo sin borrarlo. Además, la Ley 1581 y el Decreto 1377 exigen poder demostrar *cuándo* se otorgó la autorización, no solo que se otorgó.
- **Para qué:** desactivar cuentas en UC27 conservando su historial en la bitácora, tener prueba del consentimiento (UC6) ante la SIC y personalizar los correos.
- **Estado:** ✅ `8851049`.

### C-02 · Campos adicionales en `DOCUMENTO_VERIFICACION`
- **Referencia:** SRS §3.7, Tabla XVII; UC28.
- **Se hizo:** se agregaron `motivo_rechazo`, `revisado_por` y `revisado_en`, que UC28 llena al aprobar o rechazar. En el bloque 5 se sumaron `tipo_contenido` (el tipo real, detectado por la firma de bytes), `tamano_bytes` y `vigente`, con un índice único parcial `(usuario_id, tipo_documento) WHERE vigente` (C-30). El prestador ve el estado y el motivo; solo el Admin ve `revisado_por`. La llave `objeto_s3` nunca sale en una respuesta.
- **Por qué:** UC28 permite rechazar, pero el modelo no guarda ni el motivo ni quién decidió.
- **Para qué:** que el prestador sepa qué corregir y que cada decisión del Admin sea trazable.
- **Estado:** ✅ esquema en `8851049`. ✅ `951bdc4`: `tipo_contenido`, `tamano_bytes`, `vigente` y el llenado de la revisión.

### C-03 · Restricciones de integridad en la base
- **Referencia:** SRS §3.7 (no las especifica); RNF-10; UC6.
- **Se hizo:** `CHECK` de email en minúsculas, `CHECK habeas_data_aceptado = true`, llaves foráneas con `ON DELETE RESTRICT`, triggers que bloquean `UPDATE`, `DELETE` y `TRUNCATE` sobre la bitácora, y `REVOKE` al rol de la aplicación.
- **Por qué:** las reglas aplicadas solo en el código se pueden saltar con un error de programación o con un acceso directo a la base.
- **Para qué:** que el consentimiento obligatorio (UC6) y la inmutabilidad de la bitácora (RNF-10) los garantice la propia base de datos.
- **Estado:** ✅ `8851049`. Evidencia: el `UPDATE` falla con "bitacora_auditoria es de solo inserción (RNF-10)".

### C-04 ★ Idempotencia de la auditoría en la base, no en Valkey
- **Referencia:** SRS §3.6.3, Tabla XV ("Valkey: idempotencia de eventos"); Lab, Figuras 1 y 2 y especificación ACME (conector `VerificacionIdempotencia` con TTL de 24 h).
- **Se hizo:** se agregó `event_id` (UUID, `UNIQUE`, nulo en las filas propias del IAM) a `bitacora_auditoria`. El consumidor guarda cada evento con un solo `INSERT … SELECT … ON CONFLICT (event_id) DO NOTHING`. Un duplicado no inserta nada, se confirma (`ack`) y se cuenta en `iam_eventos_consumidos_total{resultado="duplicado"}`. El IAM no consulta Valkey para esto.
- **Por qué:** el propio laboratorio (§1.3) detectó que un evento reentregado después del TTL de 24 h se insertaría dos veces. Con Valkey, además, el registro "ya procesado" y la fila se confirman en sistemas distintos: si uno falla entre ambos, queda un duplicado o una pérdida. El Módulo 2 llegó a la misma conclusión y el Plan §4.3 ya se actualizó.
- **Para qué:** cero duplicados sin límite de tiempo (RNF-10, ESC-04) y una dependencia menos en el camino de la auditoría.
- **Estado:** ✅ `2d011e0`.

### C-05 · Columna `correlation_id` en la bitácora
- **Referencia:** SRS Tabla XVII (no la incluye); Plan §4.1 y §7.5.
- **Se hizo:** columna `correlation_id VARCHAR(100)`, nula. En los eventos de otros servicios toma el `correlation_id` del sobre (nula si no viene). En las filas propias toma el de la petición en curso: un `ContextVar` que fija `CorrelacionMiddleware` (ASGI puro, adaptado del de catalog) con el `X-Correlation-ID` recibido, o con un UUID nuevo si falta o no cumple `^[A-Za-z0-9._-]{1,100}$`. El middleware lo devuelve en el encabezado de la respuesta, y el mismo valor va en los errores (C-12) y en cada línea de log JSON.
- **Límite:** el 500 de una excepción no controlada lo arma `ServerErrorMiddleware` de Starlette, que queda por fuera del middleware: esa respuesta sale sin `X-Correlation-ID` y con el cuerpo de texto de Starlette, sin `correlation_id`. Pasa lo mismo en catalog. Los errores previstos (401, 403, 404, 409, 422, 503) sí lo llevan.
- **Por qué:** el Plan exige seguir una petición entre servicios con `X-Correlation-ID`, pero la bitácora no tenía dónde guardarlo.
- **Para qué:** cruzar una fila de la bitácora con los logs en Loki y con el evento que la originó.
- **Estado:** ✅ `2d011e0` (columna y eventos de otros servicios). ✅ `dcf6496` (middleware).

### C-06 · Columna `idioma` en `USUARIO`
- **Referencia:** SRS Tabla XVII; RF-10; `contracts/openapi/iam-interno.yaml`.
- **Se hizo:** `idioma VARCHAR(2) NOT NULL DEFAULT 'es'` con `CHECK (idioma IN ('es', 'en'))`; las cuentas existentes quedan en `es`. Es opcional en `POST /api/iam/register` (otro valor responde 422 `VALIDACION`) y se devuelve en su respuesta; como el login usa el mismo esquema, también aparece en su `usuario`. La ruta interna de contacto (C-15) lo entrega a catalog. Se edita con `PATCH /api/iam/perfil` (C-49).
- **Por qué:** RF-10 exige la plataforma en dos idiomas, pero el idioma de la PWA vive en el navegador. Los correos los envía el worker de catálogo, que no tiene acceso al navegador.
- **Para qué:** que los correos de reservas (UC36) y de recuperación (UC3) lleguen en el idioma del usuario.
- **Estado:** ✅ `dcf6496` (columna, registro y contacto). ✅ `47308f4`: edición en el perfil.

### C-07 ★ `razon_social` guardada en `iam_db`
- **Referencia:** SRS Tabla XVIII (`razon_social` pertenece a `PRESTADOR_PERFIL`, en `catalog_db`); contrato `prestador.aprobado.v1`.
- **Se hizo:** el IAM pide `razon_social` al cargar el RUT (UC37), la guarda en `usuario.razon_social` (de 2 a 200 caracteres; sin ella, 422 `RAZON_SOCIAL_INVALIDA`) y la envía en `prestador.aprobado`. Con el RNT el campo no se usa. Si se vuelve a cargar el RUT, la razón social se actualiza.
- **Por qué:** catálogo crea el perfil al consumir el evento y necesita un nombre comercial desde el primer momento. Quien la conoce en ese momento es el IAM, porque viene del RUT.
- **Para qué:** que el perfil del prestador nazca completo. Catálogo sigue siendo el dueño del perfil y puede editarlo después.
- **Estado:** ✅ `951bdc4`.

### C-08 ★ `prestador_id` igual al `usuario_id`
- **Referencia:** SRS Tabla XVIII (`PRESTADOR_PERFIL.id` es una PK propia de catálogo); contratos `prestador.aprobado.v1` y `prestador.suspendido.v1`.
- **Se hizo:** `prestador.suspendido` (bloque 4) lleva `prestador_id` = `usuario_id`; `prestador.aprobado` (bloque 5) también.
- **Por qué:** el contrato exige un `prestador_id` que asigna el IAM. Un identificador nuevo obligaría a crear otra tabla y a mantenerlo estable cuando un prestador se suspende y se vuelve a aprobar.
- **Para qué:** un identificador estable sin estructuras adicionales; catálogo reactiva el mismo perfil.
- **Estado:** ✅ `8583e38` (`prestador.suspendido`). ✅ `951bdc4` (`prestador.aprobado`). Acordado con Luis Fernando.

### C-09 · Tabla `outbox` en `iam_db`
- **Referencia:** SRS §3.6.2, nota (el patrón outbox es opcional); Plan §4.3 y §4.4; ADR-008.
- **Se hizo:** tabla `outbox` con el mismo esquema que la de catalog (`event_id` PK, `event_type`, `sobre jsonb`, `creado_en`, `publicado_en`, `intentos`, índice parcial `ix_outbox_pendientes`). El evento se guarda con su sobre completo (`producer: "iam-service"`, `occurred_at` = momento del cambio, `correlation_id` de la petición) en la misma transacción que el cambio y su fila de la bitácora. El relay del worker, adaptado de catalog, toma lotes de 100 con `FOR UPDATE SKIP LOCKED`, publica con *publisher confirms* y mensajes persistentes, marca `publicado_en` solo cuando el broker confirma, reintenta con espera creciente (1 s hasta 30 s) y borra a diario lo publicado hace más de 7 días. Métricas en el worker: `iam_eventos_publicados_total{event_type}`, `iam_eventos_fallos_publicacion_total`, `iam_outbox_pendientes` e `iam_outbox_antiguedad_segundos`. La entrega es "al menos una vez": catalog descarta duplicados por `event_id`.
- **Por qué:** si el proceso falla entre el commit de la aprobación y la publicación, `prestador.aprobado` se pierde y el prestador queda aprobado en el IAM pero sin perfil en catálogo.
- **Para qué:** garantizar la entrega de `prestador.aprobado` y `prestador.suspendido`. Es el mismo patrón que ya usa catálogo.
- **Estado:** ✅ `8583e38`.

### C-10 · Columnas `datos_suprimidos_en` (ver C-27) y `version` (ver C-49)
- **Referencia:** SRS Tabla XVII (no las incluye).
- **Se hizo:** `datos_suprimidos_en TIMESTAMPTZ`, nula salvo en las cuentas suprimidas, y `version INTEGER NOT NULL DEFAULT 1`, que sube con cada edición del perfil.
- **Por qué:** una cuenta suprimida debe distinguirse de una simplemente inactiva, que el Admin puede reactivar. El formulario de perfil de RNF-13 necesita una versión para detectar conflictos.
- **Para qué:** bloquear todo cambio posterior sobre una cuenta suprimida (`CUENTA_SUPRIMIDA`) y responder 409 si el perfil cambió mientras el formulario esperaba la conexión.
- **Estado:** ✅ `47308f4`.

---

## 2. API y contratos

### C-11 · Nombres de las rutas públicas
- **Referencia:** Plan §4.1 y `gateway/README.md` (`/api/iam/auth/login`, `/auth/registro`, `/auth/recuperar`). El SRS §3.3.3 solo fija el prefijo `/api/iam`.
- **Se hizo:** se conservan `POST /api/iam/register`, `/login` y `/logout`. Las rutas nuevas van bajo `/api/iam/auth/`: `verificar`, `recuperar`, `restablecer` y `refresh`.
- **Por qué:** el frontend (rama `feature/frontend-landing-reservas`) ya está integrado y probado contra las rutas existentes. Renombrarlas obligaría a rehacer trabajo a menos de una semana del cierre de la Fase 4.
- **Para qué:** cerrar la integración con la PWA sin retrabajo. No contradice el SRS; hay que actualizar el Plan §4.1 y `gateway/README`.
- **Estado:** ✅ las existentes; acordado con Juan Francisco el 29 de octubre.

### C-12 · Formato de error
- **Referencia:** Plan §4.1 (`{error, message, correlation_id}`). El SRS no lo fija.
- **Se hizo:** el IAM responde `{detail, code, errores?, correlation_id}`.
- **Por qué:** el IAM se construyó antes de que se fijara el formato común, y la PWA ya interpreta estas claves.
- **Para qué:** no romper la integración con la PWA. Se agrega `correlation_id` (el de C-05, siempre presente en los errores previstos) para la trazabilidad que pide el Plan. Unificar el formato queda como deuda técnica coordinada con el frontend.
- **Estado:** ✅ formato base; `correlation_id` ✅ `dcf6496`.

### C-13 · Encabezados de identidad `X-Usuario-Id` y `X-Usuario-Rol`
- **Referencia:** SRS §3.3.3 (no los nombra); Plan §4.1 y §6.1; Lab §4.1, Figura 12.
- **Se hizo:** se usan los nombres del Plan, que coinciden con el Lab §4.1, Figura 12 (`GET /api/iam/auth/verificar` → 200 + `X-Usuario-Id`, `X-Usuario-Rol`); una versión anterior de la planificación del IAM decía `X-User-*`. `verificar` responde `X-Usuario-Id` con el `sub` del token (UUID) y `X-Usuario-Rol` con el valor del rol tal como está en el SRS (`Turista`, `Prestador`, `Entidad` o `Admin`). Traefik debe copiarlos con `authResponseHeaders`, que reemplaza los que traiga el cliente.
- **Por qué:** catálogo, reservas, reseñas e IA ya leen `X-Usuario-*`.
- **Para qué:** que todos los servicios entiendan la identidad que propaga Traefik sin adaptaciones.
- **Riesgo:** el Plan §4.1 dice que los servicios confían en estos encabezados porque solo reciben tráfico de Traefik. Pero en las rutas **sin** ForwardAuth (públicas) Traefik no los reemplaza, y un cliente puede enviar `X-Usuario-*` falsos que llegan intactos al servicio. Mitigación: el gateway debe eliminarlos de toda petición entrante (middleware `headers` con esos `customRequestHeaders` vacíos) y, mientras tanto, ningún servicio debe leerlos en sus rutas públicas. Se coordina con Juan Francisco (`gateway/`).
- **Estado:** ✅ `d30aef8` en el IAM. La eliminación en el gateway queda ⏸ pendiente, por coordinar con Juan Francisco.

### C-14 · JWKS público adicional
- **Referencia:** SRS §3.6.1 (solo exige verificar tokens para el gateway).
- **Se hizo:** `GET /api/iam/.well-known/jwks.json`, con caché de 300 s.
- **Por qué:** los demás servicios podrían necesitar verificar la firma sin pasar por el gateway.
- **Para qué:** facilitar la interoperabilidad (RNF-03). **No** sustituye a `verificar` en el gateway (ver C-16).
- **Estado:** ✅ `3cb0cd7`.

### C-15 · Endpoint interno de contacto
- **Referencia:** no está en el SRS. Plan §4.1, "única excepción"; `contracts/openapi/iam-interno.yaml`.
- **Se hizo:** `GET /internal/usuarios/{usuario_id}/contacto`, sin prefijo `/api`, sin pasar por Traefik y fuera del OpenAPI público (`include_in_schema=False`). Responde `{usuario_id, nombre, email, idioma}` como fija el contrato, con `nombre` = `nombre_completo`.
  - **Usuario inactivo:** 200, para que siga recibiendo los avisos de sus reservas (por ejemplo, la cancelación). Con los datos suprimidos, 404 `USUARIO_NO_ENCONTRADO` (C-27).
  - **Inexistente:** 404 `USUARIO_NO_ENCONTRADO`. **UUID mal formado:** 422 `VALIDACION`.
  - **Defensa adicional a la NetworkPolicy:** si la petición trae `X-Forwarded-For` o `X-Forwarded-Host` (llegó por Traefik), responde el mismo 404 `USUARIO_NO_ENCONTRADO` sin consultar la base, aunque el usuario exista o el UUID esté mal formado. Así, una regla de enrutamiento mal configurada no expone la ruta ni permite enumerar usuarios.
  - **Trazabilidad:** métrica `iam_contacto_consultas_total{resultado}` (`ok`, `no_encontrado`, `rechazado_proxy`) y una línea de log JSON por consulta con `usuario_id`, `resultado` y `correlation_id`, nunca el correo. No escribe fila en la bitácora.
- **Por qué:** los eventos solo llevan identificadores, de modo que los datos personales no viajan por el bus (Ley 1581). Aun así, catálogo necesita el correo para enviar UC36.
- **Para qué:** que catálogo pida el correo en el momento del envío y no lo guarde. Así el único lugar con el dato sigue siendo `iam_db`.
- **Por qué basta con el log y no va a la bitácora:** por volumen, porque hay una consulta por cada correo de reserva: la bitácora (de solo inserción, UC33) crecería con filas de rutina que no son acciones de un usuario. Y por trazabilidad: si el worker de catalog envía como `X-Correlation-ID` el `correlation_id` del evento que originó el correo, la línea del log se cruza en Loki con ese evento y con la fila de la bitácora que haya generado. La métrica permite alertar ante un pico de `no_encontrado` o ante cualquier `rechazado_proxy`.
- **Riesgo:** hoy `DirectorioUsuariosIam` de catalog (`develop`) no envía `X-Correlation-ID`: el IAM genera un UUID nuevo por consulta y la línea del log no se cruza con el evento. Hace falta que catalog agregue el encabezado con su `correlation_id_actual()`. Se coordina con Luis Fernando.
- **Estado:** ✅ `dcf6496`. Propuesto por Luis Fernando. El envío del encabezado desde catalog queda ⏸ pendiente, por coordinar con él.

### C-16 · El gateway valida con `verificar` y no con el JWKS
- **Referencia:** SRS §3.3.3 y ESC-04; Plan §2.3 y §6.1; Lab §4.1, Figura 12; ADR-007.
- **Se hizo:** el ForwardAuth llama a `GET /api/iam/auth/verificar`. Es conforme al SRS, al Plan §6.1, al ADR-007 y al Lab §4.1, Figura 12 (`verificar` → 200 + `X-Usuario-Id`, `X-Usuario-Rol`); se registra aquí porque el equipo preguntó por la alternativa. El endpoint es público en el router (la validación es el propio endpoint) y comprueba firma RS256, emisor, expiración con 10 s de margen, `typ = access` y revocación por `jti` y por usuario (C-21). Si el token es válido responde 200 con cuerpo vacío, los encabezados de C-13 y `Cache-Control: no-store`, **sin consultar PostgreSQL**: solo hace una lectura en Valkey. Si no, responde 401 `TOKEN_INVALIDO` y escribe una fila en la bitácora (C-23, C-34).
- **Por qué:** con el JWKS solo se comprueba la firma. No se puede saber si el token fue revocado, ni registrar el 401 en la bitácora, y ESC-04 exige el 100 % de los rechazos registrados.
- **Para qué:** cumplir ESC-04 y que el logout y los cambios de rol tengan efecto de inmediato. Dejar PostgreSQL fuera del camino feliz mantiene baja la latencia que el ForwardAuth suma a cada petición protegida (ESC-02). `no-store` evita que una respuesta de identidad quede en alguna caché intermedia.
- **Costo:** cada petición protegida depende de Valkey; si no responde, el resultado es 503 (C-22).
- **Estado:** ✅ `d30aef8` (pruebas de API y `scripts/smoke_test.py`).

### C-17 · Evento `prestador.suspendido`
- **Referencia:** SRS Tabla XIV (solo `prestador.aprobado`); `contracts/events/prestador.suspendido.v1.json`.
- **Se hizo:** el IAM lo agrega al outbox cuando un Prestador activo deja de estarlo: el Admin lo desactiva o le cambia el rol. El payload lleva `prestador_id` (= `usuario_id`, C-08), `usuario_id` y `suspendido_por` (el Admin), sin `motivo` (C-41). También lo agrega la supresión de datos de un Prestador visible, con `suspendido_por` = el propio usuario (C-48). Si el prestador ya estaba inactivo no se publica otra vez. Reactivar a un Prestador o devolverle el rol no publica este evento: publica `prestador.aprobado` si sus dos documentos están aprobados (C-42). Una prueba valida el sobre contra `envelope.v1.json` y el payload contra `prestador.suspendido.v1.json` leyendo los archivos del monorepo.
- **Por qué:** cuando el Admin desactiva a un prestador (UC27), su oferta seguiría visible en el catálogo.
- **Para qué:** que catálogo oculte el perfil y los servicios, y que la reserva deje de aceptarlos.
- **Estado:** ✅ `8583e38`.

### C-18 · Valores de `resultado` en el contrato de auditoría
- **Referencia:** SRS Tabla XVII (`Exito`, `Denegado`, `Error`); contrato `auditoria.registrada.v1` (`EXITO`, `DENEGADO`, `ERROR`).
- **Se hizo:** la base conserva los valores del SRS y el consumidor traduce los del contrato (`EXITO` → `Exito`, etc.). Un `resultado` fuera del enum del contrato, incluidos los valores del SRS, no cumple el contrato y va a la DLQ.
- **Por qué:** el contrato del equipo usa mayúsculas.
- **Para qué:** respetar el SRS sin obligar a los productores a cambiar.
- **Estado:** ✅ `2d011e0`.

### C-19 · Nombres de las acciones de la bitácora
- **Referencia:** SRS Tabla XVII (`LOGIN_FAIL`, `ROLE_CHANGE`, `ACCESS_DENIED`, `EXPORT`); Plan §2.3 (`LOGIN_FALLIDO`, `ROL_MODIFICADO`, `PRESTADOR_VALIDADO`); Lab §4.2 (`LOGIN_EXITOSO`, `LOGIN_FALLIDO`, `REFRESH_REUTILIZADO`).
- **Se hizo:** se usan los nombres del SRS. Las acciones nuevas siguen su mismo estilo (inglés, mayúsculas con guion bajo): `LOGIN_SUCCESS`, `LOGOUT`, `USER_REGISTER`, `USER_STATUS_CHANGE`, `PROVIDER_APPROVED`, `PROVIDER_REJECTED`, `DOCUMENT_UPLOAD`, `DOCUMENT_VIEW`, `PROFILE_UPDATE`, `PASSWORD_CHANGE`, `PASSWORD_RESET_REQUEST`, `PASSWORD_RESET`, `DATA_SUPPRESSION`, `AUDIT_VIEW`. Las que llegan de otros módulos (`ZONA_CREADA`, etc.) se guardan tal como vienen.
- **Por qué:** los tres documentos no coinciden entre sí. El SRS es el acuerdo de mayor jerarquía.
- **Para qué:** un vocabulario consistente para filtrar en UC33. El filtro `accion` de `GET /api/iam/admin/bitacora` compara el nombre exacto (C-43): con nombres mezclados (`ROLE_CHANGE` y `ROL_MODIFICADO`), una búsqueda dejaría fuera parte de los cambios de rol. Las acciones de otros módulos se guardan como vienen, así que se filtran con su propio nombre (`ZONA_CREADA`). El Plan y el laboratorio deberían actualizarse con estos nombres.
- **Estado:** ✅ los existentes; ✅ `8583e38`: `ROLE_CHANGE` (del SRS), `USER_STATUS_CHANGE` y `AUDIT_VIEW`; ✅ `951bdc4`: `DOCUMENT_UPLOAD`, `DOCUMENT_VIEW`, `PROVIDER_APPROVED` y `PROVIDER_REJECTED`; ✅ `47308f4`: `PROFILE_UPDATE`, `PASSWORD_CHANGE`, `PASSWORD_RESET_REQUEST`, `PASSWORD_RESET` y `DATA_SUPPRESSION`.

### C-41 · `prestador.suspendido` sin `motivo`
- **Referencia:** `contracts/events/prestador.suspendido.v1.json` (admite `motivo` opcional, hasta 500 caracteres); Plan §4.2 (los eventos llevan solo identificadores).
- **El documento fija:** el contrato permite enviar el motivo de la suspensión.
- **Se hizo:** el IAM nunca lo envía. El motivo que escribe el Admin queda solo en la bitácora (`detalles.motivo`, recortado a 500 caracteres, C-29).
- **Por qué:** es texto libre: el Admin puede escribir ahí un nombre, un número de documento o el detalle de una queja, y todo lo que viaja por el bus queda en las colas, en la DLQ y en los logs de cada consumidor. El Plan §4.2 pide que el bus lleve solo identificadores para que los datos personales no salgan de su servicio (Ley 1581).
- **Para qué:** que el motivo quede en un solo lugar, la bitácora del IAM, con acceso restringido al Admin (UC33). Catalog no lo necesita para ocultar la oferta.
- **Estado:** ✅ `8583e38`.

### C-42 · Rehabilitar a un Prestador publica `prestador.aprobado` solo si está verificado
- **Referencia:** `contracts/events/prestador.suspendido.v1.json` ("si iam lo vuelve a habilitar, publica de nuevo `prestador.aprobado`"); UC27 y UC28.
- **El documento fija:** que al rehabilitar a un prestador suspendido se publica `prestador.aprobado`.
- **Se hizo:**
  - **Bloque 4:** no se publicaba ningún evento al reactivar a un Prestador ni al cambiar una cuenta a Prestador; la oferta no volvía a mostrarse en catalog.
  - **Bloque 5:** `cambio_administrativo.py` publica `prestador.aprobado` (con `aprobado_por` = el Admin y la `razon_social`) cuando un Prestador **vuelve a quedar visible**, sea porque lo reactivan o porque la cuenta vuelve a tener ese rol, y **sus dos documentos vigentes están aprobados**. Con documentos pendientes, rechazados o faltantes, no se publica nada. Del mismo modo, aprobar a un prestador inactivo aprueba sus documentos pero no publica (C-47): el evento sale al reactivarlo.
- **Por qué:** `prestador.aprobado` significa que el prestador tiene sus documentos (RNT y RUT) aprobados. Publicarlo sin esa condición habilitaría en catalog a prestadores que nunca fueron verificados.
- **Para qué:** que catalog solo muestre prestadores verificados y que, al rehabilitar a uno, restaure los servicios que había apagado por la suspensión.
- **Estado:** ✅ `8583e38` (sin evento). ✅ `951bdc4`: `prestador.aprobado` al rehabilitar.

### C-43 · Consulta de la bitácora (UC33)
- **Referencia:** SRS UC33 ("Consultar bitácora de auditoría inmutable") y RNF-10 ("consulta de bitácora disponible en panel administrativo"). Ninguno fija filtros, orden ni formato.
- **Se hizo:** `GET /api/iam/admin/bitacora`, con `require_role(Rol.ADMIN)`.
  - **Filtros**, combinables: `usuario_id`, `accion` (exacta, hasta 50 caracteres), `resultado` (`Exito`, `Denegado` o `Error`), `servicio_origen` (exacto), `desde` y `hasta`.
  - **Rango semiabierto:** `desde <= fecha < hasta`, para que dos rangos seguidos (un día y el siguiente) no repitan ni pierdan filas. Las fechas deben llevar zona horaria (ISO 8601, por ejemplo `2026-10-30T00:00:00-05:00` o `...Z`); sin zona, 422 `VALIDACION`. Si `desde` no es anterior a `hasta`, 422 `RANGO_FECHAS_INVALIDO`.
  - **Orden:** por `fecha` descendente, que es el momento del hecho y no el de la inserción (C-39), con el `id` como desempate.
  - **Paginación:** `pagina` y `tamano` (de 1 a 100, 20 por defecto); la respuesta lleva `{items, total, pagina, tamano}`.
  - **Cada fila** se devuelve completa: `id`, `fecha`, `usuario_id`, `accion`, `resultado`, `servicio_origen`, `ip_origen`, `detalles`, `correlation_id` y `event_id` (este último solo en las filas de otros servicios).
  - **Cada consulta se audita** con una fila `AUDIT_VIEW` / `Exito`: `usuario_id` = el Admin, su IP y el `correlation_id` de la petición, y `detalles` = `{filtros, pagina, tamano}`, donde `filtros` lleva solo los que se usaron, en texto (los UUID como cadena y las fechas en ISO 8601). **Nunca los resultados.** Se escribe en su propia transacción y **después de leer**, así que una consulta no se ve a sí misma. Si esa escritura falla, solo queda un log de error y la consulta responde 200 igual. Un 422 (filtro inválido o rango invertido) no lee ni deja fila. Los rechazos (401 y 403) quedan como `ACCESS_DENIED`, como en todo `require_role` (C-23).
- **Por qué:** sin zona horaria, PostgreSQL interpretaría la fecha en la zona del servidor, y el mismo filtro daría resultados distintos según dónde corra. `accion` y `servicio_origen` son exactos porque son vocabularios cerrados (C-19), y así usan el índice de `accion`. La consulta se audita porque la bitácora guarda datos sensibles (IPs, motivos de suspensión, a quién se le cambió el rol): RNF-10 pide trazabilidad de los eventos administrativos, y leerla también lo es. Saber quién la consultó, con qué filtros y cuándo permite detectar un uso indebido de una cuenta Admin. Los resultados no se guardan porque duplicarían en la bitácora lo que ya está en ella. La escritura va aparte y no bloquea la respuesta, como la de los rechazos (C-23): si la bitácora no admite escrituras pero sí lecturas, el Admin igual puede revisarla.
- **Para qué:** que el Admin revise en un solo lugar las acciones propias del IAM y las de los demás módulos (RNF-10), y cruce cada fila con los logs por su `correlation_id`.
- **Estado:** ✅ `8583e38` (con `AUDIT_VIEW`).

---

## 3. Seguridad y sesiones

### C-20 ★ Sin refresh token por ahora
- **Referencia:** Plan §2.3 (refresh de 7 días, rotado); Lab §4.2, máquina de estados (`AccesoExpirado`, `PendienteReautenticacion`, `REFRESH_REUTILIZADO`).
- **Se hizo:** solo existe el token de acceso de 15 minutos.
- **Por qué:** se priorizó lo que bloquea al resto del equipo (verificación, auditoría y aprobación de prestadores) dentro de la Fase 4.
- **Impacto:** el usuario vuelve a iniciar sesión cada 15 minutos. Con formularios pendientes sin conexión (RNF-13), la PWA debe pedir el login antes de enviarlos.
- **Estado:** ⏸ planeado para la semana 3 (2 al 8 de noviembre).

### C-21 ★ Revocación por usuario ("revocado-desde")
- **Referencia:** no está en el SRS. El Plan §2.3 habla de revocar el refresh token al cambiar el rol, pero no el token de acceso. Lab §4.2, máquina de estados de la sesión: en la transición "rol modificado o usuario desactivado" dice "jti a Valkey; ROL_MODIFICADO".
- **Se hizo:** `RevocacionTokens.revocar_usuario(usuario_id, desde)` guarda en Valkey `iam:revocado-desde:<usuario_id>` con el segundo del cambio (entero) y un TTL igual a la vida del token más el margen de verificación (15 min + 10 s). Al verificar se leen la llave del `jti` y la del usuario en un solo `MGET`. El token se rechaza si su `jti` está revocado o si su `iat` es menor o igual a esa marca. Aplican la misma regla `verificar`, `require_role` y el logout.
- **Por qué:** sin esto, un usuario degradado o desactivado conserva sus permisos hasta 15 minutos. El laboratorio propone guardar el `jti` en Valkey, pero el IAM no conoce los `jti` de los tokens ya emitidos: no los guarda al emitirlos, y el cambio de rol lo hace el Admin, no la sesión del usuario afectado. Por eso se revoca por usuario con una marca de tiempo, que cubre todos sus tokens sin tener que enumerarlos.
- **Para qué:** que UC27 (cambio de rol o desactivación), el cambio de contraseña y la supresión tengan efecto inmediato en todos los servicios. Se usa `<=` porque `iat` va en segundos: un token emitido en el mismo segundo del cambio también se revoca, y el usuario solo tiene que volver a iniciar sesión. Pasado el TTL, ya no queda ningún token emitido antes del cambio, así que la llave puede expirar. Leer las dos llaves juntas mantiene en una sola ida a Valkey el costo del ForwardAuth.
- **Quién la llama (bloque 4):** UC27, al cambiar el rol o desactivar una cuenta. Revoca **dos veces**:
  1. **Antes del commit**, con `desde` = el momento del cambio. Si Valkey no responde, 503 `SERVICIO_NO_DISPONIBLE` y la transacción se deshace: ni el cambio, ni la bitácora, ni el evento quedan confirmados (falla cerrado, como C-22).
  2. **Después del commit**, con un `desde` nuevo. Si esta falla, solo queda un log de error: el cambio ya está confirmado y la primera marca sigue vigente.
- **Ventana que cierra la segunda revocación:** entre la primera marca y el commit pasan milisegundos, pero el login de ese usuario puede caer en ese intervalo. Como la transacción del Admin aún no es visible, el login lee el rol o el estado viejos, y si el `iat` cae en el segundo siguiente al de la marca, el token queda fuera de ella (`iat > desde`): un usuario degradado o desactivado conservaría un token válido por 15 minutos. La segunda marca, tomada después del commit, es posterior a ese `iat` y lo revoca. Un login posterior al commit ya lee el cambio.
- **El login vuelve a leer la cuenta después del hash (bloque 7, C-53):** la espera de Argon2 puede durar segundos y, si el token saliera con lo leído antes, llevaría el rol viejo con un `iat` posterior a la segunda marca. Ahora lee la cuenta justo antes de emitir: usa el rol vigente, rechaza una cuenta desactivada y rechaza si la contraseña cambió mientras esperaba.
- **Quién más la llama (bloque 6):** el cambio de contraseña (C-52), el restablecimiento (C-28) y la supresión (C-48), con el componente `RevocacionDoble`, extraído de `CambioAdministrativo` sin cambiar su comportamiento. Por la regla `<=`, un token emitido en el mismo segundo también quedaría revocado: por eso el cambio de contraseña no entrega un token nuevo y la PWA inicia sesión otra vez.
- **Estado:** ✅ `d30aef8`: el mecanismo y la verificación (probados también con integración `valkey`). ✅ `8583e38`: UC27 con la doble revocación. ✅ `47308f4`: cambio y restablecimiento de contraseña y supresión.

### C-22 · Logout por revocación del `jti`, fallando cerrado
- **Referencia:** SRS RNF-04; Plan §2.3.
- **Se hizo:** el logout guarda el `jti` en Valkey hasta que el token expira. Si Valkey no responde, se devuelve 503 y nunca se asume "no revocado".
- **Por qué:** un JWT sigue siendo válido hasta su `exp`, aunque el usuario cierre sesión.
- **Para qué:** priorizar la seguridad sobre la disponibilidad en la autorización. El costo es que, con Valkey caído, `verificar` responde 503 `SERVICIO_NO_DISPONIBLE` y, por lo tanto, también todas las rutas protegidas de la plataforma, además de los endpoints del IAM con `require_role` y el logout. Los 503 no se auditan, porque no son accesos indebidos.
- **Estado:** ✅ `3cb0cd7` (logout) y `d30aef8` (la verificación lo aplica con la consulta combinada de C-21).

### C-23 · Auditoría de todos los 401 y 403 propios
- **Referencia:** SRS ESC-04 y RF-09; Lab §1.1.
- **Se hizo:** `verificar`, `require_role` y el logout (C-35) registran `ACCESS_DENIED` / `Denegado` en una transacción propia que se confirma aunque la acción se rechace, como fija el Lab §1.1, con el contenido de C-34. Si PostgreSQL falla, la respuesta sigue siendo 401 o 403 y el error queda en el log (solo el tipo de error, nunca el token).
- **Diferencias de detalle con ESC-04:**
  - ESC-04 pide registrar "IP, timestamp, usuario". El usuario se registra cuando la firma del token es válida: motivos `expirado`, `tipo` y `revocado`. En un token expirado, el `sub` se obtiene con un segundo decode que omite solo `exp` y sigue verificando firma y emisor. `usuario_id` queda nulo únicamente sin token o con una firma que no es válida (mal formado, otra llave, otro emisor), porque en ese caso el `sub` puede ser falso y atribuirle el intento a esa persona sería incorrecto.
  - ESC-04 dice que el rechazo por rol lo audita el módulo afectado publicando `auditoria.registrada`. En los endpoints propios del IAM, el módulo afectado es el propio IAM, y escribe directamente en su bitácora: publicar un evento para consumirlo él mismo solo agregaría un paso que puede fallar.
- **Por qué:** ESC-04 exige el 100 % de los rechazos registrados. Un fallo de la bitácora no puede convertir una denegación en un error 500.
- **Riesgo:** cada 401 escribe una fila, así que un ataque de volumen llena la bitácora. Lo contiene el rate limiting de Traefik (UC32, C-26).
- **Estado:** ✅ `d30aef8` (una prueba por cada tipo de rechazo, con su fila, y con PostgreSQL caído).

### C-24 · Enumeración de cuentas en el registro
- **Referencia:** SRS RNF-04 y Ley 1581.
- **Se hizo:** `POST /register` responde 409 `EMAIL_EN_USO` si el correo ya existe. El login y la recuperación **no** revelan si un correo existe.
- **Por qué:** usabilidad del registro en el prototipo.
- **Mitigación:** rate limiting en Traefik. Alternativa futura: responder siempre 202 y avisar por correo.
- **Estado:** ✅ `8851049`. Riesgo aceptado.

### C-25 · Verificación del correo (`email_verificado`)
- **Referencia:** SRS Tabla XVII.
- **Se hizo:** el campo existe, siempre en `false`, y no hay flujo de verificación. Como consecuencia, el correo no se edita en el perfil (C-51). La recuperación (C-28) no lo tiene en cuenta ni lo cambia: envía el enlace a cualquier cuenta activa.
- **Por qué:** ningún caso de uso del SRS lo exige, y no cabe en la Fase 4. Sin verificación, cambiar el correo permitiría apuntar la recuperación de una cuenta a una dirección que nadie comprobó.
- **Estado:** ⏸ fuera de alcance del prototipo. ✅ `47308f4`: el correo no editable.

### C-26 · Rate limiting (UC32) configurado en el gateway
- **Referencia:** SRS Tabla VI (UC32 asignado al Módulo 1); Plan §2.3 (lo aplica Traefik).
- **Se hizo:** la política (por ejemplo, 5 intentos por minuto por IP en el login) la configura Juan Francisco en `gateway/`. El IAM define y documenta los valores.
- **Por qué:** el límite debe aplicarse antes de que la petición llegue al servicio y para todas las réplicas a la vez.
- **Estado:** 📅 semana 3, con Juan Francisco.

### C-27 ★ Supresión de datos por anonimización
- **Referencia:** SRS §2.4.5 (derecho de supresión, Ley 1581); RNF-10.
- **Se hizo:** `DELETE /api/iam/perfil` (orden y fallos en C-48) deja `email = suprimido+<id>@invalid`, `nombre_completo = "Usuario suprimido"`, `razon_social = NULL`, `activo = false`, un `password_hash` aleatorio y `datos_suprimidos_en`. No borra la fila. Conserva `habeas_data_aceptado_en`, la prueba del consentimiento (C-01), y el rol, que no identifica a nadie.
- **Documentos de verificación:** **borra** de SeaweedFS todo el prefijo `{usuario_id}/`: vigentes, reemplazados (`vigente = false`, C-30) y huérfanos, porque el RUT contiene datos personales. Las filas de `documento_verificacion` se conservan porque las referencian la bitácora y las decisiones del Admin, y su llave S3 solo tiene identificadores. Su `motivo_rechazo` se vacía: es texto libre, puede nombrar a la persona y, a diferencia de la bitácora, sí se puede borrar.
- **Después de la supresión:**
  - El Admin no puede reactivarla ni cambiarle el rol, aprobarla ni rechazarla: 409 `CUENTA_SUPRIMIDA`.
  - El contacto interno y `GET /api/iam/admin/documentos/{id}/url` responden 404, sin fila `DOCUMENT_VIEW`.
  - La cola de prestadores la excluye. En `GET /api/iam/admin/usuarios` aparece como "Usuario suprimido".
  - El login falla como credenciales inválidas (`LOGIN_FAIL` con `usuario_no_existe`), `recuperar` no envía nada y un enlace pedido antes responde 400 `TOKEN_INVALIDO`.
  - `SubirDocumento` rechaza con `CUENTA_SUPRIMIDA` una carga que termina después de la supresión y borra su objeto, que llegó al bucket cuando el prefijo ya se había borrado.
  - El correo original queda libre: la persona puede registrarse otra vez, con una cuenta nueva sin relación con la anterior.
- **Datos que no se pueden borrar:**
  - **Texto libre en la bitácora inmutable (RNF-10):** `detalles.motivo` de `ROLE_CHANGE` y `USER_STATUS_CHANGE` (C-41), `detalles.documentos[].motivo` de `PROVIDER_REJECTED` y `detalles.motivo` de `MODERACION` (review-service). Lo escribe un Admin y podría mencionar a la persona.
  - **`ip_origen` de las filas de la bitácora,** ligada a un `usuario_id` que ya no identifica a nadie por sí solo.
  - **`razon_social` en el `sobre` de `prestador.aprobado` en el outbox,** hasta su purga a los 7 días de publicado (C-09).
- **Revisión de `detalles`:** ninguna fila del IAM ni de catalog, booking o review guarda correos, nombres o razón social como campo; solo identificadores, rutas, códigos y el texto libre anterior. El consumidor guarda `detalles` tal como llega (`auditoria.registrada.v1` no restringe su contenido), así que esto depende de que los productores mantengan esa regla.
- **Límite:** la supresión solo alcanza a `iam_db` y al bucket del IAM. `prestador.suspendido` oculta el perfil en catalog, pero `PRESTADOR_PERFIL` conserva su `razon_social`, `telefono` y `direccion` en `catalog_db`. Para cumplir la Ley 1581 de punta a punta, catalog debe borrarlos, y hoy no recibe ninguna señal que distinga una supresión de una suspensión reversible. Se coordina con Luis Fernando.
- **Por qué:** la bitácora inmutable (RNF-10) referencia al usuario con una llave foránea `RESTRICT`, y borrar la fila rompería la trazabilidad exigida por ESC-04.
- **Para qué:** cumplir la supresión de datos personales conservando la auditoría sin datos que identifiquen a la persona.
- **Estado:** ✅ `47308f4`. ⏸ El borrado del perfil en `catalog_db`, por coordinar con Luis Fernando.

### C-28 · Detalle del flujo de recuperación (UC3)
- **Referencia:** SRS UC3 ("verificación vía correo"), sin más detalle.
- **Se hizo:**
  - **`POST /api/iam/auth/recuperar {email}`:** responde 202 de inmediato y siempre con el mismo cuerpo, también con un formato de correo inválido. Todo lo demás corre en segundo plano (C-50). Si la cuenta existe, está activa y conserva sus datos: reserva la espera, guarda el token, audita y envía el correo.
  - **Token:** `secrets.token_urlsafe(32)`, de un solo uso y válido 30 minutos. En Valkey se guarda `iam:reset:<sha256(token)>` = `usuario_id`, nunca el token en claro. Una solicitud nueva invalida la anterior, con la llave auxiliar `iam:reset-vigente:<usuario_id>`.
  - **Enfriamiento:** `iam:reset-espera:<usuario_id>`, 60 s con `SET NX`. Dentro de ese plazo no sale otro correo, no se invalida el enlace vigente y no se audita.
  - **Correo:** con `aiosmtplib`, en el idioma del usuario (`es` o `en`), en texto plano y HTML, con el nombre escapado, la duración y el aviso de ignorarlo si no lo pidió. El enlace es `{PWA_URL}/restablecer-contrasena?token=<token>`, nunca armado con el `Host` de la petición.
  - **Bitácora:** `PASSWORD_RESET_REQUEST` con el `usuario_id`, antes de enviar: no sale ningún correo sin su fila. Si el correo no existe, no se audita y nunca se registra el correo intentado.
  - **`POST /api/iam/auth/restablecer {token, password}`:** ignora campos extra como `confirmacion`. Valida la política antes de tocar el token (422 `PASSWORD_INVALIDA`, sin gastar el enlace). Comprueba que el token sirve sin gastarlo (inválido, vencido o ya usado: 400 `TOKEN_INVALIDO`, el código que espera `ResetView.vue`), para que un token falso en esta ruta pública no gaste Argon2. Calcula el hash y **después** consume con `GETDEL` atómico: desde el bloque 7, un 503 `SERVICIO_OCUPADO` (C-53) deja el enlace intacto y el reintento funciona; de dos peticiones con el mismo enlace, solo una sigue. La misma respuesta 400 si la cuenta se desactivó o se suprimió después de pedirlo. Guarda el hash, audita `PASSWORD_RESET` y aplica la doble revocación (C-21). 204.
- **Es 400 y no 401:** el 401 `TOKEN_INVALIDO` de las rutas protegidas significa "sesión vencida"; aquí nadie tiene sesión.
- **Costo:** si la base o Valkey fallan después de consumir el token, el enlace ya se gastó y hay que pedir otro.
- **Riesgo:** el token viaja en el query string del enlace. Si Traefik registra la URL completa al servir la PWA, queda en sus logs de acceso; `gateway/` debe omitir el query string de `/restablecer-contrasena`. Se coordina con Juan Francisco.
- **Por qué:** sin estas reglas, el flujo permite averiguar qué correos existen, reutilizar enlaces, llenar el correo de otra persona o envenenar el enlace con un `Host` falso.
- **Para qué:** recuperar la cuenta (UC3) sin revelar quién está registrado y sin que una copia de Valkey sirva para restablecer contraseñas.
- **Estado:** ✅ `47308f4`. 🔨 bloque 7: consumir el token después del hash (C-53), pendiente del commit. ⏸ El límite de peticiones (C-26) y el query string en los logs de Traefik, por coordinar con Juan Francisco.

### C-29 · Reglas de la administración de usuarios
- **Referencia:** SRS UC27 (sin reglas).
- **Se hizo:** endpoints `GET /api/iam/admin/usuarios` (filtros `rol`, `activo` y `q`, que busca en nombre y correo con `ILIKE` escapando `%` y `_`; paginación `pagina` y `tamano` hasta 100), `GET /api/iam/admin/usuarios/{id}`, `PATCH .../{id}/rol` y `PATCH .../{id}/estado`, todos con `require_role(Rol.ADMIN)`. Reglas:
  - Un Admin no puede cambiar su propio rol ni desactivarse a sí mismo: 409 `AUTOGESTION_NO_PERMITIDA`.
  - La plataforma no puede quedarse sin Admins activos: 409 `ULTIMO_ADMIN`. Todo cambio bloquea primero (`FOR UPDATE`, en orden de id) las filas de los Admins activos y después la cuenta afectada, de modo que dos Admins que se quitan el rol a la vez no cuentan al mismo tiempo, y el orden fijo evita interbloqueos.
  - Cambio sin efecto (mismo rol o mismo estado): 200 con la cuenta, sin auditar, revocar ni publicar. Va antes de la regla de autogestión, así que también aplica a la propia cuenta.
  - Bitácora: `usuario_id` = el Admin que actúa; `detalles` = `{usuario_afectado, antes, despues, motivo}`, con solo los campos que cambiaron y el `motivo` recortado a 500 caracteres. La petición acepta hasta 2000 (más es 422), para frenar cuerpos abusivos.
  - Cuenta inexistente: 404 `USUARIO_NO_ENCONTRADO`.
- **Para qué:** evitar perder el acceso administrativo de la plataforma.
- **Estado:** ✅ `8583e38`.

### C-30 · Documentos: tipo, tamaño, vigente y acceso
- **Referencia:** SRS RF-12 ("PDF/imagen"), UC37 y UC28; Plan §4.1 (SeaweedFS, "acceso solo mediante URLs firmadas para el Administrador").
- **Se hizo:**
  - **El archivo pasa por el IAM** (`POST /api/iam/prestador/documentos`, multipart), y no por una URL prefirmada de subida como las imágenes de catalog: así se puede validar el contenido real antes de guardarlo.
  - **Tipo por firma de bytes:** `%PDF-`, `FF D8 FF` (JPG) o `89 50 4E 47 0D 0A 1A 0A` (PNG), al inicio del archivo. La extensión y el `Content-Type` que declara el cliente se ignoran; cualquier otro contenido (un ejecutable renombrado `.pdf`, un HTML, un ZIP) es 422 `TIPO_ARCHIVO_NO_PERMITIDO`.
  - **Tamaño:** hasta 5 MB. El IAM lee a lo sumo 5 MB + 1 byte; si hay más, 413 `ARCHIVO_DEMASIADO_GRANDE`. El cuerpo completo igual llega al servidor antes de validarse: el límite del cuerpo en Traefik (`buffering.maxRequestBodyBytes`) se coordina con Juan Francisco.
  - **Llave del objeto:** `{usuario_id}/{tipo}/{uuid}.{ext}`. Nunca usa el nombre que mandó el cliente y no se puede adivinar.
  - **Un solo vigente por tipo:** un archivo nuevo reemplaza al pendiente o al rechazado, que queda con `vigente = false` y **se conserva** en SeaweedFS para el historial de revisión. Si el vigente ya está aprobado, 409 `DOCUMENTO_APROBADO` sin subir nada (la renovación queda fuera, C-45). La carga y la revisión bloquean la cuenta del prestador, así que nunca se revisa un documento que se está reemplazando.
  - **Orden:** primero SeaweedFS (si no responde, 503 y no se registra nada) y luego la base. Si la base falla después de subir, el objeto queda huérfano y se registra en el log.
  - **Lectura (UC28):** `GET /api/iam/admin/documentos/{id}/url` devuelve una URL prefirmada de 5 minutos, firmada con el host público de SeaweedFS, que fija `ResponseContentType` (el tipo detectado) y `ResponseContentDisposition: inline; filename=<tipo>.<ext>`: el navegador muestra `RUT.pdf`, no la llave interna. Cada consulta queda como `DOCUMENT_VIEW` **antes** de entregar la URL. Si la bitácora no responde, no hay URL: a diferencia de `AUDIT_VIEW` (C-43), aquí sale un dato personal.
  - Auditoría de la carga: `DOCUMENT_UPLOAD` con `{documento_id, tipo, tipo_contenido, tamano_bytes, reemplaza}`.
- **Por qué:** sin estas reglas se pueden subir archivos maliciosos o enormes, y los documentos tributarios quedarían accesibles sin control.
- **Para qué:** que el Admin solo abra PDF o imágenes reales, por un enlace que caduca, y que cada acceso a un documento personal quede registrado.
- **Estado:** ✅ `951bdc4`. ⏸ El límite del cuerpo en Traefik, por coordinar con Juan Francisco.

### C-44 · Sin antivirus en los documentos
- **Referencia:** SRS RF-12 y UC37 (no lo piden).
- **Se hizo:** los documentos no pasan por un antivirus. Mitigaciones:
  1. **Firma de bytes:** solo se aceptan PDF, JPG y PNG reales; un ejecutable, un script o un HTML con otra extensión se rechaza (C-30).
  2. **Tamaño máximo de 5 MB.**
  3. **Bucket privado:** nadie lee un objeto sin una URL firmada (en k3s, con las identidades de infra/, C-46).
  4. **URL de 5 minutos, solo para el Admin:** el prestador nunca recibe un enlace, y cada apertura queda en la bitácora (`DOCUMENT_VIEW`).
  5. **Tipo de contenido fijado al servir** (`ResponseContentType`, el detectado por la firma) y nombre neutro (`RUT.pdf`): el navegador no puede interpretar el archivo como HTML ni como otro tipo.
- **Por qué:** un antivirus (por ejemplo ClamAV) es otro servicio que operar, con firmas que actualizar y memoria que reservar en k3s. Un PDF puede llevar contenido activo, pero un PDF real abierto en el visor del navegador, desde el origen de SeaweedFS y no desde el de la plataforma, no compromete la sesión del Admin.
- **Para qué:** cubrir los riesgos principales (archivos ejecutables o enormes, acceso no autorizado) sin otro componente.
- **Estado:** ⏸ fuera de alcance.

### C-45 · Renovación de documentos aprobados
- **Referencia:** UC37 y UC28 (no prevén la renovación).
- **Se hizo:** un documento vigente aprobado no se reemplaza: 409 `DOCUMENTO_APROBADO`.
- **Por qué:** el RNT se renueva cada año. Permitir otra carga obliga a decidir si el prestador sigue aprobado con el documento viejo mientras se revisa el nuevo, y si catalog debe enterarse. Eso necesita reglas que el SRS no da.
- **Para qué:** que un prestador aprobado no quede en un estado ambiguo. Si su documento vence, el Admin puede suspenderlo (UC27).
- **Estado:** ⏸ fuera de alcance.

### C-47 · Reglas de la verificación de prestadores (UC28)
- **Referencia:** SRS UC28 ("Aprobar / rechazar prestadores de servicios"; precondición: documentos cargados, UC37) y RF-12.
- **Se hizo:**
  - **La decisión es por prestador**, no por documento: `POST /api/iam/admin/prestadores/{id}/aprobar` y `POST .../rechazar` con `{documentos: [{tipo, motivo}]}` (uno o los dos tipos, sin repetir, motivo de 1 a 500 caracteres). Auditan `PROVIDER_APPROVED` y `PROVIDER_REJECTED` (C-19), con `usuario_id` = el Admin.
  - **Estado derivado** de los documentos vigentes: `rechazado` (alguno rechazado), `incompleto` (falta el RNT o el RUT), `aprobado` (los dos aprobados) o `pendiente`. Lo ven el prestador (`GET /api/iam/prestador/documentos`) y el Admin, que filtra la cola con `GET /api/iam/admin/prestadores?estado=pendiente`.
  - **Aprobar** exige los dos vigentes, ninguno rechazado (409 `DOCUMENTOS_INCOMPLETOS` o `DOCUMENTO_YA_REVISADO`). Si ya están aprobados, responde 200 sin auditar ni publicar. Si la cuenta está activa, agrega `prestador.aprobado` al outbox en la misma transacción. Si está inactiva, aprueba sin publicar (C-42).
  - **Rechazar** solo afecta a documentos pendientes (404 `DOCUMENTO_NO_ENCONTRADO` si no hay vigente de ese tipo; 409 `DOCUMENTO_YA_REVISADO` si ya se revisó). No publica nada. A un prestador aprobado se le suspende con UC27.
  - Una cuenta sin rol Prestador: 409 `NO_ES_PRESTADOR`.
- **Por qué:** UC28 habla de aprobar o rechazar **prestadores**, y catalog solo necesita saber si el prestador quedó habilitado. Rechazar por documento permite decirle al prestador exactamente qué corregir.
- **Para qué:** una cola de revisión clara para el Admin y un solo evento por aprobación.
- **Estado:** ✅ `951bdc4`.

### C-48 · Orden de la supresión de datos
- **Referencia:** SRS §2.4.5 y Ley 1581 (derecho de supresión), sin procedimiento.
- **El documento fija:** el derecho, no los pasos.
- **Se hizo:** `DELETE /api/iam/perfil {password}` pide la contraseña (si no coincide, 401 `CREDENCIALES_INVALIDAS` y una fila `DATA_SUPPRESSION` / `Denegado`). Después:
  1. Bloquea los Admins activos y la cuenta; si es el último Admin activo, 409 `ULTIMO_ADMIN`.
  2. Primera revocación; si Valkey falla, 503 sin haber borrado nada.
  3. Borra en SeaweedFS el prefijo `{usuario_id}/`. Si falla, también si `delete_objects` informa un error en un objeto, 503.
  4. En una transacción: datos neutros (C-27), `motivo_rechazo` vacío, `DATA_SUPPRESSION` / `Exito` con `{rol, objetos_borrados}` y `prestador.suspendido` si era un Prestador visible, con `suspendido_por` = el propio usuario.
  5. Commit y segunda revocación (si falla, solo un log). 204.
- **Si algo falla a la mitad:** desde el paso 2 los tokens ya están revocados, aunque la respuesta sea 503. Para repetir, el usuario debe **iniciar sesión otra vez**: su contraseña sigue sirviendo porque nada se confirmó. Si la base falló después del paso 3, sus documentos ya no existen pero la cuenta sigue activa hasta que repita la petición; el borrado es idempotente.
- **El 401 de la contraseña:** es `CREDENCIALES_INVALIDAS`, y la PWA debe distinguirlo por el `code` del 401 `TOKEN_INVALIDO`, que sí significa sesión vencida.
- **`suspendido_por`:** el contrato lo describe como "Administrador que suspendió", pero aquí no actúa ningún Admin. El esquema solo exige un UUID.
- **Por qué:** lo único irreversible fuera de la transacción es el borrado del paso 3. Va después de la primera revocación para que un Valkey caído no deje documentos borrados sin efecto alguno. Va antes del commit para que un fallo de SeaweedFS no deje una cuenta marcada como suprimida con sus documentos todavía en el bucket. Se hace con la cuenta bloqueada para que una carga simultánea no se cuele (C-27). Bloquear los Admins en el mismo orden que UC27 evita interbloqueos y que dos Admins se supriman a la vez y dejen la plataforma sin ninguno.
- **Para qué:** que un fallo nunca deje a la persona creyendo que sus datos se borraron cuando no fue así, sin una tabla ni un proceso más para reintentar.
- **Costo:** el bloqueo de los Admins se mantiene durante la llamada a SeaweedFS (hasta unos segundos si responde lento), y sin SeaweedFS nadie puede suprimir sus datos, ni siquiera quien nunca subió un documento.
- **Estado:** ✅ `47308f4`.

### C-49 · RNF-13 en el perfil: `If-Match` sin `Idempotency-Key`
- **Referencia:** SRS RNF-13 y §3.6 (formularios diferidos: "cada envío lleva una clave de idempotencia" y "las ediciones llevan la versión del registro"); ADR de operación sin conexión; UC4.
- **El documento fija:** `Idempotency-Key` y versión en todos los formularios diferidos, incluido UC4.
- **Se hizo:** `GET` y `PATCH /api/iam/perfil` devuelven `ETag` a partir de `version` y `Cache-Control: no-store`. Si llega `If-Match` y no coincide (acepta `"3"`, `W/"3"`, `3` y `*`; cualquier otro valor no coincide), 409 `VERSION_CONFLICTO`. Sin `If-Match` se acepta, para los clientes en línea. **No usa `Idempotency-Key`.** Bitácora `PROFILE_UPDATE` con `{campos: [...]}`: los nombres, nunca los valores. Sin cambios: 200 sin auditar ni subir la versión.
- **Por qué no hace falta la clave:** `PATCH` fija valores y no agrega nada, así que repetirlo da el mismo resultado. Para que eso se cumpla, la comprobación "sin cambios" va **antes** que la de la versión: si se perdió la respuesta y la cola reenvía el mismo `PATCH` con su `If-Match` ya viejo, encuentra los mismos valores y responde 200, no un 409 falso. Un cambio distinto con esa versión vieja sí es 409. La cola de la PWA (`offlineQueue.js`) envía la clave de todos modos, y el IAM la ignora.
- **Sin conexión no:** el cambio de contraseña (C-52) y la supresión (C-48) exigen confirmar en línea la contraseña y su respuesta, y no deben encolarse.
- **`version` cubre solo lo editable:** cambiar el rol, el estado o la razón social no la sube, para que un cambio del Admin o una carga del RUT no le cause un conflicto a un formulario que no los toca.
- **Para qué:** cumplir la detección de conflictos de RNF-13 sin almacenar claves de idempotencia.
- **Estado:** ✅ `47308f4`.

### C-50 · Fallos del SMTP y trabajo en segundo plano en la recuperación
- **Referencia:** SRS UC3 ("verificación vía correo"), sin comportamiento ante fallos.
- **El documento fija:** nada.
- **Se hizo:** `recuperar` lanza el trabajo con `asyncio.create_task` y responde. Corre en la API, con el mismo `correlation_id`. No usa `BackgroundTasks` de FastAPI porque corre dentro del ciclo de la petición y retiene la conexión keep-alive: quien envíe otra petición por esa conexión notaría la espera del SMTP. Si Valkey, la base o el SMTP fallan, queda un log de error (sin el correo) y la métrica `iam_recuperacion_solicitudes_total{resultado}` (`enviado`, `no_elegible`, `enfriamiento`, `fallo_valkey`, `fallo_smtp`, `fallo_base`). Si no se pudo enviar, descarta el token y la espera, para que se pueda pedir otra vez de inmediato. Al apagarse, la API espera hasta 15 s las tareas en curso.
- **Por qué:** para que ni el tiempo ni un 503 revelen si el correo existe, nada que dependa de esa respuesta puede correr dentro de la petición.
- **Costo:** el usuario recibe 202 aunque el correo nunca salga, y solo le queda volver a pedirlo. Si el pod muere con la tarea en curso, se pierde sin rastro más allá de la fila de la bitácora, si alcanzó a escribirse. No hay reintentos ni outbox: un enlace de 30 minutos reenviado tarde sirve de poco, y el usuario puede repetir la solicitud.
- **Riesgo:** las tareas no tienen tope. Una ráfaga contra `recuperar` acumula consultas a la base, y solo la contiene el rate limiting de Traefik (C-26), todavía pendiente.
- **Para qué:** que la recuperación no sirva para enumerar cuentas, con los fallos visibles para quien opera la plataforma. Conviene una alerta sobre `fallo_smtp`.
- **Estado:** ✅ `47308f4`. 🔨 bloque 7: Secret y salida a SMTP en k3s, pendiente del commit. ⏸ La alerta: sus reglas viven en `infra/`, fuera del bloque 7.

### C-51 · Campos del perfil que no se editan
- **Referencia:** SRS UC4 ("Gestionar perfil de usuario"), sin lista de campos.
- **El documento fija:** nada.
- **Se hizo:** `PATCH /api/iam/perfil` solo admite `nombre` e `idioma`, con las reglas del registro (`NOMBRE_INVALIDO`; otro idioma, 422 `VALIDACION`). Enviar `email`, `razon_social` o cualquier otro campo responde 422 `VALIDACION`, en vez de un 200 que no los cambió. La API llama `nombre` al `nombre_completo` de la base, como el contrato de contacto (C-15).
- **Por qué:** el correo no se edita porque no hay verificación de correo (C-25). La razón social va con la carga del RUT (C-07).
- **Para qué:** que la dirección de recuperación siempre sea la registrada y que la razón social no se separe del documento que la respalda.
- **Estado:** ✅ `47308f4`.

### C-52 · `POST /perfil/contrasena` y 422 `PASSWORD_ACTUAL_INCORRECTA`
- **Referencia:** lo comunicado al frontend: `/perfil/password` y 401 si la contraseña actual es incorrecta. El SRS no lo fija.
- **El documento fija:** nada; es una diferencia frente a lo acordado de palabra.
- **Se hizo:** `POST /api/iam/perfil/contrasena {password_actual, password_nueva}`, con los nombres en español de las demás rutas propias. Contraseña actual incorrecta: **422** `PASSWORD_ACTUAL_INCORRECTA`, con su fila `PASSWORD_CHANGE` / `Denegado`. Si es correcta: política (422 `PASSWORD_INVALIDA`), nuevo hash Argon2id, `PASSWORD_CHANGE` / `Exito` y doble revocación (C-21). 204, sin token nuevo.
- **Por qué:** con un 401, la PWA lo confundiría con una sesión vencida y sacaría al usuario, que solo se equivocó al escribir.
- **Para qué:** mostrar el error en el campo correcto. El frontend debe ajustar la ruta y el código, e iniciar sesión otra vez tras el 204.
- **Estado:** ✅ `47308f4`. ⏸ Avisar del cambio al frontend.

---

## 4. Operación y despliegue

### C-31 · Proceso worker separado
- **Referencia:** SRS §3.6.1 y Lab, Figura 6 (solo muestran `iam-service`).
- **Se hizo:** la misma imagen corre como API (`app.main`) y como worker (`python -m app.worker`), cada uno en su propio Deployment. El worker consume la cola durable `iam.auditoria` con el consumidor de catalog: mismos argumentos de cola, reintentos a 1, 5 y 25 s, y DLQ `turismo.dead-letter`. Expone `/metrics` en el puerto 9101 (`WORKER_METRICS_PORT`), que sirve también de sonda de vida. Si RabbitMQ no responde al arrancar, reintenta con espera creciente hasta 30 s. Desde el bloque 4 también corre el relay del outbox (C-09), en paralelo con los consumidores.
- **Por qué:** la API atiende el ForwardAuth de *cada* petición protegida de la plataforma. Si el consumo de eventos compite con ella por los recursos, sube la latencia de todo el sistema.
- **Para qué:** escalar la API con su HPA (2 a 4 réplicas) sin duplicar consumidores, y que reiniciar la API no interrumpa la auditoría. Es el mismo patrón que usa catálogo.
- **Estado:** ✅ `2d011e0` (consumidor, probado también de punta a punta contra RabbitMQ 4 y PostgreSQL). ✅ `8583e38` (relay del outbox). 🔨 bloque 7: `k8s/base/deployment-worker.yaml` y sonda sobre `:9101/metrics`, desplegados en un k3s temporal, pendiente del commit. ⏸ El servicio `iam-worker` en `infra/docker-compose.yml`: el bloque está en el README, sección "Despliegue", para Luis Fernando.

### C-32 ★ Sondas `/health` y `/health/live` separadas
- **Referencia:** Plan §7.3 (`/health` para readiness y liveness); Lab 3, Figura 10.
- **El documento fija:** una sola ruta `/health` para las sondas de readiness y liveness.
- **Se hizo:**
  - `/health` comprueba PostgreSQL (`SELECT 1`) y Valkey (`PING`), cada uno con un timeout de 2 s, y responde 503 si alguno falla (`checks: {database, valkey}`). Lo consultan Prometheus y Blackbox para medir la disponibilidad (RNF-01).
  - `/health/live` no consulta nada y responde `{"status": "ok"}`.
  - El `HEALTHCHECK` del Dockerfile apunta a `/health/live`. En k8s, startup, readiness y liveness también. Readiness: cada 2 s, `failureThreshold` 2 y `timeoutSeconds` 1. Una réplica caída sale en 4 s y una colgada en 5 s; con el `timeoutSeconds` 2 de catalog serían 6 s, por encima de ESC-01. Es un cálculo a partir de los valores: no se midió el aislamiento en un clúster.
  - **Quién lee `/health`:** el Plan §7 dice que Blackbox entra por el gateway, pero el gateway solo enruta `/api/iam`. Por eso la NetworkPolicy lo deja entrar directo desde `observabilidad` (C-54).
  - **Un pico de logins no saca réplicas:** medido en C-53, que explica por qué k3s usa 1 cupo de Argon2 para proteger a `verificar`.
- **Por qué:** `verificar`, que es el ForwardAuth de toda la plataforma, no usa PostgreSQL, y si Valkey cae ya responde 503 por su cuenta (C-22). PostgreSQL y Valkey son compartidos por todas las réplicas: si la readiness dependiera de ellos, su caída sacaría a todas las réplicas del enrutamiento a la vez, y una falla parcial (sin login ni registro, pero con `verificar` funcionando) se volvería una caída total de la plataforma. Por la misma razón, una liveness con dependencias reiniciaría en cadena todas las réplicas sin que eso arregle la base.
- **Para qué:** que una caída de PostgreSQL degrade solo las rutas que lo necesitan, mientras `/health` sigue mostrando la falla en el monitoreo (RNF-01, ESC-01).
- **Estado:** ✅ `dcf6496` (rutas y `HEALTHCHECK`). 🔨 bloque 7: sondas en `k8s/base/deployment-api.yaml`, desplegadas en un k3s temporal, pendiente del commit.

### C-33 · Endpoint temporal `GET /api/iam/admin/ping`
- **Referencia:** no está en el SRS ni en el Plan.
- **Se hizo:** `GET /api/iam/admin/ping`, protegido con `require_role(Rol.ADMIN)`, responde `{"ok": true}`. Un Turista recibe 403 `ROL_INSUFICIENTE` y deja su fila en la bitácora; sin token, 401.
- **Por qué:** permite probar el RBAC (403) de punta a punta, incluido `scripts/smoke_test.py`, antes de que existan los endpoints de administración.
- **Estado:** ✅ `d30aef8`. ✅ `8583e38`: eliminado (responde 404). Las pruebas de RBAC y `scripts/smoke_test.py` usan ahora `GET /api/iam/admin/usuarios`.

### C-34 · Contenido de las filas `ACCESS_DENIED` (motivo interno y columna "plantilla")
- **Referencia:** SRS Tabla XVII (`detalles`: "Metadatos contextuales", sin estructura); ESC-04; Plan §6.1.
- **Se hizo:** `detalles` tiene una estructura fija según el tipo de rechazo:
  - 401: `{"motivo", "metodo", "uri"}`. `motivo` es `sin_token`, `invalido`, `expirado`, `revocado` o `tipo`. Un `Authorization` con un esquema distinto de `Bearer` cuenta como `sin_token`. En `verificar`, `metodo` y `uri` son `X-Forwarded-Method` y `X-Forwarded-Uri` de Traefik (nulos si faltan), y la `uri` se guarda sin query string ni fragmento, recortada a 2048 caracteres. En `require_role` y el logout se usan el método y la ruta de la propia petición.
  - 403: `{"rol", "requeridos", "metodo", "ruta", "plantilla"}`. `ruta` es la ruta concreta sin query y `plantilla` es la ruta declarada en FastAPI (p. ej. `/api/iam/admin/usuarios/{id}`).
  - El motivo **no** sale en la respuesta: el cliente siempre recibe el mismo 401 `TOKEN_INVALIDO`.
- **Por qué:** sin el motivo no se distingue, al revisar la bitácora en UC33, un token vencido (normal) de una firma falsificada o de un token revocado que se sigue usando (sospechoso). El query string puede llevar datos personales o tokens. Sin la plantilla, cada id distinto en la ruta aparece como un endpoint diferente. Devolver el motivo al cliente le diría a un atacante qué parte del token falló.
- **Para qué:** filtrar y agrupar los rechazos por causa y por endpoint en UC33 sin guardar datos sensibles, y cumplir la medida de ESC-04 con información útil para investigar.
- **Estado:** ✅ `d30aef8`.

### C-35 · Auditoría del 401 del logout
- **Referencia:** SRS ESC-04; Plan §4.1 (el logout va detrás de ForwardAuth) y §6.1.
- **Se hizo:** `POST /api/iam/logout` registra `ACCESS_DENIED` con `{"motivo", "metodo", "uri"}` cuando rechaza el token, con el mismo caso de uso que `require_role`. Si la firma era válida (p. ej. un token ya revocado), la fila lleva el `usuario_id`.
- **Por qué:** ESC-04 exige el 100 % de los rechazos. Cuando el logout pasa por ForwardAuth, `verificar` rechaza primero y registra la fila, así que la petición no llega al logout y no hay duplicados. Pero el logout también se puede invocar sin pasar por ForwardAuth: llamadas dentro del clúster, una configuración del gateway que lo deje público (C-11 conserva `/api/iam/logout`, fuera de `/auth/`) o un token revocado entre `verificar` y el logout. Sin esta auditoría, esos rechazos no quedarían registrados.
- **Para qué:** que la medida de ESC-04 no dependa de la configuración del gateway.
- **Estado:** ✅ `d30aef8`.

### C-36 ★ 401 para token inválido y 403 para rol insuficiente
- **Referencia:** SRS Tabla V, fila de RF-09 ("Intentos de acceso no autorizados devuelven HTTP 403"); SRS Tabla XXII, criterio de verificación de RF-09 ("retorna HTTP 401 o 403 y genera un registro"); SRS ESC-04 ("HTTP 401 sin token válido, HTTP 403 con rol insuficiente").
- **Se hizo:** el SRS es inconsistente consigo mismo: la Tabla V dice 403, mientras que la Tabla XXII y ESC-04 dicen 401 o 403. Se implementó la versión verificable, la de la Tabla XXII y ESC-04. Sin token o con un token inválido, expirado o revocado, la respuesta es 401 `TOKEN_INVALIDO` con `WWW-Authenticate: Bearer`. Con un token válido y un rol que no corresponde, la respuesta es 403 con el código nuevo `ROL_INSUFICIENTE` ("No tiene permisos para realizar esta acción.").
- **Por qué:** la Tabla XXII es la que define cómo se prueba RF-09, y ESC-04 la concreta. Según HTTP (RFC 9110), 401 significa "no autenticado" y 403 "autenticado sin permiso". Traefik solo reenvía la petición cuando el ForwardAuth responde 2xx; cualquier otra respuesta se devuelve tal cual al cliente.
- **Para qué:** que la PWA distinga entre "vuelva a iniciar sesión" (401) y "no tiene permiso" (403), y que los demás servicios usen el mismo criterio en su RBAC.
- **Estado:** ✅ `d30aef8`. Sigue marcada con ★ para unificar la Tabla V con la Tabla XXII y ESC-04 en el SRS v1.2.

### C-37 · IP de origen solo desde proxies de confianza
- **Referencia:** SRS ESC-04 y Tabla XVII (`ip_origen`); RNF-10.
- **Se hizo:** la IP que se guarda en la bitácora (login, registro, logout y cada `ACCESS_DENIED`) es la de la conexión. Solo se toma de `X-Forwarded-For` cuando la petición viene de un proxy listado en `FORWARDED_ALLOW_IPS` (uvicorn con `--proxy-headers`). Si el valor no es una IP válida, se guarda nulo, porque la columna es `INET`.
- **Por qué:** `X-Forwarded-For` lo puede escribir cualquier cliente. Si se aceptara de cualquiera, un atacante elegiría la IP que queda registrada. Detrás de Traefik, la IP de la conexión es la del gateway, no la del usuario.
- **Para qué:** que la IP de la bitácora sea la real y confiable (ESC-04). El valor en k3s y lo que falta confirmar están en C-56.
- **Estado:** ✅ `8851049` (registro) y `3cb0cd7` (login, logout, `--proxy-headers` y `FORWARDED_ALLOW_IPS=127.0.0.1` en el Dockerfile). ✅ `d30aef8` (`verificar` y `require_role`). 🔨 bloque 7: el valor para k3s en el ConfigMap, pendiente del commit.

### C-38 · Usuario desconocido o IP inválida en `auditoria.registrada`
- **Referencia:** contrato `auditoria.registrada.v1` (`usuario_id` uuid, `ip_origen` string); SRS Tabla XVII (`usuario_id` FK a `USUARIO`, `ip_origen`); Plan §4.3 (DLQ).
- **El documento fija:** nada sobre qué hacer si el `usuario_id` no existe en `iam_db` o si `ip_origen` no es una IP. La llave foránea (`ON DELETE RESTRICT`) y el tipo `INET` rechazarían la fila, y el evento acabaría en la DLQ tras tres reintentos.
- **Se hizo:**
  - **`usuario_id` desconocido:** la fila se guarda con `usuario_id` nulo y el valor recibido en `detalles.usuario_id_no_registrado`. Se resuelve en la misma sentencia del `INSERT` (`CASE WHEN EXISTS (SELECT 1 FROM usuario …)`), sin capturar el error de la llave foránea.
  - **`ip_origen` que no es una IP suelta** (texto, rango con máscara o IPv6 con zona): se guarda nula y el texto queda en `detalles.ip_origen_invalida`.
  - A la DLQ solo va lo que no cumple el contrato: sobre o versión inválidos, `additionalProperties`, `resultado` fuera del enum, `usuario_id` que no es UUID, `ip_origen` en `null` o que no es string, y `accion` vacía o de más de 50 caracteres (la longitud de la columna).
- **Por qué:** un evento así sí cumple el contrato. Mandarlo a la DLQ sacaría de la bitácora un hecho que ocurrió y dejaría la auditoría incompleta (RNF-10). Un `usuario_id` que el IAM no conoce es justamente lo que conviene ver en UC33.
- **Para qué:** que ningún evento válido se pierda de la bitácora y que la anomalía quede visible y filtrable en `detalles`.
- **Estado:** ✅ `2d011e0`.

### C-39 · `fecha` de los eventos recibidos es su `occurred_at`
- **Referencia:** SRS Tabla XVII (`fecha`); `contracts/events/envelope.v1.json` (`occurred_at`).
- **El documento fija:** `fecha` como la fecha del registro, sin distinguir entre los eventos propios y los recibidos.
- **Se hizo:** en los eventos de otros servicios, `fecha` es el `occurred_at` del sobre, es decir, el momento del hecho en el servicio de origen y no el de la inserción. En las filas propias sigue siendo `now()`. Un `occurred_at` sin zona horaria no cumple RFC 3339 y va a la DLQ.
- **Por qué:** un evento puede llegar minutos u horas tarde (broker caído, reintentos, outbox atrasado). Con la fecha de inserción, la bitácora mostraría un acceso denegado o una exportación en un momento en que no ocurrió.
- **Para qué:** que UC33 ordene y filtre por el momento real de cada hecho y que las filas cuadren con los logs del servicio de origen (ESC-04).
- **Estado:** ✅ `2d011e0`.

### C-40 · Los eventos de la DLQ se revisan a mano
- **Referencia:** Plan §4.3 y ADR-008 (tras 3 intentos fallidos, el mensaje va a `turismo.dead-letter`).
- **El documento fija:** que el mensaje va a la DLQ, pero no qué pasa después.
- **Se hizo:** nada reprocesa la DLQ automáticamente. Cada mensaje llega con las cabeceras `x-cola` (`iam.auditoria`), `x-intentos` y `x-error`, y se revisa a mano desde la consola de administración de RabbitMQ (puerto 15672). Si el problema se corrigió, se vuelve a publicar desde ahí con la clave `auditoria.registrada`. Repetirlo es seguro: la base descarta el `event_id` ya guardado (C-04). La métrica `iam_eventos_consumidos_total{resultado="dlq"}` cuenta los que llegan.
- **Por qué:** lo que llega a la DLQ no cumple el contrato o falló tres veces seguidas. Reintentarlo solo lo haría fallar en bucle, y decidir si un mensaje roto se corrige o se descarta requiere a una persona.
- **Para qué:** que ningún evento se pierda en silencio y que la revisión quede en manos de quien opera la plataforma. Conviene una alerta sobre la métrica `dlq`.
- **Estado:** ✅ `2d011e0`. ⏸ La alerta en Grafana: sus reglas viven en `infra/`, fuera del bloque 7.

### C-46 · Bucket y credenciales del IAM en SeaweedFS
- **Referencia:** Plan §4.1 y §7 (SeaweedFS en `turismo-datos`); `infra/docker-compose.yml`.
- **Se hizo:** el IAM usa el bucket privado `documentos-verificacion` (`S3_BUCKET`), con dos endpoints: `S3_ENDPOINT_URL` (interno, para subir) y `S3_ENDPOINT_PUBLICO` (el que ve el navegador del Admin; la firma incluye el host). En desarrollo, `docker-compose.dev.yml` usa `chrislusf/seaweedfs:3.80` (la misma versión que `infra/`) **sin archivo de identidades**: acepta cualquier credencial (incluso vacía) y no comprueba firmas, así que las credenciales por defecto (`iam_access_dev` / `iam_secret_dev`) son solo de relleno. El bucket se crea con `uv run python -m scripts.crear_bucket`.
- **Por qué:** en `infra/` (y en k3s) SeaweedFS usa un archivo de identidades (`-s3.config`), como el de catalog. Allí, sin una identidad propia con permisos sobre su bucket, el IAM no puede subir ni firmar, y es ese archivo el que hace privado el bucket.
- **Para qué:** que en k3s el bucket y las credenciales del IAM los provea `infra/` (Luis Fernando): una identidad `iam` con acciones `Read:documentos-verificacion`, `Write:documentos-verificacion` y `List:documentos-verificacion`, y sus llaves en el Secret `iam-secretos` como `S3_ACCESS_KEY` y `S3_SECRET_KEY`. El IAM no crea el bucket en producción.
- **Permiso de borrado (riesgo del bloque 6, cerrado):** probado en un SeaweedFS 3.80 efímero con identidades. Con esas tres acciones, la identidad sube, lee, lista, firma URL y borra con `delete_objects`: `Write` incluye el borrado, y `List` hace falta porque la supresión lista el prefijo (C-48). Escribir en otro bucket responde `AccessDenied`.
- **★ Riesgo: el bucket no queda privado con el archivo actual.** `services/catalog-service/dev/seaweedfs-s3.json`, que monta `infra/`, le da `Read` a `anonymous` sin limitarlo a un bucket. Probado: con ese `anonymous`, **un RUT se lee sin firma** (200) con solo conocer su llave; con `Read:catalogo-imagenes`, responde 403 y la URL firmada sigue funcionando. Sin ese cambio no se cumple la mitigación 3 de C-44. La llave no se puede adivinar (lleva dos UUID), pero no es un control de acceso.
- **Estado:** ✅ `951bdc4`: configuración y script de desarrollo. 🔨 bloque 7: `S3_*` en el ConfigMap y `iam-secretos`, pendiente del commit. ⏸ Identidad, bucket, Secret y limitar `anonymous` en `infra/`, por coordinar con Luis Fernando.

### C-53 · Argon2 fuera del bucle de eventos, con cupos y sin ocupar conexiones
- **Referencia:** SRS ESC-01 y ESC-02; relacionada con la readiness de C-32 y con el límite de memoria de `k8s/base/deployment-api.yaml`.
- **El documento fija:** nada sobre la concurrencia del hash.
- **Se hizo:**
  - **Revisión:** los 8 usos (registro, login, verify de relleno, rehash, cambio y restablecimiento de contraseña, y los dos de la supresión) **ya corrían en un hilo** con `asyncio.to_thread`. Ninguno estaba dentro del bucle de eventos.
  - **Semáforo:** `Argon2PasswordHasher` tiene `hash_limitado` y `verify_limitado`, con un `asyncio.Semaphore` de `ARGON2_CONCURRENCIA_MAXIMA` cupos, y los casos de uso solo usan esas. El setting vale 4 por defecto (mínimo 1), y **el ConfigMap de k3s lo fija en 1** por la medición de abajo. Es uno por réplica, en `app.state`. Como es de `asyncio`, quien espera no ocupa un hilo ni frena el bucle, ni le quita sitio a las subidas a SeaweedFS, que usan el mismo pool de hilos.
  - **Tope de la espera:** `ARGON2_ESPERA_MAXIMA_SEGUNDOS` (10 por defecto). Si se pasa, 503 `SERVICIO_OCUPADO` con `Retry-After: 2`, en lugar de seguir en cola. No afecta a un cálculo ya empezado. El pico de CPU es la señal para que el HPA agregue réplicas.
  - **Sin efectos sobre la cuenta:** el 503 sale antes de auditar, revocar o escribir nada. En el login no cuenta como `LOGIN_FAIL`, tampoco con un correo inexistente, así que no revela si la cuenta existe. El cambio de contraseña y la supresión no revocan los tokens, a diferencia de un 503 de Valkey en la supresión (C-48). En `restablecer` el enlace no se gasta (C-28).
  - **Conexión liberada antes del hash:** login y registro calculaban dentro del `async with uow`, con una conexión tomada. Ahora la sueltan antes.
  - **Login:** vuelve a leer la cuenta después del hash (C-21).
  - **Registro:** si otro registro con el mismo correo entra durante la espera, responde la `UNIQUE` (409 `EMAIL_EN_USO`, como antes).
- **Por qué:** un hash reserva 64 MiB, y sin tope una ráfaga podía superar el límite de memoria. Con el semáforo y la conexión tomada, habría sido peor: el pool tiene 15 conexiones como máximo, las peticiones en cola lo agotarían, y los 401 de `verificar` esperarían hasta 30 s para escribir su fila (C-23).
- **Para qué:** que un pico de logins no saque réplicas sanas ni deje sin ForwardAuth al resto de la plataforma, y que el límite de 1 Gi tenga margen.
- **Pruebas:** `tests/api/test_hash_no_bloquea_api.py` comprueba que, con un login calculando y otro en el semáforo, `/health/live` y `verificar` responden antes de que termine el hash y que ninguno retiene una transacción. Se comprobó que fallan al forzar el hash dentro del bucle y al volver a calcular con la conexión abierta. `tests/api/test_servicio_ocupado_api.py` comprueba el 503 con el semáforo real, su `Retry-After`, que no deja `LOGIN_FAIL`, que el cupo se devuelve y que no tiene efectos en las demás rutas.
- **Medición** (imagen real con `--cpus=1 --memory=1g`, 120 logins en tandas de 40, con sondas de timeout de 1 s). **Es una sola corrida en Docker Desktop, con Valkey y PostgreSQL fuera del contenedor: sirve para comparar configuraciones, no como capacidad de producción. Se repite en la Fase 5.** Las tres primeras filas no tenían tope de espera:

  | Cupos | Tope de espera | `/health/live`: timeouts (máx. seguidos) | `verificar`: timeouts (máx. seguidos) | `verificar`: mediana | Login: mediana (máx.) | 503 | Total | Memoria máx. vista |
  |---|---|---|---|---|---|---|---|---|
  | 4 | Sin tope | 1 (1) | 12 de 102 (5) | 297 ms | 12,1 s (21,3 s) | 0 | 61,5 s | 348 MiB |
  | 2 | Sin tope | 0 (0) | 3 de 129 (1) | 110 ms | 9,3 s (16,8 s) | 0 | 50,3 s | 220 MiB |
  | 1 | Sin tope | 0 (0) | 0 de 231 (0) | 47 ms | 7,8 s (37,5 s) | 0 | 65,7 s | 164 MiB |
  | **1 (k3s)** | **10 s** | **0 (0)** | **0 de 108 (0)** | **78 ms** | **6,4 s (12,3 s)** | **11 de 120** | **32,7 s** | **156 MiB** |

- **Lo que muestra la medición:**
  - **La readiness aguanta:** nunca hay dos fallos seguidos, así que ninguna réplica sale del enrutamiento, en ninguna configuración.
  - **La memoria tiene margen:** como máximo 348 MiB frente a 1 Gi.
  - **★ Con varios cupos y 1 CPU, `verificar` se degrada.** Cada hash usa 4 hilos: 4 hashes agotan la cuota de CPU del contenedor y lo frenan entero, aunque el bucle no esté bloqueado. El semáforo acota la memoria, no esa CPU. Con un solo cupo no hay timeouts y más cupos no dan una ganancia clara de rendimiento. `verificar` es lo que no puede fallar: por eso k3s usa 1 cupo.
  - **El tope acota la espera:** el peor login baja de 37,5 s a 12,3 s (10 s de espera más el cálculo). Los totales no son comparables entre sí: varían de una corrida a otra, y en la última 11 logins no se calcularon.
- **Costo:**
  - En un pico, algunos logins válidos reciben 503 y deben reintentar. La PWA debe respetar `Retry-After` y no mostrarlo como credenciales inválidas.
  - Con 1 cupo, una réplica calcula un hash a la vez, y cada uno tarda del orden de medio segundo con 1 CPU. La capacidad de login crece con las réplicas del HPA, no con los cupos.
  - Si el límite de CPU sube, hay que revisar `ARGON2_CONCURRENCIA_MAXIMA`.
- **Sin probar:** que el HPA agregue réplicas durante un pico (necesita varios minutos de carga en un clúster con `metrics-server`). Hasta que las nuevas réplicas estén listas, los 503 siguen saliendo. Se comprueba en la Fase 5.
- **Estado:** 🔨 bloque 7: implementado y probado, pendiente del commit. ⏸ Repetir la medición y comprobar el HPA en la Fase 5.

### C-54 · NetworkPolicy: Blackbox directo y salida sin restringir
- **Referencia:** Plan §7.4 ("Prometheus → `/metrics` de todos", y cada servicio → su base, Valkey y RabbitMQ) y §7 (Blackbox consulta `/health` a través del gateway).
- **El documento fija:** negar la entrada por defecto, y una salida acotada a las dependencias de cada servicio.
- **Se hizo:**
  - **Entrada a la API (8001):** Traefik, solo el worker de catalog (no su API), Prometheus y Blackbox.
  - **Entrada al worker (9101):** solo Prometheus.
  - **Salida:** sin restringir, igual que catalog.
  - **Comprobado en un k3s temporal, con kube-router aplicando las políticas:** el worker de catalog, Prometheus y Blackbox llegan. La API de catalog, un pod sin esa etiqueta en `turismo-app`, otro en `default` y uno de `observabilidad` con otra etiqueta son rechazados. No se probó con tráfico real de Traefik, que usa la misma forma de regla; la etiqueta `app.kubernetes.io/name: traefik` sí se confirmó en k3s.
- **Por qué Blackbox entra directo:** el gateway solo enruta `/api/iam` y `/health` no está bajo ese prefijo. Sin esta regla nadie podría medir la disponibilidad del IAM (RNF-01). La etiqueta `app.kubernetes.io/name: blackbox-exporter` es una suposición, porque aún no existe ese despliegue.
- **Por qué la salida no se restringe:** el host del SMTP es externo y las direcciones de `turismo-datos` no están definidas todavía; una lista errónea rompería el login o los correos. Se mantiene la misma convención que catalog.
- **Riesgo:** un pod comprometido puede sacar datos o hablar con cualquier destino. La NetworkPolicy es de la capa de red, no de rutas: quien pueda entrar al puerto 8001 también ve `/internal` y `/metrics`. Por eso ni Prometheus ni Blackbox deberían usarlos con otro fin, y `/internal` tiene su propia defensa contra llamadas por Traefik (C-15).
- **Observado:** kube-router tarda unos segundos en registrar un pod nuevo, y mientras tanto sus conexiones se rechazan aunque tenga permiso. Quien llama debe reintentar; el worker de catalog ya lo hace con los correos.
- **Para qué:** limitar quién llega al IAM sin bloquear el monitoreo ni los correos.
- **Estado:** 🔨 bloque 7: implementado, pendiente del commit. ⏸ Confirmar la etiqueta de Blackbox con Juan Francisco. ⏸ Restringir la salida cuando `turismo-datos` tenga sus direcciones definitivas.

### C-55 · Migraciones en el initContainer de la API
- **Referencia:** Plan §7; C-03.
- **El documento fija:** nada sobre cuándo corren las migraciones.
- **Se hizo:** `alembic upgrade head` corre como initContainer de cada pod de la API, con la misma imagen, y `migrations/env.py` toma `pg_advisory_xact_lock` antes de migrar, el mismo patrón que catalog con su propia llave. El worker no migra: se apoya en que la API ya lo hizo.
- **Por qué:** es el mismo patrón que catalog y no requiere un Job aparte. Sin el candado, que el IAM no tenía, dos pods nuevos pueden migrar a la vez y chocar en el primer despliegue.
- **Para qué:** que ningún pod atienda con un esquema viejo.
- **Riesgos:**
  - Durante un rolling update los pods viejos siguen atendiendo, así que cada migración debe ser compatible hacia atrás.
  - El worker puede arrancar antes de la migración y fallar hasta que termine; se reinicia solo.
  - **La app y las migraciones usan las mismas credenciales**, así que el rol de la app es el dueño de las tablas. El `REVOKE` de C-03 es una barrera débil: ese rol podría volver a darse los permisos, y lo que protege de verdad la bitácora son los triggers. Separar los roles requeriría otro Secret.
- **Estado:** 🔨 bloque 7: implementado y comprobado en un k3s temporal contra la base de desarrollo (ya en `head`), pendiente del commit. No se probó el choque real de dos migraciones simultáneas.

### C-56 · `FORWARDED_ALLOW_IPS` en k3s
- **Referencia:** C-37; SRS ESC-04 y Tabla XVII (`ip_origen`).
- **El documento fija:** registrar la IP de origen, sin decir cómo obtenerla detrás del gateway.
- **Se hizo:** el ConfigMap fija `FORWARDED_ALLOW_IPS: 10.42.0.0/16`, el rango de pods por defecto de k3s. La imagen conserva `127.0.0.1` por defecto. Comprobado: el nodo del k3s temporal usó `10.42.0.0/24`, y uvicorn 0.54 acepta el CIDR (`10.42.3.7` confía, `190.24.10.5` no).
- **Por qué un rango y no una IP:** los pods de Traefik cambian de IP al reiniciarse.
- **Para qué:** que la bitácora guarde la IP del cliente y no la del gateway (ESC-04).
- **Riesgos por confirmar con Juan Francisco:**
  - Si el clúster usa otro `--cluster-cidr`, la IP de la bitácora será la de Traefik.
  - Si Traefik recibe el tráfico por el balanceador de k3s (`svclb`) con `externalTrafficPolicy: Cluster`, el origen que ve es interno y esa es la IP que escribe. Hace falta `Local`, o un `forwardedHeaders.trustedIPs` si hay otro proxy delante.
  - El rango confía en todo pod del clúster, no solo en Traefik. Lo acota la NetworkPolicy, que solo deja llegar a Traefik, al worker de catalog, a Prometheus y a Blackbox.
- **Estado:** 🔨 bloque 7: implementado, pendiente del commit. ⏸ Confirmar el rango y la política de tráfico con Juan Francisco. No se comprobó con tráfico real a través de Traefik.

### C-57 ★ Contrato `iam.yaml` generado desde la app, en OpenAPI 3.1
- **Referencia:** `contracts/openapi/README.md` ("OpenAPI 3.0", escrito por el responsable antes de implementar, con errores `{error, message, correlation_id}`).
- **El documento fija:** un archivo acordado antes de implementar, en OpenAPI 3.0, con el formato común de errores.
- **Se hizo:**
  - `uv run python -m scripts.exportar_openapi` genera `contracts/openapi/iam.yaml`, con 20 rutas, y una prueba falla si quedó desactualizado.
  - Queda en **3.1.0**, la versión que produce FastAPI; los demás contratos están en 3.0.3.
  - Salen del esquema `/internal` (ya estaba fuera), `/health`, `/health/live` y `/metrics`. Otra prueba exige que todas las rutas empiecen por `/api/iam/`.
  - **Se completó lo que faltaba en los routers:** 503 de Valkey en toda ruta protegida, 401 y 403 en `GET /prestador/documentos`, 404 en el perfil, y `CUENTA_SUPRIMIDA` en las descripciones.
  - **El 422 real:** FastAPI documentaba `HTTPValidationError`, un formato que el servicio nunca responde; `app/api/openapi.py` lo reemplaza por `ErrorResponse` también en `/docs`.
  - `verificar` lee `X-Forwarded-Method` y `X-Forwarded-Uri` de los encabezados y no como parámetros, sin cambiar su comportamiento, para que no figuren como parte de la API ni aparezca un 422 imposible.
- **Por qué:** el servicio se construyó antes que el contrato, y un archivo escrito a mano se desactualizaría. Convertir a 3.0 a mano es frágil (`anyOf` con `null` frente a `nullable`).
- **Para qué:** que el contrato sea siempre el comportamiento real y que la PWA pueda confiar en él.
- **Límites:** 3.1 puede no leerse en herramientas que solo aceptan 3.0. Los errores siguen el formato de C-12, no el común. Las rutas de C-11 difieren del Plan.
- **Estado:** 🔨 bloque 7: implementado y probado, pendiente del commit. ⏸ Reflejar la versión y el modo de generación en `contracts/openapi/README.md`, con Luis Fernando.

---

## Pendiente de reflejar en los documentos del equipo

Coordinar con Luis Fernando, que es el responsable de la arquitectura y de los contratos:

- **SRS v1.2:** C-04, C-07, C-08, C-17 (y las reglas de UC27 de C-29 y de UC28 de C-47), C-20, C-27 y C-36 (unificar la Tabla V con la Tabla XXII y ESC-04), además de los campos de C-01, C-02, C-05 y C-06, y de C-38 y C-39 en la descripción de `BITACORA_AUDITORIA`. En ESC-04, aclarar que el IAM audita directamente sus propios 403 y que el usuario solo se registra si la firma del token es válida (C-23).
- **Plan:** §4.1 (C-11, C-12 y el riesgo de C-13: la confianza en `X-Usuario-*` exige eliminarlos en las rutas públicas), §2.3 (C-19 y C-21) §4.3 (C-38 y C-40: qué va a la DLQ y que se revisa a mano) y §7.3 (C-32: readiness y liveness en `/health/live`, y `/health` solo para el monitoreo). §7 y §7.4: Blackbox no puede entrar por el gateway a `/health`, y la salida de red no se restringe (C-54).
- **Lab:** Figuras 1 y 2 y especificación ACME (C-04); Figura 6 (C-31); Figura 10 (C-32: readiness y liveness en `/health/live`); §4.2 (C-20 y C-21: en la transición "rol modificado o usuario desactivado", cambiar "jti a Valkey" por la revocación por usuario con revocado-desde).
- **Gateway (`gateway/`, Juan Francisco):** `authResponseHeaders` con `X-Usuario-Id` y `X-Usuario-Rol`, y eliminación de esos encabezados en toda petición entrante (C-13). Límite del cuerpo (`buffering.maxRequestBodyBytes`, unos 6 MB) en `POST /api/iam/prestador/documentos` (C-30). `/api/iam/auth/recuperar` y `/restablecer` públicas, con rate limiting (C-26, C-50); `/api/iam/perfil` con ForwardAuth; el query string de `/restablecer-contrasena` fuera de los logs de acceso (C-28). Solo `PathPrefix(/api/iam)` y sin `trustForwardHeader` en el ForwardAuth. Confirmar el rango de pods y `externalTrafficPolicy` (C-56), la etiqueta de Blackbox (C-54), y los dominios de `PWA_URL` y `S3_ENDPOINT_PUBLICO`, que debe llegar a SeaweedFS desde el navegador del Admin. Ejemplos en el README del servicio, sección "Despliegue".
- **Frontend (`frontend/`, Juan Francisco):** usar `POST /perfil/contrasena` y `PASSWORD_ACTUAL_INCORRECTA`, y volver a iniciar sesión tras el 204 (C-52). Distinguir `CREDENCIALES_INVALIDAS` en la supresión (C-48). No encolar sin conexión el cambio de contraseña ni la supresión (C-49). Ante un 503 `SERVICIO_OCUPADO`, reintentar según `Retry-After` y no mostrarlo como credenciales inválidas; aplica a login, registro, restablecimiento, cambio de contraseña y supresión (C-53). El 400 `TOKEN_INVALIDO` y los cuerpos de recuperar y restablecer ya coinciden.
- **Infra (`infra/`, Luis Fernando):** **limitar `anonymous` a `Read:catalogo-imagenes`, o los documentos quedan legibles sin firma (C-46).** Identidad `iam` con `Read`, `Write` y `List` sobre `documentos-verificacion`, crear ese bucket y el Secret con sus llaves. El rol `iam_user` en `iam_db`, que hoy existe sin ese usuario, con un script que corre solo en un volumen nuevo (C-55). Los servicios `iam-migraciones`, `iam-service` e `iam-worker` en el compose y los jobs de Prometheus (C-31). Las alertas de `fallo_smtp` y de la DLQ (C-40, C-50). El nombre del Service de SeaweedFS en `turismo-datos`. Bloques listos en el README del servicio, sección "Despliegue".
- **Contratos (`contracts/`, Luis Fernando):** en `prestador.suspendido.v1.json`, aclarar que el IAM no envía `motivo` (C-41), o quitarlo del esquema, y que `suspendido_por` es el propio usuario en una supresión (C-48). En `openapi/README.md`, que `iam.yaml` se genera desde la app y está en OpenAPI 3.1 (C-57).
- **Catalog (`services/catalog-service/`, Luis Fernando):** que `DirectorioUsuariosIam` envíe `X-Correlation-ID` con el `correlation_id` del evento al pedir el contacto (C-15). Borrar `razon_social`, `telefono` y `direccion` de `PRESTADOR_PERFIL` cuando un prestador suprime sus datos, lo que requiere una señal distinta de `prestador.suspendido` (C-27). Tratar el 404 del contacto de un usuario suprimido sin reintentar (C-15).
- **Registro de decisiones:** proponer un ADR del IAM que reúna C-04, C-16, C-21, C-27 y C-34.
