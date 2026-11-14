# Registro de Decisiones Arquitectónicas (ADR)

**Proyecto:** Plataforma Digital para la Gestión Integrada y Sostenible del Turismo en Santa Marta  
**Curso:** Arquitectura de Software — Experiencia Final de Diseño  
**Programa:** Ingeniería de Sistemas — Universidad del Magdalena  
**Versión:** 1.0  
**Fecha:** 13 de octubre de 2026  
**Documentos relacionados:** [SRS](./Requirements_docIEEE.md) · [Comparación de Alternativas](./Comparacion_Alternativas_Arquitectonicas.md) · [Plan de Implementación](./Plan_de_Implementacion.md)

---

Cada decisión sigue el formato: **Estado**, **Contexto**, **Decisión**, **Alternativas consideradas**, **Consecuencias** y **Trazabilidad**. Una decisión aceptada solo se modifica con un ADR nuevo que la reemplace.

| ID | Decisión | Exigida por el enunciado | Estado |
|---|---|---|---|
| [ADR-001](#adr-001-metodología-de-desarrollo) | Metodología de desarrollo: Scrum adaptado | Sí (selección de metodología) | Aceptada |
| [ADR-002](#adr-002-estilo-arquitectónico) | Estilo arquitectónico: microservicios orientados a eventos | Sí (selección de estilo) | Aceptada |
| [ADR-003](#adr-003-tipo-de-base-de-datos-y-estrategia-de-persistencia) | Persistencia políglota consolidada en PostgreSQL y Valkey | Sí (tipo de base de datos) | Aceptada |
| [ADR-004](#adr-004-estrategia-de-manejo-de-conectividad) | Conectividad limitada: PWA con caché del catálogo y formularios diferidos | Sí (estrategia de conectividad) | Aceptada |
| [ADR-005](#adr-005-plataforma-de-despliegue) | Plataforma de despliegue: contenedores en Kubernetes (k3s) | No | Aceptada |
| [ADR-006](#adr-006-lenguaje-y-framework-de-los-microservicios) | Lenguaje y framework: Python + FastAPI en los 5 servicios | No | Aceptada |
| [ADR-007](#adr-007-api-gateway) | API Gateway: Traefik con ForwardAuth | No | Aceptada |
| [ADR-008](#adr-008-mensajería-asíncrona-y-auditoría) | Mensajería: RabbitMQ y auditoría asíncrona centralizada en el Módulo 1 | No | Aceptada (actualizada: outbox) |
| [ADR-009](#adr-009-observabilidad) | Observabilidad: Prometheus, Grafana y Loki | No | Aceptada |
| [ADR-010](#adr-010-componente-de-inteligencia-artificial) | IA: chatbot sobre la API de Gemini con herramientas de solo lectura | No | Aceptada |
| [ADR-011](#adr-011-proveedor-del-modelo-de-lenguaje-groq-en-lugar-de-gemini) | Proveedor del modelo de lenguaje: Groq en lugar de Gemini | No | Propuesta |
| [ADR-012](#adr-012-cifrado-en-reposo-y-en-tránsito) | Cifrado en reposo y en tránsito: en la infraestructura, con lo interno declarado como limitación | No | Aceptada |
| [ADR-013](#adr-013-decisiones-del-módulo-1-iam) | Decisiones del Módulo 1 (IAM): verificación propia, revocación y refresh en Valkey, bitácora idempotente, outbox y supresión por anonimización | No | Aceptada |

---

## ADR-001: Metodología de desarrollo

* **Estado:** Aceptada.
* **Contexto:** Equipo de 5 estudiantes con disponibilidad heterogénea (R-05), 13 semanas de ejecución con sustentación entre el 15 y el 17 de noviembre y una arquitectura de microservicios que requiere detectar temprano los problemas de integración (R-01).
* **Decisión:** Scrum adaptado con 6 sprints de 2 semanas seguidos de la sustentación, tablero Kanban en GitHub Projects, revisión de sprint alineada con cada fase del cronograma y propiedad de cada componente por un integrante (SRS, Apéndice C).
* **Alternativas consideradas:**
  * *Cascada:* descartada; difiere la integración al final, cuando los defectos de contratos entre servicios son más costosos.
  * *RUP:* descartada; su carga documental excede el tamaño del equipo y del proyecto.
  * *Kanban puro:* descartada; sin iteraciones fijas no hay puntos de revisión que coincidan con las entregas académicas.
* **Consecuencias:** Entregables incrementales por sprint y revisiones frecuentes. Exige disciplina para mantener el tablero y las ceremonias.
* **Trazabilidad:** SRS Apéndice D.1, R-01, R-05.

---

## ADR-002: Estilo arquitectónico

* **Estado:** Aceptada.
* **Contexto:** Picos estacionales de demanda (ESC-02, ESC-08), disponibilidad mínima del 99% (RNF-01), componente de IA que debe evolucionar sin afectar el núcleo (ESC-05) y datos personales que conviene aislar (Ley 1581).
* **Decisión:** Microservicios por *Bounded Context* (5 servicios) con comunicación híbrida: REST síncrono para operaciones del usuario y eventos asíncronos (Pub/Sub) para tareas secundarias.
* **Alternativas consideradas:** *Monolito modular con arquitectura hexagonal* (100 frente a 104 puntos en la tabla ponderada). Descartado por escalar y fallar como un bloque. El análisis completo, con la sensibilidad del resultado, está en la [Comparación de Alternativas](./Comparacion_Alternativas_Arquitectonicas.md).
* **Consecuencias:** Escalado y despliegue independientes y aislamiento de fallos, a cambio de mayor complejidad operativa (broker, varias bases, observabilidad distribuida) y consistencia eventual entre servicios.
* **Trazabilidad:** RNF-01, RNF-02, RNF-05, ESC-01, ESC-02, ESC-05, ESC-08.

---

## ADR-003: Tipo de base de datos y estrategia de persistencia

* **Estado:** Aceptada.
* **Contexto:** El enunciado exige evaluar persistencia única o políglota según las características de los datos, los atributos de calidad, el costo, la complejidad y la evolución. Los datos del sistema son de naturalezas distintas: transaccionales (reservas y cupos, que requieren ACID), geoespaciales (catálogo), semiestructurados (reseñas con calificaciones variables), efímeros de alta velocidad (caché y sesiones) y archivos (documentos RNT/RUT).
* **Decisión:** Persistencia **políglota consolidada**: varios modelos de datos sobre pocos motores, todos FOSS.
  * PostgreSQL 16 con una base lógica por servicio (*Database-per-Service*): relacional para IAM, reservas y recomendaciones; PostGIS para el catálogo; JSONB para las reseñas.
  * Valkey para caché, sesiones del chatbot e idempotencia.
  * SeaweedFS (API S3) para documentos y respaldos.
* **Alternativas consideradas:**
  * *Persistencia única (solo PostgreSQL, sin caché):* descartada; no cumple ESC-02 (500 rps con $p95 < 2$ s) sin caché en memoria y obliga a guardar sesiones en la base transaccional.
  * *Políglota con un motor por tipo de dato (PostgreSQL, MongoDB, Redis):* descartada. MongoDB Community usa la licencia SSPL, que la OSI no reconoce como código abierto (contradice la prioridad FOSS), y cada motor adicional aumenta el costo de operación, respaldo y monitoreo para un equipo de 5 personas (R-01). Redis cambió a licencias no OSI en 2024; Valkey es su bifurcación BSD.
* **Consecuencias:** Un solo motor relacional que operar, respaldar y monitorear, con el modelo adecuado para cada dato. Las cinco bases comparten instancia en el prototipo, por lo que una falla del clúster PostgreSQL afecta a todos los servicios; se mitiga con réplicas de CloudNativePG en el Escenario B. Si las reseñas crecieran más allá de lo que JSONB maneja bien, FerretDB permite exponer una API compatible con MongoDB sin cambiar de motor.
* **Trazabilidad:** SRS §3.6.3, §3.7; Plan §5; RNF-06, RNF-09, ESC-02, ESC-06.

---

## ADR-004: Estrategia de manejo de conectividad

* **Estado:** Aceptada.
* **Contexto:** Muchos prestadores comunitarios operan en zonas con conexión intermitente (Minca, Sierra Nevada) y tienen recursos tecnológicos limitados (restricción social del enunciado, SRS §2.4.3). Los turistas también consultan desde lugares con mala señal. El enunciado exige una estrategia explícita de manejo de conectividad.
* **Decisión:** Entregar la interfaz como **PWA** (Vue.js 3 + Workbox) con dos mecanismos:
  1. **Catálogo sin conexión:** El Service Worker guarda la aplicación (*cache first*) y las respuestas del catálogo (*stale-while-revalidate*, hasta 7 días), mostrando la fecha de la última actualización. Del mapa solo se conservan las teselas ya visualizadas, conforme a la política de uso de OpenStreetMap.
  2. **Formularios diferidos:** Los formularios de perfil (UC4), reseña (UC15), oferta (UC17, UC18) y cupos y tarifas (UC19) se guardan en IndexedDB con el estado "Pendiente de envío" y se envían automáticamente al recuperar la conexión (Background Sync donde exista; si no, al detectar la reconexión o abrir la aplicación). Cada envío lleva `Idempotency-Key` para evitar duplicados y las ediciones llevan la versión del registro para detectar conflictos (HTTP 409).
  * Las operaciones que dependen del estado en tiempo real (solicitar y confirmar reservas, UC11 y UC20) requieren conexión y se deshabilitan sin ella, con un mensaje explicativo.
* **Alternativas consideradas:**
  * *Aplicación nativa con base de datos local y sincronización:* descartada; exige instalar una aplicación, duplica el desarrollo (Android/iOS) y contradice la restricción de no requerir aplicativos nativos.
  * *Solo diseño liviano sin soporte sin conexión:* descartada; reduce el consumo de datos pero no evita perder el trabajo del prestador cuando se cae la conexión.
  * *Encolar también las solicitudes de reserva:* descartada; podría aceptar solicitudes sobre cupos que ya no existen y contradice RF-03 (disponibilidad en tiempo real).
* **Consecuencias:** Inclusión de prestadores con conectividad limitada sin aplicaciones nativas. A cambio, los servicios deben soportar idempotencia y control de versión, la interfaz debe manejar conflictos, y los datos guardados en el dispositivo deben borrarse al cerrar sesión (privacidad). Riesgo R-06.
* **Trazabilidad:** RNF-13, ESC-09, RF-08, SRS §3.3.1 y §3.6.6, Plan §6.8.

---

## ADR-005: Plataforma de despliegue

* **Estado:** Aceptada. Reemplaza la propuesta de ejecutar los Módulos 1 a 4 en AWS Lambda y el Módulo 5 en Kubernetes (SRS 1.0.1).
* **Contexto:** El enunciado no exige *serverless* ni un proveedor de nube; privilegia el software libre y los servicios cloud de bajo costo, exige el despliegue del prototipo y la validación de escalabilidad y disponibilidad sobre él. El Módulo 5 debe permanecer siempre activo para evitar arranques en frío en conversaciones de varios segundos.
* **Decisión:** Desplegar **todos** los componentes como contenedores en **Kubernetes (k3s)**: un nodo en el prototipo (Escenario A) y tres en el piloto (Escenario B). Docker Compose queda solo para desarrollo local.
* **Alternativas consideradas:**
  * *Híbrido AWS Lambda (Módulos 1 a 4) + Kubernetes (Módulo 5):* descartada; obliga a operar dos plataformas, requiere servicios propietarios adicionales (API Gateway de AWS, Amazon MQ, RDS Proxy, CloudWatch) para que Lambda consuma eventos y se conecte a la base de datos, y contradice la prioridad FOSS.
  * *Docker Compose en un solo host:* descartada como entorno de despliegue; no ofrece escalado automático ni *rolling updates*, necesarios para demostrar ESC-05 y ESC-08.
  * *Kubernetes con Knative (escalado a cero):* descartada por ahora; agrega complejidad y arranques en frío que afectan ESC-02 sin un beneficio necesario para el prototipo.
* **Consecuencias:** Una sola plataforma, FOSS y portable; el Módulo 5 deja de ser un caso especial (Deployment con al menos una réplica). Escalado automático (HPA), autorreparación y actualizaciones sin interrupción. A cambio, el equipo opera el clúster y la elasticidad está limitada por la capacidad de los nodos (R-07).
* **Trazabilidad:** RNF-01, RNF-02, RNF-12, ESC-01, ESC-05, ESC-08, Plan §7.

---

## ADR-006: Lenguaje y framework de los microservicios

* **Estado:** Aceptada. Resuelve la decisión pendiente del monorepo (Spring Boot o NestJS).
* **Contexto:** El enunciado exige paradigma orientado a objetos. El chatbot se construye en Python. Un equipo de 5 personas con 13 semanas se beneficia de compartir un solo stack (R-01).
* **Decisión:** **Python 3.12 + FastAPI** en los 5 microservicios, con clases de dominio y arquitectura hexagonal. Cada servicio es una aplicación HTTP estándar (ASGI) empaquetada como contenedor, sin depender de la plataforma de ejecución, de modo que el mismo código podría migrar a otra plataforma de contenedores o *serverless* sin reescribirse.
* **Alternativas consideradas:**
  * *Java con Spring Boot:* descartada; mayor consumo de memoria por réplica (relevante en un clúster pequeño) y un segundo lenguaje junto al Python del chatbot.
  * *Node.js con NestJS:* descartada; también obliga a mantener dos lenguajes.
* **Consecuencias:** Una plantilla base, unas mismas prácticas de pruebas (`pytest`) y facilidad de rotación entre servicios. Python requiere cuidado con el rendimiento (servidor ASGI asíncrono, caché) para cumplir ESC-02.
* **Trazabilidad:** RNF-05, R-01, Plan §1.3 y §2.2.

---

## ADR-007: API Gateway

* **Estado:** Aceptada. Resuelve la decisión pendiente entre Nginx y Traefik.
* **Contexto:** Se necesita un punto de entrada único con TLS, validación de identidad, *rate limiting* y CORS, integrado con Kubernetes.
* **Decisión:** **Traefik**, controlador de Ingress incluido en k3s. Las rutas protegidas usan el middleware ForwardAuth contra `GET /api/iam/auth/verificar` del Módulo 1, que devuelve la identidad en encabezados; las rutas públicas del catálogo no requieren token.
* **Alternativas consideradas:**
  * *Nginx Ingress:* descartada; equivalente en funciones, pero implica reemplazar el Ingress de k3s y configurar la autenticación con anotaciones menos expresivas.
  * *Validación del JWT en cada servicio sin ForwardAuth:* descartada como mecanismo principal; reparte la lógica de seguridad y dificulta registrar en un solo lugar los accesos con token inválido (ESC-04).
* **Consecuencias:** Configuración declarativa con recursos de Kubernetes y auditoría centralizada de tokens inválidos. Cada petición protegida hace una llamada adicional al Módulo 1, que por eso escala con HPA; el catálogo público, que concentra el tráfico de temporada alta, no paga ese costo.
* **Trazabilidad:** RNF-04, ESC-04, SRS §3.3.3, Plan §4.1 y §6.1.

---

## ADR-008: Mensajería asíncrona y auditoría

* **Estado:** Aceptada. Elimina la alternativa "RabbitMQ o Redis Streams". Actualizada en la implementación del Módulo 2: patrón outbox e idempotencia en la base del consumidor.
* **Contexto:** Correos, métricas, habilitación de reseñas y bitácora de auditoría no deben bloquear al usuario. La bitácora debe registrar el 100% de los accesos indebidos (ESC-04) y ser inmutable (RNF-10).
* **Decisión:** **RabbitMQ** con el exchange `turismo.eventos` (topic), una cola por consumidor, *publisher confirms*, idempotencia por `event_id` y DLQ tras 3 intentos. La auditoría tiene un único dueño, el Módulo 1: escribe sus eventos en la misma transacción de la acción y consume `auditoria.registrada` de los demás módulos; la tabla solo admite inserciones.
* **Actualización (implementación del Módulo 2, octubre de 2026):** al programar catalog-service nos dimos cuenta de que era más sencillo y más seguro guardar los eventos y los `event_id` procesados en tablas de la propia base del servicio:
  * **Patrón outbox adoptado:** el evento se guarda en la tabla `outbox` en la misma transacción que el cambio, y un proceso aparte (*worker*, otro Deployment con la misma imagen) lo publica con *publisher confirms* y lo marca como publicado. Si RabbitMQ está caído, el evento espera en la tabla; si la transacción se deshace, el evento no existe. Varios workers no publican el mismo evento (`SELECT … FOR UPDATE SKIP LOCKED`).
  * **Idempotencia en la base, no en Valkey:** el consumidor registra el `event_id` en la tabla `evento_procesado` en la misma transacción que aplica el efecto. Con Valkey, una caída entre el efecto y el registro (o el vencimiento del TTL de 24 h) podía aplicar un evento dos veces; en la tabla, efecto y registro se confirman juntos.
  * Se recomienda el mismo esquema a booking-service y review-service.
* **Alternativas consideradas:**
  * *Redis/Valkey Streams:* descartada; evita un componente, pero carece del enrutamiento por *topic*, las DLQ y la consola de administración que facilitan la operación y la depuración.
  * *Escritura directa de cada módulo en la bitácora del Módulo 1:* descartada; viola *Database-per-Service*.
  * *Publicar directamente después de confirmar la transacción (sin outbox):* era la opción inicial; se reemplazó en la implementación del Módulo 2 porque un fallo entre el commit y la publicación perdía el evento (ESC-04 exige registrar el 100% de los accesos indebidos).
* **Consecuencias:** Desacople y resiliencia ante fallos transitorios, con consistencia eventual. Los consumidores deben ser idempotentes y los contratos de eventos se versionan en `contracts/events/`.
* **Trazabilidad:** RF-09, RF-11, RF-14, RNF-10, ESC-04, SRS §3.6.2, Plan §4.2 a §4.4.

---

## ADR-009: Observabilidad

* **Estado:** Aceptada.
* **Contexto:** Se debe verificar la disponibilidad del 99% (RNF-01), la latencia p95 (RNF-06) y el comportamiento del escalado (ESC-08), y seguir una petición a través de varios servicios.
* **Decisión:** **Prometheus** (métricas de `/metrics` y sondas del Blackbox exporter sobre `/health`), **Grafana** (tableros) y **Loki** (registros en JSON con `X-Correlation-ID`), desplegados en el namespace `observabilidad`.
* **Alternativas consideradas:** *Servicios gestionados de un proveedor (por ejemplo, CloudWatch):* descartados por la decisión de plataforma (ADR-005) y la prioridad FOSS. *Trazas distribuidas con OpenTelemetry y Tempo:* pospuestas; el identificador de correlación cubre la necesidad del prototipo.
* **Consecuencias:** Evidencia medible para la validación de los escenarios de calidad. Consume recursos del clúster, que se consideran en el dimensionamiento de los nodos.
* **Trazabilidad:** RNF-01, RNF-06, UC31, ESC-01, ESC-02, ESC-08, Plan §7.5.

---

## ADR-010: Componente de inteligencia artificial

* **Estado:** Aceptada.
* **Contexto:** El enunciado permite elegir entre recomendación personalizada, clasificación de opiniones, predicción de demanda o chatbot basado en información registrada y controlada; la IA es complementaria y debe integrarse de forma desacoplada. Las recomendaciones deben explicarse y no favorecer a un operador.
* **Decisión:** Chatbot de recomendaciones (Módulo 5) que consume la **API de Gemini** con llamada a funciones y consulta la plataforma solo mediante **herramientas de solo lectura** sobre los Módulos 2, 3 y 4. Registra cada recomendación con su justificación en `recommendation_db` y guarda la sesión en Valkey.
* **Alternativas consideradas:** *Filtrado híbrido propio entrenado con un dataset sintético:* descartado; exige construir y validar un modelo y un dataset, fuera del foco del curso (R-03). *Modelo abierto alojado por el equipo:* descartado por el costo de GPU y de operación.
* **Consecuencias:** Única dependencia propietaria del sistema (excepción justificada a la prioridad FOSS), con costos por consumo y límites de solicitudes (R-04). La indisponibilidad de Gemini solo afecta al chatbot.
* **Trazabilidad:** RF-06, RNF-08, UC14, ESC-05, R-03, R-04, [Guía Técnica del Módulo 5](./Guia_Tecnica_Modulo_IA.md).

---

## ADR-011: Proveedor del modelo de lenguaje: Groq en lugar de Gemini

* **Estado:** Propuesta (Alvaro Ospino, responsable del Módulo 5). Si se acepta, reemplaza al ADR-010 **solo en el proveedor**; el resto del ADR-010 (chatbot, herramientas de solo lectura, registro en `recommendation_db`, sesión en Valkey) se mantiene.
* **Contexto:** Al empezar la integración del Módulo 5 con la API de Gemini, el equipo tuvo dos problemas:
  1. **La API no respondía** a las solicitudes de prueba, así que no se pudo validar el flujo del chatbot.
  2. **Exigía registrar un método de pago** al crear la aplicación, algo que un proyecto académico sin presupuesto para servicios de IA no puede asumir.

  El Módulo 5 ya está construido sobre una interfaz propia (`ModeloDeLenguaje`), de modo que el proveedor es un adaptador intercambiable y cambiarlo no toca el dominio, los casos de uso ni el contrato REST.
* **Decisión:** El Módulo 5 usa la **API de Groq** (SDK `groq`) como proveedor del modelo de lenguaje, con llamada a funciones (tools) y un modelo abierto que la admita. El proveedor y el modelo se eligen por configuración con variables genéricas: `LLM_PROVIDER=groq`, `LLM_API_KEY` (como `Secret`) y `LLM_MODEL` (como `ConfigMap`). Reemplazan a `GEMINI_API_KEY` y `GEMINI_MODEL`.
* **Alternativas consideradas:**
  * *Seguir con Gemini:* descartada por los dos problemas del contexto.
  * *API de OpenAI:* descartada; también exige un método de pago y cobra por consumo desde el primer uso.
  * *Modelo abierto alojado por el equipo (por ejemplo, con Ollama):* sigue descartada por la misma razón que en el ADR-010, el costo de GPU y de operación en el clúster.
  * *Groq (elegida):* tiene un plan gratuito para desarrollo (se confirma al crear la clave que no pide método de pago), una API compatible con la de OpenAI con llamada a funciones, respuestas de baja latencia y modelos abiertos.
* **Consecuencias:**
  * Groq sigue siendo un **servicio externo propietario**: se mantiene la excepción justificada a la prioridad FOSS del ADR-010, ahora con Groq como única dependencia propietaria.
  * El plan gratuito tiene **límites de solicitudes** (R-04). Bastan para el desarrollo y las pruebas de calidad (unas 30 conversaciones tipo), pero en producción se revisarían. El servicio responde 503 `ASISTENTE_NO_DISPONIBLE` al superar el límite y el resto de la plataforma sigue operando (ESC-01).
  * **Privacidad (Ley 1581):** la conversación y los resultados de las tools viajan a Groq. Se le envía el mínimo necesario (nunca nombre, correo ni documento), y antes de usarlo con turistas reales hay que revisar sus condiciones de uso y retención de datos.
  * **Impacto en otros módulos:** ninguno. El contrato `recommendation.yaml` no cambia y ningún otro servicio depende del proveedor.
  * **Documentos a actualizar al aceptarse:** el ADR-010 (estado "Reemplazada parcialmente por ADR-011"), el SRS, el Plan de Implementación (§4 y flujo 6), la Comparación de Alternativas, el README raíz y los diagramas que mencionan Gemini. La Guía Técnica del Módulo 5 y `docs/modulo-ia/` se actualizan en la rama del módulo.
* **Trazabilidad:** RF-06, RNF-08, UC14, ESC-01, ESC-05, R-04, ADR-010, [Guía Técnica del Módulo 5](./Guia_Tecnica_Modulo_IA.md).

---

## ADR-012: Cifrado en reposo y en tránsito

* **Estado:** Aceptada el 4 de noviembre de 2026 por Luis Fernando Barraza, responsable de la arquitectura y de `infra/`. Responde a C-58 de `services/iam-service/docs/cambios-frente-al-srs.md`.
* **Contexto:** El SRS (§2.4.5, Ley 1581) pide "almacenamiento cifrado de datos sensibles", pero no dice en qué capa. Hoy:
  * Las contraseñas usan Argon2id y los tokens de recuperación se guardan en Valkey como SHA-256.
  * Los documentos de los prestadores (RUT y RNT) se guardan sin cifrar en SeaweedFS. Los correos y nombres de `iam_db`, las reservas y las reseñas se guardan sin cifrar en PostgreSQL. Los respaldos de PostgreSQL (`respaldos-postgres`) tampoco van cifrados.
  * Dentro del clúster, los servicios hablan sin TLS con PostgreSQL, RabbitMQ, Valkey y SeaweedFS. Las NetworkPolicy limitan quién llega a cada uno.
  * El documento no puede cifrarse en el servicio: el navegador del Admin lo descarga directamente de SeaweedFS con una URL firmada, así que esa URL entregaría el contenido cifrado.
* **Decisión:** se divide en dos:
  * **Se implementa (A-mínima):**
    1. **TLS en el borde:** Traefik termina HTTPS con certificados de cert-manager (ya está en el Plan §7). Todo lo que sale del clúster, incluidas las URL firmadas de SeaweedFS, va por HTTPS.
    2. **Cifrado de los volúmenes de SeaweedFS** con `-filer.encryptVolumeData` (disponible en la 3.80 en modo `server`). Cubre documentos, imágenes y respaldos de PostgreSQL. Se activa antes de cargar datos reales, porque no cifra lo que ya está escrito.
    3. **Disco cifrado en la VM del clúster**, si el proveedor lo ofrece (cifrado en reposo del disco o LUKS). Cubre PostgreSQL, RabbitMQ y Valkey sin tocar los servicios.
  * **Se declara como limitación del prototipo en el SRS v1.2 (B):** TLS entre los servicios y PostgreSQL, RabbitMQ y Valkey dentro del clúster, y cifrado por columna de los datos personales en PostgreSQL. Ambos quedan como trabajo futuro con sus condiciones.
* **Alternativas consideradas:**
  * *A completa, todo en la infraestructura:* TLS interno con certificados propios para PostgreSQL (CloudNativePG lo trae), RabbitMQ y Valkey, más todo lo de A-mínima. Descartada por ahora:
    * Exige rotar certificados y cambiar las URL de conexión de los 5 servicios.
    * Las 5 bases de pruebas (testcontainers, compose) tendrían que replicarlo.
    * En un solo nodo, el tráfico interno no sale de la máquina y las NetworkPolicy ya lo restringen.
    * El costo es alto para un equipo de cinco personas con una sola VM de 8 GB.
  * *B pura, solo declararlo como limitación:* descartada:
    * Deja sin cubrir lo más visible para la SIC: documentos de identidad tributaria en un disco y respaldos sin cifrar.
    * Lo más barato (dos flags y una opción del proveedor) resuelve la mayor parte del riesgo.
  * *Cifrar en cada servicio:* descartada por la URL firmada del contexto y porque repartiría llaves entre cinco servicios.
* **Consecuencias:**
  * **Protege** frente a un disco, un volumen o un respaldo robados, y frente a quien escucha el tráfico entre el usuario y la plataforma.
  * **No protege** frente a quien entra al sistema encendido con credenciales válidas. Eso lo cubren las credenciales por servicio, las NetworkPolicy, el bucket privado (C-46) y la bitácora.
  * La llave de `encryptVolumeData` la guarda el filer de SeaweedFS en su propio almacenamiento. Si se pierde ese volumen, los datos no se recuperan. El respaldo del filer pasa a ser obligatorio.
  * **Pendiente para cumplirla:**
    * Probar `-filer.encryptVolumeData` con el despliegue de `infra/` en la VM: subir, leer con URL firmada, respaldar y restaurar.
    * ~~Confirmar el cifrado de disco del proveedor elegido.~~ Hecho: la VM de AWS (`tourism-vm`) usa un volumen EBS gp3 cifrado, que cubre PostgreSQL, RabbitMQ, Valkey y SeaweedFS (punto 3).
    * TLS en el borde (punto 1) funcionando en la VM pública: Let's Encrypt y HTTP → HTTPS (`services/iam-service/docs/evidencias/vm-aws.txt`, 7.1-7.2).
    * Escribir en el SRS v1.2 (§2.4.5) qué se cifra, dónde y qué queda como limitación.
    * Marcar C-58 como resuelta en la documentación del IAM.
* **Trazabilidad:** SRS §2.4.5, RNF-09, Ley 1581, C-46, C-58, ADR-003, ADR-005, ADR-007, Plan §7.

---

## ADR-013: Decisiones del Módulo 1 (IAM)

* **Estado:** Aceptada el 13 de noviembre de 2026 por Luis Fernando Barraza, responsable de la arquitectura. Propuesta el mismo día por Valentina Nieves (Módulo 1). No reemplaza ningún ADR: precisa cómo el Módulo 1 cumple el ADR-007 y el ADR-008.
* **Contexto:**
  * El IAM es el punto por el que pasa cada petición protegida: Traefik lo consulta con ForwardAuth (ADR-007). Su latencia y su disponibilidad son las de toda la plataforma.
  * Guarda datos personales bajo la Ley 1581: correos, nombres, documentos tributarios y la bitácora de auditoría (RNF-10, ESC-04).
  * Al implementarlo, el IAM se apartó en varios puntos de lo que fijaban el SRS v1.1, el Plan de Implementación y el Laboratorio 3. Este ADR reúne esas decisiones; el detalle de cada una, con su causa, su efecto y su estado, está en `services/iam-service/docs/cambios-frente-al-srs.md` (C-xx).
* **Decisión:**
  1. **Verificación propia para el ForwardAuth** (`GET /api/iam/auth/verificar`), en lugar de que Traefik valide el JWT con el JWKS (C-16):
     * Comprueba firma RS256, emisor, expiración, tipo y revocación. En el camino feliz solo lee Valkey, nunca PostgreSQL.
     * 401 `TOKEN_INVALIDO` sin token válido y 403 `ROL_INSUFICIENTE` con rol insuficiente (C-36).
     * Cada 401 y 403 deja una fila `ACCESS_DENIED` con un motivo interno que no sale en la respuesta, sin el query string y con la plantilla de la ruta (C-23, C-34).
  2. **Revocación por usuario con `revocado-desde`**, además del `jti` (C-21): un cambio de rol, de estado o de contraseña guarda la hora del cambio, y se rechaza todo token con `iat <=` esa marca. Las llaves del `jti`, del usuario y de la sesión se leen en un solo `MGET`.
  3. **Refresh token opaco con rotación** (C-20, C-60):
     * Valor aleatorio, no JWT; Valkey guarda solo su SHA-256.
     * Cada uso entrega uno nuevo. Un refresh ya rotado revoca la familia y deja `REFRESH_REUTILIZADO`.
     * El access token lleva el `sid` de la familia, y `verificar` rechaza una sesión revocada en la misma lectura del punto 2.
     * La rotación es atómica (un script Lua): de dos usos simultáneos, gana uno.
  4. **Bitácora centralizada de solo `INSERT`, idempotente en la base** (C-04, RNF-10): `UNIQUE(event_id)` con `ON CONFLICT DO NOTHING`, sin Valkey. Triggers y `REVOKE` impiden `UPDATE`, `DELETE` y `TRUNCATE` (C-03).
  5. **Eventos por outbox con relay en el worker** (C-09), como fija el ADR-008: `prestador.aprobado`, `prestador.suspendido` y `usuario.suprimido` se guardan en la misma transacción que el cambio. `OUTBOX_EVENTOS_RETENIDOS` permite retener un tipo hasta que exista su cola (C-63).
  6. **Supresión por anonimización, no por borrado** (C-27): datos neutros en la fila, documentos borrados de SeaweedFS y la bitácora intacta. `usuario.suprimido` avisa a catalog para que borre los datos del perfil del prestador (C-63).
  7. **Otras diferencias con el SRS y el Plan:**
     * `razon_social` se guarda en `iam_db`, porque viene con el RUT, y viaja en `prestador.aprobado` (C-07). `prestador_id` = `usuario_id` (C-08).
     * Readiness y liveness en `/health/live`, sin dependencias. `/health`, con PostgreSQL y Valkey, queda para el monitoreo (C-32).
     * `iam.yaml` se genera desde la app, en OpenAPI 3.1 (C-57).
     * El cifrado de los datos sensibles va en la infraestructura, según el ADR-012 (C-58).
* **Alternativas consideradas:**
  1. *Validar el JWT con el JWKS en el gateway:* descartada; no revoca antes del `exp` ni registra los 401 en la bitácora (ESC-04). *Solo 403, como la Tabla V del SRS:* descartada; la Tabla XXII y ESC-04 piden 401 o 403, y la PWA necesita distinguir "inicie sesión" de "sin permiso" (C-36).
  2. *Guardar el `jti` en Valkey al cambiar el rol (Laboratorio §4.2):* descartada; el IAM no conoce los `jti` ya emitidos, y el cambio lo hace el Admin, no la sesión afectada.
  3. *Refresh como JWT con `jti` (Plan §2.3):* descartada; pasaría la firma sin Valkey y `verificar` tendría que excluirlo a mano. *Sin refresh:* descartada; obliga a iniciar sesión cada 15 minutos, también con formularios pendientes (RNF-13).
  4. *Idempotencia en Valkey con TTL de 24 h (SRS Tabla XV, Laboratorio ACME):* descartada; un evento reentregado después del TTL se duplica, y la marca y la fila se confirman en sistemas distintos.
  5. *Publicar después del commit, sin outbox:* descartada en el ADR-008; un fallo entre los dos pierde el evento. *Publicar `usuario.suprimido` sin cola enlazada:* descartada; el broker lo confirma y lo descarta.
  6. *Borrar al usuario:* descartada; la bitácora lo referencia con una llave foránea y debe conservarse (ESC-04). *Solo `prestador.suspendido`:* insuficiente; oculta el perfil pero no borra nada, porque es reversible.
  7. *`razon_social` solo en catalog (SRS Tabla XVIII):* descartada; catalog la necesita al crear el perfil y quien la conoce es el IAM. *Readiness en `/health` (Plan §7.3):* descartada; una caída de PostgreSQL sacaría a todas las réplicas a la vez. *Contrato escrito a mano en 3.0:* descartada; se desactualiza, y convertirlo a 3.0 es frágil. *Cifrar en el servicio:* descartada en el ADR-012 por la URL firmada.
* **Consecuencias:**
  * **Se gana:**
    * El logout, la desactivación y la detección de robo tienen efecto inmediato en toda la plataforma.
    * Cada rechazo deja su fila en la bitácora, en una transacción propia (ESC-04). Si PostgreSQL no responde, el 401 o el 403 se mantiene y el fallo queda en el log (C-23).
    * Ningún evento se pierde entre el commit y RabbitMQ. Un reenvío del relay puede duplicarlo; los consumidores lo descartan por `event_id` (C-04, ADR-008).
    * La supresión cumple la Ley 1581 sin romper la trazabilidad.
  * **Valkey pasa a ser dependencia crítica:** si cae, `verificar` responde 503 y nadie entra a las rutas protegidas; tampoco hay login ni refresh (falla cerrado, C-22). Por eso usa `noeviction` (C-60).
  * **La bitácora crece sin poder borrarse,** y el texto libre que escribe un Admin en ella no se puede suprimir (C-27).
  * **Respuesta perdida en un refresh:** si la rotación ocurre y la respuesta no llega, el reintento con el refresh viejo se trata como robo y cierra la sesión (C-60). Trabajo futuro: un periodo de gracia de 10 a 30 s para el refresh anterior inmediato, que debilita un poco la detección dentro de esa ventana.
  * **Revocación inmediata:** un cambio de rol, de estado o de contraseña, y la supresión, cierran todas las sesiones del usuario, también sus refresh, y debe volver a iniciar sesión. La marca va en segundos, así que también cae un token emitido en el mismo segundo del cambio (C-21).
  * **Liberar un evento retenido antes de que exista su cola lo pierde** (C-63).
* **Trazabilidad:** RF-09, RF-12, RNF-04, RNF-10, RNF-12, RNF-13, ESC-04, UC1 a UC4, UC6, UC27, UC28, UC33, UC37, Ley 1581, ADR-007, ADR-008, ADR-012, Laboratorio 3 §4.2.
* **Cambios propuestos a los documentos** (detalle en "Pendiente de reflejar" de `cambios-frente-al-srs.md`):
  * **SRS v1.2:** C-01, C-02, C-04, C-05, C-06, C-07, C-08, C-17 (con C-29 y C-47), C-20, C-23 (ESC-04), C-27, C-36, C-38, C-39, C-57 y C-58.
  * **Plan:** §2.3 (C-19, C-21, C-60), §4.1 (C-11, C-12, C-13), §4.3 (C-38, C-40), §7 y §7.4 (C-54), §7.2 (C-61) y §7.3 (C-32).
  * **Laboratorio 3:** Figuras 1 y 2 y especificación ACME (C-04), Figura 6 (C-31), Figura 10 (C-32) y §4.2 (C-20, C-21, C-60).
