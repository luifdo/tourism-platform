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
- **Se hizo:** se agregaron `motivo_rechazo`, `revisado_por` y `revisado_en`.
- **Por qué:** UC28 permite rechazar, pero el modelo no guarda ni el motivo ni quién decidió.
- **Para qué:** que el prestador sepa qué corregir y que cada decisión del Admin sea trazable.
- **Estado:** ✅ esquema en `8851049`; se usan desde el bloque 5.

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
- **Estado:** ✅ `2d011e0` (columna y eventos de otros servicios). 🔨 bloque 3: middleware implementado y probado, pendiente del commit.

### C-06 · Columna `idioma` en `USUARIO`
- **Referencia:** SRS Tabla XVII; RF-10; `contracts/openapi/iam-interno.yaml`.
- **Se hizo:** `idioma VARCHAR(2) NOT NULL DEFAULT 'es'` con `CHECK (idioma IN ('es', 'en'))`; las cuentas existentes quedan en `es`. Es opcional en `POST /api/iam/register` (otro valor responde 422 `VALIDACION`) y se devuelve en su respuesta; como el login usa el mismo esquema, también aparece en su `usuario`. La ruta interna de contacto (C-15) lo entrega a catalog. La edición queda para el perfil del bloque 6.
- **Por qué:** RF-10 exige la plataforma en dos idiomas, pero el idioma de la PWA vive en el navegador. Los correos los envía el worker de catálogo, que no tiene acceso al navegador.
- **Para qué:** que los correos de reservas (UC36) y de recuperación (UC3) lleguen en el idioma del usuario.
- **Estado:** 🔨 bloque 3: columna, registro y contacto implementados y probados, pendiente del commit. 📅 bloque 6: edición en el perfil.

### C-07 ★ `razon_social` guardada en `iam_db`
- **Referencia:** SRS Tabla XVIII (`razon_social` pertenece a `PRESTADOR_PERFIL`, en `catalog_db`); contrato `prestador.aprobado.v1`.
- **Se hizo:** el IAM pide `razon_social` al cargar el RUT (UC37), la guarda en `usuario` y la envía en `prestador.aprobado`.
- **Por qué:** catálogo crea el perfil al consumir el evento y necesita un nombre comercial desde el primer momento. Quien la conoce en ese momento es el IAM, porque viene del RUT.
- **Para qué:** que el perfil del prestador nazca completo. Catálogo sigue siendo el dueño del perfil y puede editarlo después.
- **Estado:** 📅 bloque 5.

### C-08 ★ `prestador_id` igual al `usuario_id`
- **Referencia:** SRS Tabla XVIII (`PRESTADOR_PERFIL.id` es una PK propia de catálogo); contratos `prestador.aprobado.v1` y `prestador.suspendido.v1`.
- **Por qué:** el contrato exige un `prestador_id` que asigna el IAM. Un identificador nuevo obligaría a crear otra tabla y a mantenerlo estable cuando un prestador se suspende y se vuelve a aprobar.
- **Para qué:** un identificador estable sin estructuras adicionales; catálogo reactiva el mismo perfil.
- **Estado:** 📅 bloque 5. Acordado con Luis Fernando.

### C-09 · Tabla `outbox` en `iam_db`
- **Referencia:** SRS §3.6.2, nota (el patrón outbox es opcional); Plan §4.3 y §4.4; ADR-008.
- **Por qué:** si el proceso falla entre el commit de la aprobación y la publicación, `prestador.aprobado` se pierde y el prestador queda aprobado en el IAM pero sin perfil en catálogo.
- **Para qué:** garantizar la entrega de `prestador.aprobado` y `prestador.suspendido`. Es el mismo patrón que ya usa catálogo.
- **Estado:** 📅 bloque 4.

