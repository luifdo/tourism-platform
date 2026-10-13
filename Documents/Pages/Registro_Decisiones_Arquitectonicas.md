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
| [ADR-008](#adr-008-mensajería-asíncrona-y-auditoría) | Mensajería: RabbitMQ y auditoría asíncrona centralizada en el Módulo 1 | No | Aceptada |
| [ADR-009](#adr-009-observabilidad) | Observabilidad: Prometheus, Grafana y Loki | No | Aceptada |
| [ADR-010](#adr-010-componente-de-inteligencia-artificial) | IA: chatbot sobre la API de Gemini con herramientas de solo lectura | No | Aceptada |

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

* **Estado:** Aceptada. Elimina la alternativa "RabbitMQ o Redis Streams".
* **Contexto:** Correos, métricas, habilitación de reseñas y bitácora de auditoría no deben bloquear al usuario. La bitácora debe registrar el 100% de los accesos indebidos (ESC-04) y ser inmutable (RNF-10).
* **Decisión:** **RabbitMQ** con el exchange `turismo.eventos` (topic), una cola por consumidor, *publisher confirms*, idempotencia por `event_id` y DLQ tras 3 intentos. La auditoría tiene un único dueño, el Módulo 1: escribe sus eventos en la misma transacción de la acción y consume `auditoria.registrada` de los demás módulos; la tabla solo admite inserciones.
* **Alternativas consideradas:**
  * *Redis/Valkey Streams:* descartada; evita un componente, pero carece del enrutamiento por *topic*, las DLQ y la consola de administración que facilitan la operación y la depuración.
  * *Escritura directa de cada módulo en la bitácora del Módulo 1:* descartada; viola *Database-per-Service*.
  * *Patrón outbox desde el inicio:* pospuesta; garantiza la entrega pero agrega una tabla y un proceso por servicio. Se adoptará si las pruebas de ESC-04 muestran pérdidas.
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
