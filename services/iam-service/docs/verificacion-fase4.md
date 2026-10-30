# iam-service: verificación antes del PR a `develop` (Fase 4)

**Base verificada:** `3c09bac` más los cambios locales del bloque 8 y de los arreglos previos al PR. El e2e en k3d corrió antes de esos arreglos y no se repitió. Las pruebas `archivo::prueba` son relativas a `tests/`; las evidencias, a `docs/evidencias/`. "e2e x" es el escenario x de `e2e-k3d.txt`.

**Estados:** ✅ cumplido · ⚠ parcial · ❌ no cumplido · ⏸ fuera de alcance

**Resumen de la matriz:** 36 filas: 25 ✅, 9 ⚠, 1 ❌ y 1 ⏸. Los hallazgos están en la sección 5.

## 1. Matriz de cumplimiento

### Casos de uso

| Requisito | Qué exige | Cómo se cumple | Evidencia | Estado | Entrada |
|---|---|---|---|---|---|
| UC1 | Registro de 18+ con UC6 (SRS Tabla VI) | `POST /api/iam/register`, solo Turista y Prestador | `api/test_register_api.py::test_registro_201`; `b1-smoke.txt`; e2e a | ✅ | C-01, C-11, C-24 |
| UC2 | Iniciar sesión y obtener token de acceso | `POST /api/iam/login`, JWT RS256 de 15 min | `api/test_login_api.py::test_login_200`; e2e a | ✅ | C-11, C-20 |
| UC3 | Recuperar contraseña por correo | `auth/recuperar` y `auth/restablecer` | `api/test_recuperacion_api.py::test_recuperar_envia_el_correo_y_audita`; e2e f | ✅ | C-28, C-50 |
| UC4 | Gestionar el perfil | `GET` y `PATCH /perfil`, `POST /perfil/contrasena` | `api/test_perfil_api.py::test_cualquier_rol_ve_su_perfil`; `b1-smoke.txt` | ✅ | C-49, C-51, C-52 |
| UC6 | Aceptar la política de datos | Obligatorio en el registro, con fecha y `CHECK` en la base | `unit/test_registrar_usuario.py::test_habeas_data_se_valida_primero` | ✅ | C-01, C-03 |
| UC27 | Administrar usuarios y roles | `/admin/usuarios`, rol y estado, con revocación inmediata | `api/test_admin_usuarios_api.py::test_desactivar_prestador`; e2e a y c | ✅ | C-21, C-29, C-41, C-42 |
| UC28 | Aprobar o rechazar prestadores, publica `prestador.aprobado` | `/admin/prestadores/{id}/aprobar` y `rechazar` | `api/test_documentos_api.py::test_aprobar_publica_y_audita`; e2e a | ✅ | C-08, C-47 |
| UC32 | Gestionar políticas de seguridad y rate limiting (Traefik) | La política se probó en un gateway de prueba. Es configuración, sin pantalla para el Admin, y la real falta en `gateway/` | e2e i | ⚠ | C-26 |
| UC33 | Consultar la bitácora | `GET /admin/bitacora`, con filtros y su propia auditoría | `api/test_bitacora_api.py::test_otro_rol_403`; e2e b y d | ✅ | C-19, C-43 |
| UC37 | Cargar RNT y RUT | `POST /prestador/documentos` con validación por firma de bytes | `api/test_documentos_api.py::test_subir_201`; e2e a | ✅ | C-02, C-07, C-30 |

### Requisitos y escenarios