### C-10 · Columna `datos_suprimidos_en` (ver C-27)
- **Estado:** 📅 bloque 6.

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
- **Estado:** ✅ formato base; `correlation_id` 🔨 bloque 3, implementado y probado, pendiente del commit.

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
  - **Usuario inactivo:** 200, para que siga recibiendo los avisos de sus reservas (por ejemplo, la cancelación). Los datos suprimidos serán 404 (bloque 6, C-27).
  - **Inexistente:** 404 `USUARIO_NO_ENCONTRADO`. **UUID mal formado:** 422 `VALIDACION`.
  - **Defensa adicional a la NetworkPolicy:** si la petición trae `X-Forwarded-For` o `X-Forwarded-Host` (llegó por Traefik), responde el mismo 404 `USUARIO_NO_ENCONTRADO` sin consultar la base, aunque el usuario exista o el UUID esté mal formado. Así, una regla de enrutamiento mal configurada no expone la ruta ni permite enumerar usuarios.
  - **Trazabilidad:** métrica `iam_contacto_consultas_total{resultado}` (`ok`, `no_encontrado`, `rechazado_proxy`) y una línea de log JSON por consulta con `usuario_id`, `resultado` y `correlation_id`, nunca el correo. No escribe fila en la bitácora.
- **Por qué:** los eventos solo llevan identificadores, de modo que los datos personales no viajan por el bus (Ley 1581). Aun así, catálogo necesita el correo para enviar UC36.
- **Para qué:** que catálogo pida el correo en el momento del envío y no lo guarde. Así el único lugar con el dato sigue siendo `iam_db`.
- **Por qué basta con el log y no va a la bitácora:** por volumen, porque hay una consulta por cada correo de reserva: la bitácora (de solo inserción, UC33) crecería con filas de rutina que no son acciones de un usuario. Y por trazabilidad: si el worker de catalog envía como `X-Correlation-ID` el `correlation_id` del evento que originó el correo, la línea del log se cruza en Loki con ese evento y con la fila de la bitácora que haya generado. La métrica permite alertar ante un pico de `no_encontrado` o ante cualquier `rechazado_proxy`.
- **Riesgo:** hoy `DirectorioUsuariosIam` de catalog (`develop`) no envía `X-Correlation-ID`: el IAM genera un UUID nuevo por consulta y la línea del log no se cruza con el evento. Hace falta que catalog agregue el encabezado con su `correlation_id_actual()`. Se coordina con Luis Fernando.
- **Estado:** 🔨 bloque 3: implementado y probado, pendiente del commit. Propuesto por Luis Fernando. El envío del encabezado desde catalog queda ⏸ pendiente, por coordinar con él.

### C-16 · El gateway valida con `verificar` y no con el JWKS
- **Referencia:** SRS §3.3.3 y ESC-04; Plan §2.3 y §6.1; Lab §4.1, Figura 12; ADR-007.
- **Se hizo:** el ForwardAuth llama a `GET /api/iam/auth/verificar`. Es conforme al SRS, al Plan §6.1, al ADR-007 y al Lab §4.1, Figura 12 (`verificar` → 200 + `X-Usuario-Id`, `X-Usuario-Rol`); se registra aquí porque el equipo preguntó por la alternativa. El endpoint es público en el router (la validación es el propio endpoint) y comprueba firma RS256, emisor, expiración con 10 s de margen, `typ = access` y revocación por `jti` y por usuario (C-21). Si el token es válido responde 200 con cuerpo vacío, los encabezados de C-13 y `Cache-Control: no-store`, **sin consultar PostgreSQL**: solo hace una lectura en Valkey. Si no, responde 401 `TOKEN_INVALIDO` y escribe una fila en la bitácora (C-23, C-34).
- **Por qué:** con el JWKS solo se comprueba la firma. No se puede saber si el token fue revocado, ni registrar el 401 en la bitácora, y ESC-04 exige el 100 % de los rechazos registrados.
- **Para qué:** cumplir ESC-04 y que el logout y los cambios de rol tengan efecto de inmediato. Dejar PostgreSQL fuera del camino feliz mantiene baja la latencia que el ForwardAuth suma a cada petición protegida (ESC-02). `no-store` evita que una respuesta de identidad quede en alguna caché intermedia.
- **Costo:** cada petición protegida depende de Valkey; si no responde, el resultado es 503 (C-22).
- **Estado:** ✅ `d30aef8` (pruebas de API y `scripts/smoke_test.py`).

### C-17 · Evento `prestador.suspendido`
- **Referencia:** SRS Tabla XIV (solo `prestador.aprobado`); `contracts/events/prestador.suspendido.v1.json`.
- **Por qué:** cuando el Admin desactiva a un prestador (UC27), su oferta seguiría visible en el catálogo.
- **Para qué:** que catálogo oculte el perfil y los servicios, y que la reserva deje de aceptarlos.
- **Estado:** 📅 bloque 4.

