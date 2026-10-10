# Plan de Implementación y Funcionamiento Interno
## Plataforma Digital para la Gestión Integrada y Sostenible del Turismo en Santa Marta

**Curso:** Arquitectura de Software — Experiencia Final de Diseño  
**Programa:** Ingeniería de Sistemas — Universidad del Magdalena  
**Versión:** 1.0 (Especificación Técnica Interna)  
**Fecha:** Agosto 2026  
**Documento Complementario de Alto Nivel:** [Especificación de Requerimientos de Software (SRS IEEE 29148)](./Requirements_docIEEE.md)  

---

## Tabla de Contenido

* [1. Introducción y Enfoque de Implementación](#1-introducción-y-enfoque-de-implementación)
  * [1.1 Propósito del documento](#11-propósito-del-documento)
  * [1.2 Consolidación Arquitectónica: Unificación del Módulo 2 y Módulo 6](#12-consolidación-arquitectónica-unificación-del-módulo-2-y-módulo-6)
* [2. Arquitectura Interna y Descomposición de Microservicios](#2-arquitectura-interna-y-descomposición-de-microservicios)
  * [2.1 Topología General de Servicios (5 Microservicios + Perímetro)](#21-topología-general-de-servicios-5-microservicios--perímetro)
  * [2.2 Estructura Interna por Microservicio (Arquitectura Limpia / Hexagonal)](#22-estructura-interna-por-microservicio-arquitectura-limpia--hexagonal)
  * [2.3 Especificación Interna de cada Componente](#23-especificación-interna-de-cada-componente)
* [3. Stack Tecnológico Detallado y Decisiones FOSS](#3-stack-tecnológico-detallado-y-decisiones-foss)
  * [3.1 Matriz de Tecnologías y Versiones](#31-matriz-de-tecnologías-y-versiones)
  * [3.2 Justificación Técnica de Decisiones Abiertas](#32-justificación-técnica-de-decisiones-abiertas)
* [4. Mecanismos de Comunicación y Protocolos Internos](#4-mecanismos-de-comunicación-y-protocolos-internos)
  * [4.1 Comunicación Síncrona REST / HTTPS](#41-comunicación-síncrona-rest--https)
  * [4.2 Comunicación Asíncrona Orientada a Eventos (Message Broker)](#42-comunicación-asíncrona-orientada-a-eventos-message-broker)
  * [4.3 Manejo de Idempotencia y Políticas de Reintento (DLQ)](#43-manejo-de-idempotencia-y-políticas-de-reintento-dlq)
* [5. Modelos Físicos de Persistencia (Database-per-Service)](#5-modelos-físicos-de-persistencia-database-per-service)
  * [5.1 Esquema Relacional y Geoespacial (PostgreSQL + PostGIS)](#51-esquema-relacional-y-geoespacial-postgresql--postgis)
  * [5.2 Esquema NoSQL Documental (MongoDB / JSONB)](#52-esquema-nosql-documental-mongodb--jsonb)
  * [5.3 Estructuras en Memoria y Estrategia de Caché (Valkey / Redis)](#53-estructuras-en-memoria-y-estrategia-de-caché-valkey--redis)
* [6. Flujos de Ejecución y Secuencias Internas Clave](#6-flujos-de-ejecución-y-secuencias-internas-clave)
  * [6.1 Flujo 1: Autenticación, Emisión de Tokens y Propagación de Identidad](#61-flujo-1-autenticación-emisión-de-tokens-y-propagación-de-identidad)
  * [6.2 Flujo 2: Búsqueda Geoespacial Indexada con PostGIS y Caché](#62-flujo-2-búsqueda-geoespacial-indexada-con-postgis-y-caché)
  * [6.3 Flujo 3: Transacción Atómica de Reserva y Bloqueo de Cupos](#63-flujo-3-transacción-atómica-de-reserva-y-bloqueo-de-cupos)
  * [6.4 Flujo 4: Publicación de Reseña, Pre-filtrado Heurístico y Despacho de Eventos](#64-flujo-4-publicación-de-reseña-pre-filtrado-heurístico-y-despacho-de-eventos)
  * [6.5 Flujo 5: Pipeline Asíncrono de Inferencia de Recomendaciones con IA](#65-flujo-5-pipeline-asíncrono-de-inferencia-de-recomendaciones-con-ia)
  * [6.6 Flujo 6: Consolidación Analítica de Capacidad de Carga y Alertas Institucionales](#66-flujo-6-consolidación-analítica-de-capacidad-de-carga-y-alertas-institucionales)
* [7. Entorno de Ejecución, Contenedores y Observabilidad](#7-entorno-de-ejecución-contenedores-y-observabilidad)
  * [7.1 Orquestación Local con Docker Compose](#71-orquestación-local-con-docker-compose)
  * [7.2 Redes Virtuales y Segmentación de Seguridad](#72-redes-virtuales-y-segmentación-de-seguridad)
  * [7.3 Telemetría y Monitoreo con Prometheus y Grafana](#73-telemetría-y-monitoreo-con-prometheus-y-grafana)
* [8. Estrategia de Pruebas Internas y Validación de Carga](#8-estrategia-de-pruebas-internas-y-validación-de-carga)

---

## 1. Introducción y Enfoque de Implementación

### 1.1 Propósito del documento

El propósito del presente documento es detallar la **arquitectura técnica interna, los modelos de ejecución, los contratos de comunicación y los mecanismos de persistencia** que sustentan el desarrollo de la Plataforma Digital para la Gestión Integrada y Sostenible del Turismo en Santa Marta.

A diferencia de la [Especificación de Requerimientos de Software (SRS)](./Requirements_docIEEE.md), que se enfoca en la perspectiva de alto nivel (el *qué* del sistema, acuerdos de alcance, requerimientos funcionales, atributos de calidad y cronograma general), este Plan de Implementación define el **funcionamiento interno** (el *cómo* técnico, decisiones de bajo nivel, diseño de componentes, esquemas de bases de datos, manejo de concurrencia y despliegue físico).

---

### 1.2 Consolidación Arquitectónica: Unificación del Módulo 2 y Módulo 6

En la concepción original de la arquitectura se contemplaban 6 microservicios. No obstante, tras el análisis de cohesión funcional, acoplamiento de datos y viabilidad operativa para un equipo de 5 ingenieros en 14 semanas, **el Módulo 6 (Analítica & Destino) ha sido absorbido íntegramente por el Módulo 2 (Catálogo & GIS)**, pasando a denominarse:

> **Módulo 2: Catálogo, GIS & Inteligencia de Destino (Catalog, GIS & Destination Analytics Service)**

#### Justificación Técnica de la Fusión:
1. **Cohesión de Dominio y Co-localización de Datos:** Los indicadores analíticos (demanda por zonas, cálculo de presión sobre atractivos, capacidad de carga ambiental y generación de mapas de calor) operan sobre las mismas entidades geoespaciales y tablas de servicios que administra el catálogo. Separarlos en dos microservicios obligaba a duplicar esquemas espaciales o a realizar costosas consultas distribuidas a través de la red.
2. **Eficiencia en la Persistencia Espacial:** La extensión espacial **PostGIS** de PostgreSQL permite ejecutar funciones de agregación analítica espacial directa (`ST_DWithin`, `ST_ClusterKMeans`, densidades kernel) en la misma base de datos donde residen los puntos de interés turístico, optimizando drásticamente los tiempos de respuesta.
3. **Reducción de Sobrecarga Operativa:** Se reduce la cantidad de servicios a compilar, desplegar y monitorear de 6 a **5 microservicios core**, disminuyendo el riesgo técnico **R-01** (curva de aprendizaje en microservicios) y simplificando la orquestación en Docker Compose.

---

## 2. Arquitectura Interna y Descomposición de Microservicios

### 2.1 Topología General de Servicios (5 Microservicios + Perímetro)

La plataforma se organiza en **cinco microservicios desacoplados**, un **API Gateway perimetral** y una **infraestructura transversal de mensajería y observabilidad**:

```mermaid
flowchart TB
    classDef clientStyle fill:#eff6ff,stroke:#2563eb,stroke-width:2px,color:#1e40af,font-weight:bold;
    classDef gwStyle fill:#f5f3ff,stroke:#7c3aed,stroke-width:2px,color:#5b21b6,font-weight:bold;
    classDef coreStyle fill:#f0fdf4,stroke:#16a34a,stroke-width:2px,color:#14532d,font-weight:bold;
    classDef aiStyle fill:#fdf4ff,stroke:#c026d3,stroke-width:2px,color:#701a75,font-weight:bold;
    classDef brokerStyle fill:#fffbeb,stroke:#d97706,stroke-width:2px,color:#78350f,font-weight:bold;
    classDef dbStyle fill:#f8fafc,stroke:#475569,stroke-width:2px,color:#0f172a;
    classDef cacheStyle fill:#fff1f2,stroke:#e11d48,stroke-width:2px,color:#881337;

    Clients["Clientes Web & Móviles<br><i>(Turistas, Prestadores, Entidades, Admins)</i>"]:::clientStyle
    APIGW["API Gateway & Reverse Proxy<br><i>(Nginx / Traefik: TLS, JWT Perimetral, Rate Limiting)</i>"]:::gwStyle

    Clients ==>|HTTPS / REST| APIGW

    subgraph Microservicios["Ecosistema de Microservicios FOSS (5 Módulos)"]
        direction TB
        MS1["Módulo 1: Seguridad & IAM<br><i>(Autenticación, RBAC, Auditoría, Validación RNT/RUT)</i>"]:::coreStyle
        MS2["Módulo 2: Catálogo, GIS & Inteligencia de Destino<br><i>(Atractivos, PostGIS, Mapas OSM, Analítica, Aforos, Alertas)</i>"]:::coreStyle
        MS3["Módulo 3: Reservas & Cupos<br><i>(Motor Transaccional de Cupos, Solicitudes, Estados)</i>"]:::coreStyle
        MS4["Módulo 4: Reseñas & Moderación<br><i>(Opiniones, Calificaciones, Pre-filtro Heurístico)</i>"]:::coreStyle
        MS5["Módulo 5: IA & Recomendación<br><i>(Worker Asíncrono Python, Filtrado Híbrido, Explicabilidad)</i>"]:::aiStyle
    end

    APIGW -->|/api/v1/auth, /api/v1/users| MS1
    APIGW -->|/api/v1/catalog, /api/v1/destinations, /api/v1/analytics| MS2
    APIGW -->|/api/v1/bookings, /api/v1/availability| MS3
    APIGW -->|/api/v1/reviews| MS4

    subgraph EventBus["Bus de Mensajería & Eventos Asíncronos"]
        Broker["Message Broker FOSS<br><i>(RabbitMQ / Redis Streams)</i>"]:::brokerStyle
    end

    MS3 -.->|Publica: reserva.creada / reserva.confirmada| Broker
    MS4 -.->|Publica: resena.creada| Broker
    MS2 -.->|Publica: alerta.oficial / Envia notificaciones| Broker
    Broker -.->|Consume: cálculo de afinidad| MS5
    Broker -.->|Consume: despacho de correos SMTP| MS2

    subgraph Persistencia["Persistencia Políglota FOSS (Database-per-Service)"]
        direction LR
        DB1[("PostgreSQL<br>db_iam")]:::dbStyle
        DB2[("PostgreSQL + PostGIS<br>db_catalog_analytics")]:::dbStyle
        DB3[("PostgreSQL<br>db_bookings")]:::dbStyle
        DB4[("MongoDB Community / JSONB<br>db_reviews")]:::dbStyle
        Cache[("Valkey / Redis<br>Caché, Sesiones & Rate Limit")]:::cacheStyle
    end

    MS1 --- DB1
    MS2 --- DB2
    MS3 --- DB3
    MS4 --- DB4
    MS1 & MS2 & MS3 --- Cache
```

---

### 2.2 Estructura Interna por Microservicio (Arquitectura Limpia / Hexagonal)

Cada microservicio del backend se organiza internamente bajo los principios de **Arquitectura Hexagonal (Ports & Adapters)** para desacoplar las reglas de negocio de los detalles de infraestructura, frameworks y bases de datos:

```text
src/
├── domain/                    # Entidades puras y reglas de negocio del dominio
│   ├── model/                 # Objetos de dominio, Value Objects y Agregados
│   └── exception/             # Excepciones de negocio tipadas
├── application/               # Casos de uso y orquestación de flujos
│   ├── port/
│   │   ├── in/                # Interfaces de entrada (casos de uso)
│   │   └── out/               # Interfaces de salida (repositorios, brokers, mailers)
│   ├── service/               # Implementación de casos de uso
│   └── dto/                   # Data Transfer Objects de entrada y salida
└── infrastructure/            # Adaptadores técnicos (detalles externos)
    ├── adapter/
    │   ├── in/
    │   │   └── rest/          # Controladores HTTP REST, filtros y mapeo de DTOs
    │   └── out/
    │       ├── persistence/   # Entidades ORM / JPA / Repositorios SQL y NoSQL
    │       ├── messaging/     # Productores y consumidores de colas RabbitMQ
    │       └── external/      # Clientes HTTP (OpenStreetMap, SMTP)
    └── config/                # Inyección de dependencias, beans y variables de entorno
```

---

### 2.3 Especificación Interna de cada Componente

#### 1. Módulo 1: Seguridad & IAM Service
* **Responsabilidad Interna:** Gestión centralizada del ciclo de vida de usuarios, autenticación basada en credenciales robustas, autorización por roles (RBAC), control documental de prestadores y bitácora de auditoría inmutable.
* **Mecanismos Internos:**
  * **Cifrado de Contraseñas:** Algoritmo **Argon2id** (configuración recomendada RFC 9106: memoria 64 MB, 3 iteraciones, 4 hilos de paralelismo) que previene ataques por fuerza bruta basados en GPU/ASIC.
  * **Generador y Validador de Tokens:** Generación de JWTs firmados con clave simétrica robusta (`HS256` con clave de 256 bits) o asimétrica (`RS256`), con tiempo de vida corto (15 a 60 minutos para Access Token) y Refresh Tokens revocables almacenados en caché.
  * **Bitácora de Auditoría Asíncrona:** Registro inmutable de transacciones críticas (`USUARIO_REGISTRO`, `LOGIN_FALLIDO`, `ROL_MODIFICADO`, `PRESTADOR_VALIDADO`). Las inserciones se realizan en la tabla relacional `bitacora_auditoria` con índice temporal B-Tree.

#### 2. Módulo 2: Catálogo, GIS & Inteligencia de Destino (Módulo Unificado)
* **Responsabilidad Interna:** Administración y renderizado del catálogo turístico, procesamiento de consultas espaciales con mapas libres, analítica agregada de demanda turística, estimación de capacidad de carga y despacho de alertas institucionales y correos transaccionales.
* **Mecanismos Internos:**
  * **Capa Geoespacial PostGIS:** Almacenamiento de puntos georreferenciados mediante el tipo nativo `GEOMETRY(Point, 4326)` o `GEOGRAPHY(Point)`. Búsquedas por radio y proximidad ejecutadas mediante la función `ST_DWithin` optimizada con índices espaciales `GIST`.
  * **Caché de Segundo Nivel:** Consultas de alto tráfico (catálogo general y listados de categorías) cacheadas en **Valkey/Redis** con un tiempo de expiración (TTL) de 300 segundos, invalidándose ante mutaciones del catálogo mediante eventos.
  * **Submódulo de Analítica y Capacidad de Carga:** Rutinas de agregación SQL sobre reservas y visitas para calcular el índice de saturación de cada atractivo:
    $$\text{Índice de Saturación} = \frac{\sum \text{Visitantes Estimados}}{\text{Capacidad de Carga Oficial}}$$
    Si el índice supera el 85%, el sistema marca el atractivo con bandera de advertencia y habilita al rol Entidad para emitir alertas oficiales (UC26).
  * **Worker de Notificaciones Transaccionales (SMTP):** Consumidor interno que escucha eventos de reservas confirmadas/canceladas y envía correos electrónicos formateados en HTML con plantillas embebidas mediante conexión SMTP segura (TLS).

#### 3. Módulo 3: Reservas & Cupos (Bookings & Availability Service)
* **Responsabilidad Interna:** Motor transaccional de alta consistencia para consulta, bloqueo temporal y confirmación de cupos de servicios turísticos.
* **Mecanismos Internos:**
  * **Control de Concurrencia y Bloqueo Atómico:** Para evitar condiciones de carrera (*race conditions*) y sobreventa (*overbooking*), las operaciones de reserva ejecutan una consulta de actualización con bloqueo pesimista a nivel de fila en PostgreSQL:
    ```sql
    SELECT cupos_disponibles FROM disponibilidad_cupo 
    WHERE servicio_id = $1 AND fecha = $2 
    FOR UPDATE;
    ```
    Si `cupos_disponibles >= personas_solicitadas`, se descuentan los cupos atómicamente y se inserta la solicitud de reserva en estado `Solicitada` dentro de una transacción serializable.
  * **Publicador de Eventos de Dominio:** Al persistirse exitosamente una reserva o confirmarse por parte del prestador, se publica de forma asíncrona el evento `reserva.creada` o `reserva.confirmada` hacia el broker de mensajería.

#### 4. Módulo 4: Reseñas & Moderación (Reviews & Moderation Service)
* **Responsabilidad Interna:** Captura de opiniones y calificaciones de turistas, réplicas de prestadores y filtro de moderación previo.
* **Mecanismos Internos:**
  * **Pre-filtro Heurístico Ligero:** Procesador léxico embebido en el microservicio que normaliza el texto (minúsculas, remoción de diacríticos y lematización básica) y evalúa una lista negra de patrones y palabras ofensivas.
    * Si el texto supera el umbral de sensibilidad, se almacena con estado `En_Revision` y se encola para moderación del Administrador (UC29).
    * Si el texto es limpio, se publica inmediatamente con estado `Publicado`.
  * **Almacenamiento NoSQL / Semi-estructurado:** Almacenamiento en colecciones de MongoDB o tablas relacionales con columnas `JSONB` de PostgreSQL para permitir estructuras de calificaciones multidimensionales (limpieza, puntualidad, precio, amabilidad) y respuestas anidadas del prestador.

#### 5. Módulo 5: IA & Recomendación (AI Recommendation Service)
* **Responsabilidad Interna:** Motor analítico auxiliar en Python que computa afinidades turísticas y genera recomendaciones personalizadas con explicabilidad algorítmica.
* **Mecanismos Internos:**
  * **Worker Asíncrono Desacoplado:** El microservicio no expone rutas bloqueantes de cálculo pesado para los usuarios finales. Consume eventos del broker en segundo plano para actualizar perfiles y calcula recomendaciones que deposita en caché o en base de datos.
  * **Filtrado Híbrido:**
    1. *Filtrado basado en contenido:* Similitud de coseno entre las preferencias declaradas por el turista (categorías preferidas, rango de presupuesto) y los metadatos de los atractivos.
    2. *Filtrado colaborativo ligero:* Modelo de descomposición matricial (SVD o matrices de co-ocurrencia) entrenado sobre el dataset sintético de turistas y visitas a Santa Marta.
  * **Generador de Explicabilidad (RNF-08):** Cada recomendación genera una cadena de texto estructurada con el motivo de la inferencia (ej. *"Recomendado porque reservaste un tour en Taganga y tienes afinidad con actividades acuáticas"*).

---

## 3. Stack Tecnológico Detallado y Decisiones FOSS

### 3.1 Matriz de Tecnologías y Versiones

| Capa / Componente | Tecnología Seleccionada | Versión | Licencia | Rol en la Arquitectura |
|---|---|---|---|---|
| **API Gateway & Reverse Proxy** | **Nginx** | 1.24+ | BSD-2-Clause | Terminación TLS/SSL, enrutamiento perimetral, validación de cabeceras, compresión gzip y Rate Limiting. |
| **Backend Core (Módulos 1, 2, 3, 4)** | **Node.js (NestJS / Express)** o **Java (Spring Boot)** | Node 20 LTS / Java 17+ | MIT / Apache 2.0 | Microservicios transaccionales con tipado estricto, inyección de dependencias y controladores REST. |
| **Backend IA (Módulo 5)** | **Python (FastAPI + Scikit-Learn)** | Python 3.11+ | PSF / BSD | Microservicio de inferencia de recomendaciones y procesamiento matemático vectorial. |
| **Base de Datos Relacional / GIS** | **PostgreSQL + PostGIS** | PG 16 / PostGIS 3.4 | PostgreSQL / GPL-2.0 | Persistencia transaccional ACID para IAM, Reservas y Catálogo con soporte geoespacial. |
| **Base de Datos Documental** | **MongoDB Community Edition** *(o PG JSONB)* | 7.0+ | SSPL / PostgreSQL | Almacenamiento de reseñas, calificaciones multidimensionales y bitácoras semiestructuradas. |
| **Caché en Memoria** | **Valkey** *(fork FOSS de Redis)* | 7.2+ | BSD-3-Clause | Caché de segundo nivel, almacenamiento de listas de revocación de tokens y control de sesiones. |
| **Message Broker (Event Bus)** | **RabbitMQ** | 3.12+ | MPL 2.0 | Bus de mensajería asíncrona basado en el estándar AMQP 0-9-1 para eventos desacoplados. |
| **Cartografía y Mapas Web** | **OpenStreetMap + Leaflet.js** | Leaflet 1.9+ | ODbL / BSD-2-Clause | Visualización interactiva de mapas en el frontend sin costos comerciales por consulta. |
| **Frontend Web** | **HTML5, Vanilla CSS3, JavaScript / Vue.js** | Vue 3 (opcional) | MIT | Interfaz de usuario responsiva, accesible (WCAG 2.1 AA) e internacionalizada (i18n). |
| **Contenedores y Orquestación** | **Docker & Docker Compose** | Engine 24+ | Apache 2.0 | Estandarización y ejecución reproducible de todos los servicios e infraestructura en Linux. |
| **Observabilidad y Métricas** | **Prometheus + Grafana** | Prom 2.45+ / Graf 10+ | Apache 2.0 / AGPL-3.0 | Recolección de métricas de rendimiento y visualización de tableros de salud operativa. |

---

### 3.2 Justificación Técnica de Decisiones Abiertas

1. **Adopción de Valkey frente a Redis:** En 2024, Redis cambió su modelo de licenciamiento a licencias no aprobadas por la OSI (RSALv2 / SSPL). Para preservar el compromiso de Software Libre 100% (FOSS) y compatibilidad directa de protocolos (`redis-cli`, librerías cliente), se adopta **Valkey**, bifurcación comunitaria bajo licencia permisiva BSD-3-Clause respaldada por la Linux Foundation.
2. **PostGIS como núcleo analítico y de catálogo:** Al unificar el Módulo 6 dentro del Módulo 2, PostGIS se convierte en el motor analítico central. Permite cálculos espaciales de proximidad y clusters de saturación directamente en el motor de base de datos sin requerir herramientas analíticas de terceros.
3. **Persistencia de Reseñas: MongoDB vs PostgreSQL JSONB:**
   * Si el equipo busca minimizar la cantidad de motores en ejecución local (mitigación del riesgo de memoria en Docker), las reseñas se modelan como tablas relacionales con campos `JSONB` e índices `GIN` dentro de PostgreSQL.
   * Si se despliega MongoDB Community, se aísla en su propio contenedor dentro de la red interna de datos.

---

## 4. Mecanismos de Comunicación y Protocolos Internos

### 4.1 Comunicación Síncrona REST / HTTPS

Las peticiones iniciadas por clientes web o móviles interactúan exclusivamente con el **API Gateway** a través de HTTPS. El Gateway realiza la terminación SSL y redirige internamente las solicitudes al microservicio correspondiente a través de la red privada de Docker:

* **Formato de Carga:** JSON (Content-Type: `application/json`).
* **Estándar de Errores:** Respuestas de error estructuradas conforme a la especificación **RFC 7807 (Problem Details for HTTP APIs)**:
  ```json
  {
    "type": "https://api.turismosantamarta.gov.co/errors/insufficient-availability",
    "title": "Cupos insuficientes",
    "status": 409,
    "detail": "El servicio no cuenta con los 4 cupos solicitados para la fecha 2026-10-15.",
    "instance": "/api/v1/bookings",
    "timestamp": "2026-10-15T14:32:00Z"
  }
  ```
* **Trazabilidad y Correlación:** Cada petición entrante en el API Gateway recibe un identificador único en la cabecera `X-Correlation-ID`. Dicho identificador es propagado a todas las llamadas internas y registrado en los logs de los microservicios para auditoría y observabilidad.

---

### 4.2 Comunicación Asíncrona Orientada a Eventos (Message Broker)

Para garantizar que operaciones lentas (cálculo de recomendaciones con IA, envío de correos electrónicos transaccionales, auditoría) no bloqueen las peticiones de los usuarios, se utiliza un bus de mensajería con **RabbitMQ**:

#### Topología de RabbitMQ:
* **Exchange Principal:** `tourism.topic` (Tipo: `topic`, Durable: `true`).
* **Routing Keys y Colas:**

| Routing Key | Evento Emitido Por | Colas Suscritas | Consumidor Interno | Acción Ejecutada |
|---|---|---|---|---|
| `booking.created` | Módulo 3 (Reservas) | `q.ai.interactions` | Módulo 5 (IA) | Actualiza el vector de interés del turista. |
| `booking.confirmed` | Módulo 3 (Reservas) | `q.notifications.email` | Módulo 2 (Catálogo/Analítica) | Envía correo de confirmación al turista con datos del prestador. |
| `booking.cancelled` | Módulo 3 (Reservas) | `q.notifications.email` | Módulo 2 (Catálogo/Analítica) | Notifica al prestador y libera cupos. |
| `review.published` | Módulo 4 (Reseñas) | `q.ai.sentiment` | Módulo 5 (IA) | Actualiza ponderación de calidad del servicio sugerido. |
| `alert.published` | Módulo 2 (Catálogo/Analítica) | `q.notifications.broadcast` | Módulo 2 (Catálogo/Analítica) | Despacha notificaciones oficiales sobre aforo o cierres temporales. |

#### Esquema Estándar de Mensaje JSON:
```json
{
  "eventId": "a7b3c94d-5821-4bfe-98e3-0d2938174201",
  "eventType": "booking.confirmed",
  "occurredAt": "2026-10-12T16:20:00Z",
  "correlationId": "corr-88de-5c16-1e3d-4a4f",
  "producer": "bookings-service",
  "data": {
    "bookingId": "c4d8e219-9f7a-4b02-861d-910283746192",
    "touristId": "u-102938",
    "touristEmail": "turista@ejemplo.com",
    "serviceId": "srv-playa-cristal-01",
    "serviceName": "Tour Playa Cristal con Guía Local",
    "reservationDate": "2026-11-05",
    "partySize": 2
  }
}
```

---

### 4.3 Manejo de Idempotencia y Políticas de Reintento (DLQ)

Para prevenir efectos secundarios no deseados causados por la entrega repetida de mensajes en el bus:
1. **Identificador de Idempotencia:** Cada consumidor almacena en caché Valkey el `eventId` procesado con un TTL de 24 horas. Si llega un mensaje con un `eventId` ya existente en la caché, se reconoce (`ACK`) y se descarta su reejecución.
2. **Dead Letter Queue (DLQ):** Los mensajes que fallen durante el procesamiento tras 3 intentos sucesivos con retroceso exponencial (*exponential backoff*: 1s, 5s, 25s) son enrutados automáticamente al exchange `tourism.dlx` y depositados en la cola `q.dead-letter` para análisis del equipo de operaciones.

---

## 5. Modelos Físicos de Persistencia (Database-per-Service)

### 5.1 Esquema Relacional y Geoespacial (PostgreSQL + PostGIS)

#### 1. Base de Datos: `db_iam` (Módulo 1: Seguridad & IAM)
```sql
CREATE TABLE usuarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(150) NOT NULL,
    telefono VARCHAR(30),
    rol VARCHAR(20) NOT NULL CHECK (rol IN ('TURISTA', 'PRESTADOR', 'ENTIDAD', 'ADMIN')),
    activo BOOLEAN DEFAULT TRUE,
    habeas_data_aceptado BOOLEAN NOT NULL DEFAULT FALSE,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE documentos_verificacion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    tipo_documento VARCHAR(20) NOT NULL CHECK (tipo_documento IN ('RNT', 'RUT')),
    numero_registro VARCHAR(50),
    archivo_url VARCHAR(500) NOT NULL,
    estado VARCHAR(20) DEFAULT 'PENDIENTE' CHECK (estado IN ('PENDIENTE', 'APROBADO', 'RECHAZADO')),
    observaciones TEXT,
    fecha_subida TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    revisado_por UUID REFERENCES usuarios(id)
);

CREATE TABLE bitacora_auditoria (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id UUID REFERENCES usuarios(id),
    accion VARCHAR(50) NOT NULL,
    ip_origen VARCHAR(45) NOT NULL,
    detalles JSONB,
    fecha_evento TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_bitacora_fecha ON bitacora_auditoria(fecha_evento);
CREATE INDEX idx_bitacora_usuario ON bitacora_auditoria(usuario_id);
```

#### 2. Base de Datos: `db_catalog_analytics` (Módulo 2: Catálogo, GIS & Inteligencia de Destino)
```sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE categorias_servicios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) UNIQUE NOT NULL,
    descripcion TEXT
);

CREATE TABLE atractivos_servicios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prestador_id UUID NOT NULL,
    categoria_id INT REFERENCES categorias_servicios(id),
    nombre VARCHAR(150) NOT NULL,
    descripcion TEXT NOT NULL,
    ubicacion_nombre VARCHAR(150) NOT NULL,
    coordenadas GEOMETRY(Point, 4326) NOT NULL,
    tarifa_base NUMERIC(12, 2) NOT NULL DEFAULT 0.0,
    capacidad_aforo_diario INT NOT NULL DEFAULT 50,
    estado VARCHAR(20) DEFAULT 'PUBLICADO' CHECK (estado IN ('BORRADOR', 'PUBLICADO', 'INACTIVO')),
    imagenes_urls TEXT[],
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_servicios_coordenadas ON atractivos_servicios USING GIST(coordenadas);
CREATE INDEX idx_servicios_categoria ON atractivos_servicios(categoria_id);

CREATE TABLE alertas_oficiales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entidad_usuario_id UUID NOT NULL,
    atractivo_servicio_id UUID REFERENCES atractivos_servicios(id),
    nivel_alerta VARCHAR(20) NOT NULL CHECK (nivel_alerta IN ('INFORMATIVA', 'PREVENTIVA', 'CRITICA')),
    titulo VARCHAR(150) NOT NULL,
    mensaje TEXT NOT NULL,
    activa BOOLEAN DEFAULT TRUE,
    fecha_emision TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fecha_expiracion TIMESTAMP WITH TIME ZONE
);
```

#### 3. Base de Datos: `db_bookings` (Módulo 3: Reservas & Cupos)
```sql
CREATE TABLE disponibilidad_cupo (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    servicio_id UUID NOT NULL,
    fecha DATE NOT NULL,
    cupos_totales INT NOT NULL CHECK (cupos_totales >= 0),
    cupos_disponibles INT NOT NULL CHECK (cupos_disponibles >= 0),
    tarifa_especial NUMERIC(12, 2),
    UNIQUE (servicio_id, fecha)
);
CREATE INDEX idx_disp_servicio_fecha ON disponibilidad_cupo(servicio_id, fecha);

CREATE TABLE solicitudes_reserva (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    turista_id UUID NOT NULL,
    servicio_id UUID NOT NULL,
    fecha_reserva DATE NOT NULL,
    cantidad_personas INT NOT NULL CHECK (cantidad_personas > 0),
    precio_total NUMERIC(12, 2) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'SOLICITADA' 
        CHECK (estado IN ('SOLICITADA', 'CONFIRMADA', 'RECHAZADA', 'CANCELADA', 'FINALIZADA')),
    motivo_rechazo_cancelacion TEXT,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_reservas_turista ON solicitudes_reserva(turista_id);
CREATE INDEX idx_reservas_servicio ON solicitudes_reserva(servicio_id);
```

---

### 5.2 Esquema NoSQL Documental (MongoDB / JSONB)

Colección: `resenas` (Módulo 4: Reseñas & Moderación)

```json
{
  "_id": { "$oid": "64fe8b1092a71d45c82901a1" },
  "servicioId": "c4d8e219-9f7a-4b02-861d-910283746192",
  "turistaId": "u-102938",
  "turistaNombre": "Carlos M.",
  "puntuacion": 5,
  "calificacionesDetalle": {
    "limpieza": 5,
    "guianza": 5,
    "relacionCalidadPrecio": 4
  },
  "comentario": "Excelente recorrido ecológico en Minca, muy recomendado para conectar con la naturaleza.",
  "contieneLenguajeSensible": false,
  "estadoModeracion": "PUBLICADO",
  "respuestaPrestador": {
    "texto": "¡Muchas gracias Carlos! Te esperamos de vuelta.",
    "respondidoEn": "2026-10-14T10:15:00Z"
  },
  "creadoEn": "2026-10-12T18:00:00Z"
}
```

---

### 5.3 Estructuras en Memoria y Estrategia de Caché (Valkey / Redis)

* **Prefijo `token:blacklist:{jwtId}`:** Almacena JWTs revocados anticipadamente hasta su expiración (TTL = tiempo restante del token).
* **Prefijo `rate_limit:{ip}:{ruta}`:** Llaves enteras gestionadas con el algoritmo *Token Bucket* / *Fixed Window Counter* (`INCR` con TTL de 60 segundos) para bloquear abusos si se superan 100 peticiones por minuto.
* **Prefijo `catalog:item:{servicioId}`:** Serialización JSON con la ficha del atractivo y sus coordenadas (TTL = 600 segundos).
* **Prefijo `recommendations:user:{turistaId}`:** Listado de los 5 atractivos con mayor afinidad generados por el Módulo 5 (TTL = 1800 segundos).

---

## 6. Flujos de Ejecución y Secuencias Internas Clave

### 6.1 Flujo 1: Autenticación, Emisión de Tokens y Propagación de Identidad

```mermaid
sequenceDiagram
    autonumber
    actor User as Usuario (Frontend)
    participant GW as API Gateway
    participant IAM as Módulo 1 (IAM)
    participant Cache as Valkey (Caché)
    participant DB as PostgreSQL (db_iam)

    User->>GW: POST /api/v1/auth/login {email, password}
    GW->>IAM: Proxy a /auth/login
    IAM->>DB: Consultar usuario por email
    DB-->>IAM: Registro de usuario y password_hash (Argon2id)
    IAM->>IAM: Verificar Argon2id(password, hash)
    alt Credenciales Válidas
        IAM->>IAM: Generar JWT (sub, rol, exp, jti)
        IAM->>DB: Registrar LOGIN_EXITOSO en bitácora
        IAM-->>GW: HTTP 200 {access_token, token_type: Bearer, user_info}
        GW-->>User: Retornar token al cliente
    else Credenciales Inválidas
        IAM->>DB: Registrar LOGIN_FALLIDO en bitácora
        IAM-->>GW: HTTP 401 Unauthorized
        GW-->>User: HTTP 401 Unauthorized
    end
```

---

### 6.2 Flujo 2: Búsqueda Geoespacial Indexada con PostGIS y Caché

```mermaid
sequenceDiagram
    autonumber
    actor Tur as Turista
    participant GW as API Gateway
    participant Cache as Valkey
    participant Cat as Módulo 2 (Catálogo & GIS)
    participant PostGIS as DB PostGIS

    Tur->>GW: GET /api/v1/catalog/search?lat=11.24&lon=-74.21&radius=5000&cat=Playas
    GW->>Cat: Proxy consulta de búsqueda
    Cat->>Cache: GET cache:search:11.24:-74.21:5000:Playas
    alt Respuesta en Caché (Hit)
        Cache-->>Cat: JSON con atractivos en radio
        Cat-->>GW: HTTP 200 (Desde Caché)
        GW-->>Tur: Lista de resultados en < 50ms
    else No está en Caché (Miss)
        Cat->>PostGIS: SELECT id, nombre, ST_Distance(...) WHERE ST_DWithin(...)
        PostGIS-->>Cat: Conjunto de filas ordenadas por cercanía
        Cat->>Cache: SETEX cache:search:... 300s (JSON)
        Cat-->>GW: HTTP 200 (Resultados frescos)
        GW-->>Tur: Lista de atractivos con marcadores OSM
    end
```

---

### 6.3 Flujo 3: Transacción Atómica de Reserva y Bloqueo de Cupos

```mermaid
sequenceDiagram
    autonumber
    actor Tur as Turista
    participant GW as API Gateway
    participant Book as Módulo 3 (Reservas & Cupos)
    participant DB as PostgreSQL (db_bookings)
    participant Broker as RabbitMQ

    Tur->>GW: POST /api/v1/bookings {servicioId, fecha, partySize: 2} (Bearer Token)
    GW->>GW: Validar firma de JWT y rol 'TURISTA'
    GW->>Book: Enrutar solicitud a Módulo 3
    Book->>DB: BEGIN TRANSACTION;
    Book->>DB: SELECT cupos_disponibles FROM disponibilidad_cupo FOR UPDATE;
    alt Cupos Disponibles >= 2
        Book->>DB: UPDATE disponibilidad_cupo SET cupos_disponibles = cupos_disponibles - 2;
        Book->>DB: INSERT INTO solicitudes_reserva (...) VALUES (..., 'SOLICITADA');
        Book->>DB: COMMIT;
        Book->>Broker: Publicar evento 'booking.created' en tourism.topic
        Book-->>GW: HTTP 201 Created {reservaId, estado: 'SOLICITADA'}
        GW-->>Tur: Solicitud confirmada al usuario
    else Sin Cupos Suficientes
        Book->>DB: ROLLBACK;
        Book-->>GW: HTTP 409 Conflict (RFC 7807: Cupos Insuficientes)
        GW-->>Tur: Error estructurado explicativo
    end
```

---

### 6.4 Flujo 4: Publicación de Reseña, Pre-filtrado Heurístico y Despacho de Eventos

```mermaid
sequenceDiagram
    autonumber
    actor Tur as Turista
    participant GW as API Gateway
    participant Rev as Módulo 4 (Reseñas)
    participant Filter as Pre-filtro Heurístico (Embebido)
    participant DB as MongoDB / JSONB
    participant Broker as RabbitMQ

    Tur->>GW: POST /api/v1/reviews {servicioId, rating: 5, comentario}
    GW->>Rev: Proxy reseña
    Rev->>Filter: Evaluar comentario (análisis léxico)
    alt Comentario Aprobado (Limpio)
        Filter-->>Rev: Resultado: LIMPIO
        Rev->>DB: Insertar documento {estadoModeracion: 'PUBLICADO'}
        Rev->>Broker: Publicar 'review.published'
        Rev-->>GW: HTTP 201 Created {estado: 'PUBLICADO'}
    else Detectado Lenguaje Ofensivo
        Filter-->>Rev: Resultado: SOSPECHOSO
        Rev->>DB: Insertar documento {estadoModeracion: 'EN_REVISION'}
        Rev-->>GW: HTTP 202 Accepted {mensaje: 'Reseña enviada a moderación'}
    end
    GW-->>Tur: Respuesta al cliente
```

---

### 6.5 Flujo 5: Pipeline Asíncrono de Inferencia de Recomendaciones con IA

```mermaid
sequenceDiagram
    autonumber
    participant Broker as RabbitMQ
    participant AI as Módulo 5 (Worker Python IA)
    participant Models as Matrices Sintéticas / SVD
    participant Cache as Valkey (Caché)

    Broker->>AI: Consumir evento 'booking.created' / 'review.published'
    AI->>AI: Extraer turistaId, servicioId y categoría
    AI->>Models: Calcular afinidad híbrida (Contenido + Filtrado Colaborativo)
    AI->>AI: Aplicar regla de sostenibilidad (priorizar destinos con aforo bajo)
    AI->>AI: Construir texto explicativo (RNF-08)
    AI->>Cache: Guardar SETEX recommendations:user:{turistaId} 1800s
    AI->>Broker: ACK mensaje procesado exitosamente
```

---

### 6.6 Flujo 6: Consolidación Analítica de Capacidad de Carga y Alertas Institucionales

Al estar unificado en el **Módulo 2 (Catálogo, GIS & Inteligencia de Destino)**:

1. **Cálculo de Aforos:** Un cron programado cada 30 minutos ejecuta una consulta agregada que suma las reservas activas por fecha y sector geográfico, comparándola con la capacidad oficial registrada en `atractivos_servicios.capacidad_aforo_diario`.
2. **Generación de Mapa de Calor:** El backend transforma las coordenadas y porcentajes de saturación a formato **GeoJSON** para su visualización inmediata en Leaflet.js por parte de la Entidad de Gestión.
3. **Emisión de Alertas:** Cuando la Entidad emite una alerta preventiva (UC26), se inserta en `alertas_oficiales` y se publica el evento `alert.published` en RabbitMQ, lo que dispara una notificación visual flotante para los turistas que visualizan el mapa interactivo.

---

## 7. Entorno de Ejecución, Contenedores y Observabilidad

### 7.1 Orquestación Local con Docker Compose

Para el entorno de desarrollo y validación académica, todos los componentes se ejecutan mediante un archivo `docker-compose.yml` unificado:

```yaml
version: '3.8'

services:
  # 1. Reverse Proxy & Perímetro
  api-gateway:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./infra/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    networks:
      - frontend-net
      - backend-net
    depends_on:
      - iam-service
      - catalog-service
      - bookings-service
      - reviews-service

  # 2. Microservicios Backend Core
  iam-service:
    build: ./services/iam-service
    environment:
      - PORT=3001
      - DB_URL=postgresql://iam_user:iam_pass@postgres-iam:5432/db_iam
      - JWT_SECRET=super_secret_key_minimum_32_characters_long
      - REDIS_URL=redis://valkey-cache:6379
    networks:
      - backend-net
      - data-net
    depends_on:
      - postgres-iam
      - valkey-cache

  catalog-service:
    build: ./services/catalog-service
    environment:
      - PORT=3002
      - DB_URL=postgresql://catalog_user:catalog_pass@postgres-catalog:5432/db_catalog_analytics
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
      - REDIS_URL=redis://valkey-cache:6379
    networks:
      - backend-net
      - data-net
    depends_on:
      - postgres-catalog
      - rabbitmq

  bookings-service:
    build: ./services/bookings-service
    environment:
      - PORT=3003
      - DB_URL=postgresql://booking_user:booking_pass@postgres-bookings:5432/db_bookings
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
    networks:
      - backend-net
      - data-net
    depends_on:
      - postgres-bookings
      - rabbitmq

  reviews-service:
    build: ./services/reviews-service
    environment:
      - PORT=3004
      - MONGO_URL=mongodb://mongodb-reviews:27017/db_reviews
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
    networks:
      - backend-net
      - data-net
    depends_on:
      - mongodb-reviews
      - rabbitmq

  # 3. Microservicio de Inteligencia Artificial (Worker)
  ai-service:
    build: ./services/ai-service
    environment:
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
      - REDIS_URL=redis://valkey-cache:6379
    networks:
      - backend-net
    depends_on:
      - rabbitmq
      - valkey-cache

  # 4. Bases de Datos & Middleware FOSS
  postgres-iam:
    image: postgres:16-alpine
    networks: [data-net]
  postgres-catalog:
    image: postgis/postgis:16-3.4-alpine
    networks: [data-net]
  postgres-bookings:
    image: postgres:16-alpine
    networks: [data-net]
  mongodb-reviews:
    image: mongo:7.0
    networks: [data-net]
  valkey-cache:
    image: valkey/valkey:7.2-alpine
    networks: [data-net]
  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    networks: [backend-net]

  # 5. Observabilidad
  prometheus:
    image: prom/prometheus:v2.45.0
    networks: [backend-net]
  grafana:
    image: grafana/grafana:10.0.0
    ports:
      - "3000:3000"
    networks: [backend-net]

networks:
  frontend-net:
    driver: bridge
  backend-net:
    driver: bridge
  data-net:
    driver: bridge
```

---

### 7.2 Redes Virtuales y Segmentación de Seguridad

Para garantizar el principio de menor privilegio en la red interna:
* **`frontend-net`:** Conecta únicamente a clientes externos con el API Gateway.
* **`backend-net`:** Conecta el API Gateway con los 5 microservicios, el broker RabbitMQ y los agentes de monitoreo.
* **`data-net`:** Conecta exclusivamente a cada microservicio con su base de datos asignada. Ningún cliente externo ni servicio no autorizado puede acceder directamente a los puertos de PostgreSQL o MongoDB.

---

### 7.3 Telemetría y Monitoreo con Prometheus y Grafana

1. **Exposición de Métricas:** Cada microservicio expone un endpoint `/metrics` en formato estándar Prometheus con métricas críticas:
   * `http_requests_total{method, route, status}`
   * `http_request_duration_seconds{route}` (para auditar percentil 95: $p95 < 2.0$s)
   * `database_connection_pool_active`
   * `rabbitmq_messages_unacknowledged`
2. **Dashboard de Grafana:** Visualización en tiempo real del estado de salud de los 5 microservicios, consumo de CPU/Memoria de contenedores y tiempos de respuesta por ruta crítica.

---

## 8. Estrategia de Pruebas Internas y Validación de Carga

1. **Pruebas Unitarias:** Implementadas con `Jest` (Node.js), `JUnit 5 / Mockito` (Java) o `pytest` (Python) para validar la lógica pura del dominio y de los casos de uso con cobertura mínima del 70%.
2. **Pruebas de Integración:** Pruebas contra contenedores reales efímeros utilizando **Testcontainers** para validar que las consultas espaciales en PostGIS y los bloqueos transaccionales en PostgreSQL operan correctamente.
3. **Pruebas de Rendimiento y Carga (k6 / Locust):**
   * **Simulación ESC-02:** 500 usuarios virtuales concurrentes consultando el catálogo y mapa interactivo mediante peticiones `GET /api/v1/catalog/search` durante 10 minutos para validar $p95 < 2.0$s.
   * **Simulación ESC-08 (Escalabilidad):** Aumento progresivo hasta 1.000 usuarios concurrentes, agregando réplicas de contenedores del Módulo 2 y 3 con `docker compose up --scale catalog-service=2 --scale bookings-service=2`.