| Requisito | Qué exige | Cómo se cumple | Evidencia | Estado | Entrada |
|---|---|---|---|---|---|
| RF-08 (IAM) | Incorporación de prestadores en máximo 3 pasos (Tablas V y XXII) | API: registro, carga y aprobación del Admin. Los pasos los ve la PWA | e2e a; la demostración en la interfaz es del frontend | ⚠ | — |
| RF-09 | RBAC, 401/403 y registro en bitácora | `verificar`, `require_role`, `ACCESS_DENIED` | `api/test_rbac_api.py::test_turista_403_con_fila_en_la_bitacora`; e2e b | ✅ | C-13, C-16, C-23, C-36 |
| RF-12 | Adjuntar y revisar RNT y RUT | Carga, cola de revisión, URL firmada de 5 min | `unit/test_revision_prestador.py::test_abrir_sin_bitacora_no_entrega_url`; e2e a y h | ✅ | C-30, C-44, C-45 |
| RNF-01 | `/health` para la disponibilidad ≥ 99 % | `/health` con PostgreSQL y Valkey. El monitoreo no está desplegado, así que la disponibilidad no se mide | `test_health.py::test_health_ok_con_postgresql_y_valkey`; `b1-smoke.txt` | ⚠ | C-32, C-54 |
| RNF-03 | OpenAPI 3.0 (§3.4) | `iam.yaml` generado desde la app, en **3.1** | `unit/test_contrato_openapi.py::test_iam_yaml_coincide_con_la_app` | ⚠ | C-57 |
| RNF-04 | JWT, Argon2id, Ley 1581, análisis estático | RS256, Argon2id con RFC 9106 (64 MiB, t=3, p=4), consentimiento | `unit/test_password_hasher.py::test_hash_uses_argon2id`; `b3-bandit.txt`; `b3-pip-audit.txt`; `b3-trivy.txt` | ✅ | C-21, C-22, C-53 |
| RNF-10 | Bitácora inmutable, consulta en panel | Triggers y `REVOKE`, UC33, consumidor de eventos | `integration/test_bitacora_inmutable.py`; `b1-bitacora-solo-insercion.txt`; `integration/test_consumidor_auditoria.py::test_guarda_el_evento_y_el_duplicado_no`; e2e d | ✅ | C-03, C-04, C-38, C-39, C-40 |
| RNF-12 | Contenedores, manifiestos versionados, rolling update sin 5xx, `/health` y `/metrics` | `k8s/`, misma imagen, `maxUnavailable: 0`, preStop | e2e j: 0 errores en 1272 peticiones, p95 de 16 ms, rollout de 10 s | ✅ | C-31, C-32, C-55 |
| RNF-13 (perfil) | Formulario diferido, una sola vez, versión con 409 (§3.6.6) | `ETag` e `If-Match`, repetir el `PATCH` no duplica. La prueba sin conexión es de la PWA | `api/test_perfil_api.py::test_patch_cambia_audita_solo_los_nombres_y_sube_la_version` | ⚠ | C-49 |
| ESC-04 | 401 y 403, 100 % registrado con IP, fecha y usuario | Cada rechazo probado deja su fila. **La IP es la que Traefik ve,** y en k3d no es la del cliente real | `api/test_verificar_api.py::test_postgresql_caido_en_un_rechazo_sigue_siendo_401`; e2e b | ⚠ | C-23, C-34, C-35, C-56; F-08 |

### Ley 1581 (SRS §2.4.5)

| Requisito | Qué exige | Cómo se cumple | Evidencia | Estado | Entrada |
|---|---|---|---|---|---|
| Consentimiento | Informado y previo, con prueba | `habeas_data_aceptado_en`, `CHECK` en la base | `unit/test_registrar_usuario.py::test_habeas_data_se_valida_primero` | ✅ | C-01, C-03 |
| Actualización | Derecho a actualizar | Nombre e idioma. **El correo no se edita** | `api/test_perfil_api.py::test_reglas_del_registro_y_campos_que_no_se_editan` | ⚠ | C-25, C-51 |
| Supresión | Derecho a suprimir | Anonimiza y borra documentos. **Catalog conserva el perfil** | `api/test_supresion_api.py::test_suprime_los_datos_y_borra_los_objetos`; e2e g | ⚠ | C-27, C-48 |
| Almacenamiento cifrado | "Almacenamiento cifrado de datos sensibles" | **No implementado:** RUT y RNT en SeaweedFS y correos en PostgreSQL van sin cifrado de aplicación ni de objeto. La propuesta está escrita y la decisión del equipo sigue en ⏸ (C-58); hasta que se aplique, el requisito no se cumple | Búsqueda de `ServerSideEncryption` en `app/` y `k8s/`: sin resultados | ❌ | C-58; F-01 |

### Laboratorio 3