### C-18 · Valores de `resultado` en el contrato de auditoría
- **Referencia:** SRS Tabla XVII (`Exito`, `Denegado`, `Error`); contrato `auditoria.registrada.v1` (`EXITO`, `DENEGADO`, `ERROR`).
- **Se hizo:** la base conserva los valores del SRS y el consumidor traduce los del contrato (`EXITO` → `Exito`, etc.). Un `resultado` fuera del enum del contrato, incluidos los valores del SRS, no cumple el contrato y va a la DLQ.
- **Por qué:** el contrato del equipo usa mayúsculas.
- **Para qué:** respetar el SRS sin obligar a los productores a cambiar.
- **Estado:** ✅ `2d011e0`.

### C-19 · Nombres de las acciones de la bitácora
- **Referencia:** SRS Tabla XVII (`LOGIN_FAIL`, `ROLE_CHANGE`, `ACCESS_DENIED`, `EXPORT`); Plan §2.3 (`LOGIN_FALLIDO`, `ROL_MODIFICADO`, `PRESTADOR_VALIDADO`); Lab §4.2 (`LOGIN_EXITOSO`, `LOGIN_FALLIDO`, `REFRESH_REUTILIZADO`).
- **Se hizo:** se usan los nombres del SRS. Las acciones nuevas siguen su mismo estilo (inglés, mayúsculas con guion bajo): `LOGIN_SUCCESS`, `LOGOUT`, `USER_REGISTER`, `USER_STATUS_CHANGE`, `PROVIDER_APPROVED`, `PROVIDER_REJECTED`, `DOCUMENT_UPLOAD`, `DOCUMENT_VIEW`, `PROFILE_UPDATE`, `PASSWORD_CHANGE`, `PASSWORD_RESET_REQUEST`, `PASSWORD_RESET`, `DATA_SUPPRESSION`. Las que llegan de otros módulos (`ZONA_CREADA`, etc.) se guardan tal como vienen.
- **Por qué:** los tres documentos no coinciden entre sí. El SRS es el acuerdo de mayor jerarquía.
- **Para qué:** un vocabulario consistente para filtrar en UC33. El Plan y el laboratorio deberían actualizarse con estos nombres.
- **Estado:** ✅ los existentes; el resto, en cada bloque.

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
- **Estado:** ✅ `d30aef8`: el mecanismo y la verificación (probados también con integración `valkey`). Quienes llaman a `revocar_usuario` (UC27, cambio de contraseña, supresión) llegan en los bloques 4 y 6.

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
- **Se hizo:** el campo existe, siempre en `false`, y no hay flujo de verificación.
- **Por qué:** ningún caso de uso del SRS lo exige, y no cabe en la Fase 4.
- **Estado:** ⏸ fuera de alcance del prototipo.

### C-26 · Rate limiting (UC32) configurado en el gateway
- **Referencia:** SRS Tabla VI (UC32 asignado al Módulo 1); Plan §2.3 (lo aplica Traefik).
- **Se hizo:** la política (por ejemplo, 5 intentos por minuto por IP en el login) la configura Juan Francisco en `gateway/`. El IAM define y documenta los valores.
- **Por qué:** el límite debe aplicarse antes de que la petición llegue al servicio y para todas las réplicas a la vez.
- **Estado:** 📅 semana 3, con Juan Francisco.

### C-27 ★ Supresión de datos por anonimización
- **Referencia:** SRS §2.4.5 (derecho de supresión, Ley 1581); RNF-10.
- **Se hizo:** `DELETE /api/iam/perfil` reemplaza el correo, el nombre y la razón social por valores neutros, desactiva la cuenta y registra `datos_suprimidos_en`. No borra la fila.
- **Por qué:** la bitácora inmutable (RNF-10) referencia al usuario con una llave foránea `RESTRICT`, y borrar la fila rompería la trazabilidad exigida por ESC-04.
- **Para qué:** cumplir la supresión de datos personales conservando la auditoría sin datos que identifiquen a la persona.
- **Estado:** 📅 bloque 6.

### C-28 · Detalle del flujo de recuperación (UC3)
- **Referencia:** SRS UC3 ("verificación vía correo"), sin más detalle.
- **Se hizo:** `recuperar` responde siempre 202. El token es de un solo uso, dura 30 minutos y en Valkey se guarda su SHA-256, no el token. Hay 60 s de espera entre solicitudes. El enlace apunta a la PWA (`/restablecer-contrasena?token=`) y al restablecer se revocan las sesiones anteriores.
- **Por qué:** sin estas reglas, el flujo permite averiguar qué correos existen, reutilizar enlaces o abusar del envío de correos.
- **Estado:** 📅 bloque 6.

### C-29 · Reglas de la administración de usuarios
- **Referencia:** SRS UC27 (sin reglas).
- **Se hizo:** un Admin no puede cambiar su propio rol ni desactivarse a sí mismo, y el sistema no puede quedarse sin Admins activos (409 `ULTIMO_ADMIN`).
- **Para qué:** evitar perder el acceso administrativo de la plataforma.
- **Estado:** 📅 bloque 4.

### C-30 · Documentos: tipo, tamaño, vigente y acceso
- **Referencia:** SRS RF-12 ("PDF/imagen") y UC37.
- **Se hizo:** se aceptan PDF, JPG y PNG de hasta 5 MB, validando el contenido real del archivo y no solo la extensión. Hay un solo documento vigente por tipo: si se carga uno nuevo, reemplaza al pendiente o al rechazado. El Admin los abre con URL prefirmadas de 5 minutos, y cada consulta queda en la bitácora.
- **Por qué:** sin estas reglas se pueden subir archivos maliciosos o enormes, y los documentos tributarios quedarían accesibles sin control.
- **Estado:** 📅 bloque 5.

---

## 4. Operación y despliegue

### C-31 · Proceso worker separado
- **Referencia:** SRS §3.6.1 y Lab, Figura 6 (solo muestran `iam-service`).
- **Se hizo:** la misma imagen corre como API (`app.main`) y como worker (`python -m app.worker`), cada uno en su propio Deployment. El worker consume la cola durable `iam.auditoria` con el consumidor de catalog: mismos argumentos de cola, reintentos a 1, 5 y 25 s, y DLQ `turismo.dead-letter`. Expone `/metrics` en el puerto 9101 (`WORKER_METRICS_PORT`), que sirve también de sonda de vida. Si RabbitMQ no responde al arrancar, reintenta con espera creciente hasta 30 s. La publicación del outbox se le agrega en el bloque 4 (C-09).
- **Por qué:** la API atiende el ForwardAuth de *cada* petición protegida de la plataforma. Si el consumo de eventos compite con ella por los recursos, sube la latencia de todo el sistema.
- **Para qué:** escalar la API con su HPA (2 a 4 réplicas) sin duplicar consumidores, y que reiniciar la API no interrumpa la auditoría. Es el mismo patrón que usa catálogo.
- **Estado:** ✅ `2d011e0` (consumidor, probado también de punta a punta contra RabbitMQ 4 y PostgreSQL). 📅 bloque 4: relay del outbox. 📅 bloque 7: Deployment y sondas en k3s. ⏸ El servicio `iam-worker` en `infra/docker-compose.yml` se coordina con quien mantiene `infra/`.

### C-32 ★ Sondas `/health` y `/health/live` separadas
- **Referencia:** Plan §7.3 (`/health` para readiness y liveness); Lab 3, Figura 10.
- **El documento fija:** una sola ruta `/health` para las sondas de readiness y liveness.
- **Se hizo:**
  - `/health` comprueba PostgreSQL (`SELECT 1`) y Valkey (`PING`), cada uno con un timeout de 2 s, y responde 503 si alguno falla (`checks: {database, valkey}`). Lo consultan Prometheus y Blackbox para medir la disponibilidad (RNF-01).
  - `/health/live` no consulta nada y responde `{"status": "ok"}`.
  - El `HEALTHCHECK` del Dockerfile apunta a `/health/live`. En k8s, readiness y liveness también apuntarán a `/health/live` (bloque 7).