| Punto | Qué exige | Cómo se cumple | Evidencia | Estado | Entrada |
|---|---|---|---|---|---|
| Fig. 1 y 2, ACME | Cola `iam.auditoria` | Consumidor con la cola durable | e2e d | ✅ | C-04, C-31 |
| Fig. 1 y 2, ACME | DLQ `turismo.dead-letter` | Payload inválido, directo a la DLQ | `integration/test_consumidor_auditoria.py::test_fuera_del_contrato_va_directo_a_la_dlq`; e2e d | ✅ | C-40 |
| Fig. 1 y 2, ACME | Sin duplicados | `UNIQUE(event_id)` | e2e d: dos publicaciones, una fila | ✅ | C-04 |
| §4.1 | `verificar` devuelve `X-Usuario-*` | Sí, y Traefik los propaga; los falsos no llegan | e2e b | ✅ | C-13, C-16 |
| §4.2 | Máquina de estados de la sesión | Sin refresh por ahora | Registro C-20 | ⏸ | C-20, C-21 |
| §4.2 | Sin bloqueo de cuenta | No lo hay; rate limiting en Traefik | Inspección de `iniciar_sesion.py`; e2e i | ✅ | C-26 |
| Fig. 10 | Readiness que aísla réplicas | `/health/live` cada 2 s, 2 fallos. Sin errores al borrar réplicas. **No se probó una réplica colgada** | `k8s/base/deployment-api.yaml`; e2e k | ⚠ | C-32 |
| §5.1 | 2 a 4 réplicas al 70 % | `hpa.yaml`; subió de 2 a 4 bajo carga y no pasó de 4 | e2e k | ✅ | C-53; F-09 |
| §5.1 | Datos en `iam_db` y SeaweedFS | Sí | e2e a y g | ✅ | C-46 |
| §6.1 | Bitácora de solo inserción | Triggers: `UPDATE`, `DELETE` y `TRUNCATE` fallan, e `INSERT ... ON CONFLICT DO NOTHING` sigue funcionando. Con el rol de esta base, que es superusuario, rechaza el trigger; el `REVOKE` no se ejerce aquí | `integration/test_bitacora_inmutable.py`; `b1-bitacora-solo-insercion.txt` | ✅ | C-03 |
| §6.1 | Sin duplicados | `UNIQUE(event_id)` | e2e d | ✅ | C-04 |
| §6.1 | Todos los accesos denegados | 401 y 403 con su fila | e2e b | ✅ | C-23 |

## 2. Prompts de los bloques 1 a 7 frente al código

Fuente: `prompts-iam-bloques.md`. Se listan solo las diferencias.

**Distinto y documentado en el registro** (sin acción):

| Bloque | El prompt pedía | Quedó | Entrada |
|---|---|---|---|
| 1 | TTL de `revocado-desde` igual al del token | TTL + 10 s de margen | C-21 |
| 2 | `detalles.usuario_id_reportado` | `detalles.usuario_id_no_registrado` | C-38 |
| 3 y 7 | Readiness en `/health` | `/health/live` | C-32 |
| 4 | Tabla outbox con `id` y `payload` | `event_id` como PK y `sobre` | C-09 |
| 4 | `ROLE_CHANGE` con `{rol_anterior, rol_nuevo}` | `{usuario_afectado, antes, despues, motivo}` | C-29 |
| 4 | `prestador.suspendido` con `motivo` | Sin `motivo` | C-41 |
| 5 | Bucket creado al arrancar | Lo provee `infra/`; script en desarrollo | C-46 |
| 5 | Llave `documentos/{usuario_id}/...` | `{usuario_id}/...` | C-30 |
| 5 | `GET /admin/prestadores/pendientes` | `GET /admin/prestadores?estado=pendiente` | C-47 |
| 5 | `PRESTADOR_VALIDADO` y `PRESTADOR_RECHAZADO` | `PROVIDER_APPROVED` y `PROVIDER_REJECTED` | C-19 |
| 5 | `rechazar {motivo, documento_id?}` | `{documentos: [{tipo, motivo}]}` | C-47 |
| 6 | `/perfil/password` | `/perfil/contrasena` | C-52 |
| 6 | `BackgroundTasks` | `asyncio.create_task` | C-50 |
| 6 | Cerrar las otras sesiones | Cierra todas, también la actual | C-21, C-52 |
| 6 | `GETDEL` antes del hash | Después del hash | C-28, C-53 |

**Distinto y sin entrada en el registro:**

| Bloque | El prompt pedía | Quedó | Hallazgo |
|---|---|---|---|
| 4 | Items de `/admin/usuarios` con `nombre` | `nombre_completo` | F-02 |
| 5 | Respuesta de la carga con `tipo` | `tipo_documento`, más campos | F-02 |
| 5 | Smoke test con la aprobación del Admin | El smoke llega hasta "pendiente" y no aprueba | F-03 |
| 2 | Comprobar que el `UPDATE` sigue bloqueado | Ya con prueba automatizada | F-04, cerrado |
| 1 | `VerificarAcceso` recibe IP, método y URI | Recibe solo el token; el router audita. Interno, sin efecto en el contrato | F-05 |

## 3. Registro

- **Entradas en 🔨:** ninguna.
- **★ frente a "Pendiente de reflejar":** C-04, C-07, C-08, C-20, C-21, C-27, C-32, C-36, C-57 y C-58 aparecen todas. C-57 ya figura también en la línea "SRS v1.2", porque contradice RNF-03 (F-06, cerrado).