- **Por qué:** `verificar`, que es el ForwardAuth de toda la plataforma, no usa PostgreSQL, y si Valkey cae ya responde 503 por su cuenta (C-22). PostgreSQL y Valkey son compartidos por todas las réplicas: si la readiness dependiera de ellos, su caída sacaría a todas las réplicas del enrutamiento a la vez, y una falla parcial (sin login ni registro, pero con `verificar` funcionando) se volvería una caída total de la plataforma. Por la misma razón, una liveness con dependencias reiniciaría en cadena todas las réplicas sin que eso arregle la base.
- **Para qué:** que una caída de PostgreSQL degrade solo las rutas que lo necesitan, mientras `/health` sigue mostrando la falla en el monitoreo (RNF-01, ESC-01).
- **Estado:** 🔨 bloque 3: rutas y `HEALTHCHECK` implementados y probados, pendiente del commit. 📅 bloque 7: sondas en los manifiestos de k3s.

### C-33 · Endpoint temporal `GET /api/iam/admin/ping`
- **Referencia:** no está en el SRS ni en el Plan.
- **Se hizo:** `GET /api/iam/admin/ping`, protegido con `require_role(Rol.ADMIN)`, responde `{"ok": true}`. Un Turista recibe 403 `ROL_INSUFICIENTE` y deja su fila en la bitácora; sin token, 401.
- **Por qué:** permite probar el RBAC (403) de punta a punta, incluido `scripts/smoke_test.py`, antes de que existan los endpoints de administración.
- **Estado:** ✅ `d30aef8`. Se elimina en el bloque 4.

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
- **Para qué:** que la IP de la bitácora sea la real y confiable (ESC-04). En k3s, `FORWARDED_ALLOW_IPS` debe contener el rango de los pods de Traefik (bloque 7).
- **Estado:** ✅ `8851049` (registro) y `3cb0cd7` (login, logout, `--proxy-headers` y `FORWARDED_ALLOW_IPS=127.0.0.1` en el Dockerfile). ✅ `d30aef8` (`verificar` y `require_role`). 📅 bloque 7: el valor de `FORWARDED_ALLOW_IPS` para k3s (rango de los pods de Traefik) se fija en los manifiestos del servicio.

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
- **Para qué:** que ningún evento se pierda en silencio y que la revisión quede en manos de quien opera la plataforma. Conviene una alerta sobre la métrica `dlq` (bloque 7).
- **Estado:** ✅ `2d011e0`. 📅 bloque 7: alerta en Grafana.

---

## Pendiente de reflejar en los documentos del equipo

Coordinar con Luis Fernando, que es el responsable de la arquitectura y de los contratos:

- **SRS v1.2:** C-04, C-07, C-08, C-17, C-20, C-27 y C-36 (unificar la Tabla V con la Tabla XXII y ESC-04), además de los campos de C-01, C-02, C-05 y C-06, y de C-38 y C-39 en la descripción de `BITACORA_AUDITORIA`. En ESC-04, aclarar que el IAM audita directamente sus propios 403 y que el usuario solo se registra si la firma del token es válida (C-23).
- **Plan:** §4.1 (C-11, C-12 y el riesgo de C-13: la confianza en `X-Usuario-*` exige eliminarlos en las rutas públicas), §2.3 (C-19 y C-21) §4.3 (C-38 y C-40: qué va a la DLQ y que se revisa a mano) y §7.3 (C-32: readiness y liveness en `/health/live`, y `/health` solo para el monitoreo).
- **Lab:** Figuras 1 y 2 y especificación ACME (C-04); Figura 6 (C-31); Figura 10 (C-32: readiness y liveness en `/health/live`); §4.2 (C-20 y C-21: en la transición "rol modificado o usuario desactivado", cambiar "jti a Valkey" por la revocación por usuario con revocado-desde).
- **Gateway (`gateway/`, Juan Francisco):** `authResponseHeaders` con `X-Usuario-Id` y `X-Usuario-Rol`, y eliminación de esos encabezados en toda petición entrante (C-13).
- **Catalog (`services/catalog-service/`, Luis Fernando):** que `DirectorioUsuariosIam` envíe `X-Correlation-ID` con el `correlation_id` del evento al pedir el contacto (C-15).
- **Registro de decisiones:** proponer un ADR del IAM que reúna C-04, C-16, C-21, C-27 y C-34.