## 4. Corrida limpia y seguridad

Entorno: proyecto de compose `iam-verificacion`, volúmenes nuevos, puertos propios y llaves JWT temporales. **La base de desarrollo no cambió:** `usuario` 26, `bitacora_auditoria` 688 y `outbox` 4, antes y después (`b1-base-desarrollo.txt`).

| Comprobación | Resultado | Evidencia |
|---|---|---|
| `alembic upgrade head` desde base vacía | 6 migraciones aplicadas | `b1-migraciones-seed.txt` |
| `seed_admin` | Crea y es idempotente | `b1-migraciones-seed.txt` |
| Suite completa, tras los arreglos | 541 pasan | `d-verificaciones.txt` |
| Integración (db, valkey, rabbitmq, s3), tras los arreglos | 67 pasan, 0 omitidas | `d-verificaciones.txt` |
| Smoke test, imagen real sin `pip` y en solo lectura | 48 de 48 | `b1-smoke.txt` |
| API, worker y `alembic current` en solo lectura, sin capacidades | Corren, sin errores de escritura | `f07-imagen-sin-pip.txt` |
| SeaweedFS en pausa, con la imagen real | 9 cargas con 503 en 9,4 s como máximo; 11 logins con 200, el más lento en 0,31 s | `f11-s3-colgado.txt` |
| `downgrade base` y `upgrade head`, con datos | Funcionan; `alembic check` sin diferencias con los modelos | `b1-downgrade-upgrade.txt` |
| Bitácora rechaza `UPDATE`, `DELETE`, `TRUNCATE` | Las tres fallan con "solo inserción"; con los triggers desactivados a propósito, la prueba nueva falla | `integration/test_bitacora_inmutable.py`; `b1-bitacora-solo-insercion.txt` |
| Cobertura de `app/domain` y `app/application` | **99 %** (meta: 70 %) | `d-verificaciones.txt` |

Las migraciones, el `seed_admin` y el `downgrade` no se tocaron en los arreglos y se ejecutaron de nuevo solo en su camino de subida. `bandit`, `pip-audit` y el e2e no se repitieron. La base de desarrollo tampoco cambió con los arreglos: 26, 688 y 4.

### Hallazgos de seguridad

| Herramienta | Hallazgo | Severidad | Clasificación |
|---|---|---|---|
| bandit | B105 `Tayrona2026` en `schemas/auth.py` (2) | Baja | Falso positivo: ejemplo de OpenAPI |
| bandit | B105 `iam:reset:` en `valkey_tokens_recuperacion.py` | Baja | Falso positivo: prefijo de llave |
| bandit | B101 `assert` (10), en repositorios, UoW, consumidor y casos de uso | Baja | Real sin impacto: comprueban invariantes internas, ninguno decide acceso, y la imagen no usa `-O` |
| pip-audit | Dependencias de producción de `uv.lock` | — | Sin vulnerabilidades |
| trivy | Debian 13: 44 altas, 58 medias, 61 bajas, 1 desconocida; 0 críticas; ninguna con parche | Alta (nominal) | Reales en la imagen base, sin parche. No se identificó una ruta de ataque directa: util-linux, ncurses, systemd, perl y acl son binarios locales, y el contenedor corre sin privilegios, sin capacidades y en solo lectura. Ver F-07 |
| trivy | `pip` 25.0.1 de la imagen base: 5 medias y 1 baja, con parche | Media | **Resuelto:** la imagen final ya no trae `pip` y trivy no reporta paquetes de Python (`f07-trivy-sin-pip.txt`). `b3-trivy.txt` conserva el análisis anterior |
| trivy | Secretos en la imagen | — | Ninguno |

### Secretos y datos reales

Sin hallazgos (`b4-secretos.txt`): ningún PEM, `.env` ni `secretos.env` versionado hoy ni en el historial, ningún bloque de llave privada, ninguna clave de nube. `services/iam-service/CLAUDE.md` no está versionado; se ignora con `.git/info/exclude`, que solo protege este clon. Los valores falsos de `e2e/` (`solo-para-pruebas-e2e`) son intencionales.

### Punta a punta en k3d

**11 de 11 escenarios OK** en `e2e-k3d.txt`, con k3s v1.35.5 y Traefik, **antes de los arreglos de F-04, F-06, F-07 y F-11**; no se repitió. El rate limiting, el gateway y las dependencias son de prueba, no la configuración real de `gateway/` e `infra/`. Datos principales:

| Escenario | Resultado |
|---|---|
| j. Rolling update bajo carga | 0 errores en 1272 peticiones, p95 de 16 ms, rollout de 10 s |
| k. Borrado ordenado de una réplica | 0 errores en 688 peticiones, 2 réplicas listas a los 5 s |
| k. Borrado forzado | 0 errores en 714 peticiones, 2 réplicas listas a los 6 s |
| k. HPA, con el mismo bucle de 4 hilos | Subió de 2 a 4 réplicas, con CPU por encima del 70 % |
| Logs de la API y del worker (11 621 líneas) | Sin correos ni tokens |

**Límites:**
- Son corridas en Docker Desktop con un solo nodo y carga baja. No miden capacidad y se repiten en la Fase 5.
- El escenario k borra pods. **No prueba una réplica colgada ni la caída de un nodo,** así que los menos de 5 s de ESC-01 siguen sin medirse.
- Traefik se probó con tráfico real, pero la IP de cliente no es pública (F-08).
- `e2e-k3d-sin-volumenes.txt` conserva una corrida fallida: mostró F-10 y F-11.
- Antes de la corrida válida hubo fallos del propio arnés, corregidos en `e2e/` y en el script: permisos de la cookie de RabbitMQ, puertos gRPC de SeaweedFS, cola de prueba no durable y la espera de réplicas. Una vez k3s falló al arrancar y bastó con recrear el clúster.
- El relay del outbox registró un `ERROR` al arrancar, mientras las dependencias se levantaban, y se recuperó solo.

## 5. Hallazgos

Cerrados: F-04, F-06 y F-11. En F-07 se resolvió `pip`, no la imagen base. Los demás siguen abiertos.

| ID | Hallazgo | Severidad | Bloquea el PR | Propuesta o resultado |
|---|---|---|---|---|
| F-01 | §2.4.5 pide almacenamiento cifrado de datos sensibles; no está implementado (C-58) | Alta (cumplimiento) | No: decisión del equipo, en ⏸ | Propuesta escrita en C-58: disco cifrado en la VM, cifrado de volúmenes de SeaweedFS y TLS. Cifrar en el servicio rompería las URL firmadas |
| F-08 | Traefik ve a todos los clientes como `10.42.0.1` (`externalTrafficPolicy: Cluster`): en esas condiciones, el rate limiting por IP se comparte entre **todos** los usuarios, y la bitácora guarda esa IP en vez de la real (ESC-04). k3d agrega su propio balanceador, así que hay que confirmarlo en el k3s real | Alta, si se confirma | No: es de `gateway/` | Juan Francisco: `externalTrafficPolicy: Local` con `HelmChartConfig`, y comprobar la IP real |
| F-10 | `infra/docker-compose.yml` usa `-volume.max=5`. La colección por defecto puede quedarse con todos y los documentos responden 503. Depende del orden: pasó en una corrida y falló en otra | Media | No: es de `infra/` | Luis Fernando: subir el límite antes de agregar `documentos-verificacion` |
| F-11 | Si SeaweedFS no puede escribir, la carga responde el 503 correcto **a los 32 s**, por los reintentos de boto3 | Media | **Cerrado** | C-59: tope de 9 s, hilos propios y los mismos límites en la supresión. 503 en 9,4 s y login sin bloquearse (`f11-s3-colgado.txt`). Quedan los límites listados en C-59 |
| F-04 | Sin prueba automatizada de la inmutabilidad de la bitácora, que es lo que verifica la SIC (Lab §6.1) | Media | **Cerrado** | `tests/integration/test_bitacora_inmutable.py`, marcada `db`; falla si se desactivan los triggers |
| F-09 | Con un `request` de CPU de 100m, unas 50 peticiones por segundo a `verificar` bastan para llevar el HPA a 4 réplicas | Baja | No | Medir en la Fase 5 y ajustar el `request` |
| F-06 | C-57 contradice RNF-03, y no está en la línea "SRS v1.2" de "Pendiente de reflejar" | Baja | **Cerrado** | Agregada |
| F-02 | `nombre_completo` y `tipo_documento` difieren del prompt | Baja | No | Ninguna en el código; son el contrato actual y están en `iam.yaml` |
| F-03 | El smoke test no cubre la aprobación del Admin | Baja | No | Cubierto en e2e a; agregarlo al smoke si se quiere |
| F-07 | Imagen base con 44 altas sin parche y `pip` vulnerable | Baja | No | `pip` y otras partes sin uso, fuera de la imagen. **Las vulnerabilidades de Debian siguen igual:** 44 altas, 58 medias, 61 bajas y 1 desconocida, sin parche; hay que revisar la base en cada versión |
| F-05 | Firma interna de `VerificarAcceso` distinta del prompt | Informativa | No | Ninguna |
