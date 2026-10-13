# Comparación y Selección de Alternativas Arquitectónicas

**Proyecto:** Plataforma Digital para la Gestión Integrada y Sostenible del Turismo en Santa Marta  
**Curso:** Arquitectura de Software  
**Programa:** Ingeniería de Sistemas — Universidad del Magdalena  
**Fase:** Fase 2 — Comparación Arquitectónica ([SRS, Apéndice D](./Requirements_docIEEE.md#apéndice-d-plan-de-proyecto-cronograma-y-presupuesto))  
**Decisiones derivadas:** [Registro de Decisiones Arquitectónicas](./Registro_Decisiones_Arquitectonicas.md) (ADR-002 y siguientes)  
**Documento base:** [Especificación de Requerimientos (SRS)](./Requirements_docIEEE.md)  

---

Este documento presenta el proceso de diseño seguido para seleccionar el estilo arquitectónico de la plataforma: se comparan dos alternativas viables frente a las restricciones (SRS §2.4), los atributos de calidad (SRS §3.4 y §3.5) y los riesgos del proyecto (SRS Apéndice B), y se justifica la alternativa seleccionada.

---

## 1. Alternativas Propuestas

### 1.1 Alternativa A: Monolito Modular

* **Estilo arquitectónico:** Monolito modular con arquitectura hexagonal (puertos y adaptadores) por módulo.
* **Idea general de estructura:** Una única aplicación desplegable que agrupa los cinco contextos del dominio (IAM, Catálogo, GIS & Analítica, Reservas, Reseñas, IA) como módulos internos con fronteras explícitas. Los módulos se comunican mediante llamadas en proceso a través de interfaces; las tareas diferidas (correos, auditoría) se ejecutan con una cola de trabajos interna. Persistencia en una sola instancia de PostgreSQL + PostGIS con un esquema por módulo. Se escala replicando la aplicación completa detrás de Nginx.
* **Ventaja principal:** Menor tiempo y complejidad de implementación: un solo repositorio, un solo despliegue, transacciones ACID locales entre módulos y sin infraestructura distribuida que operar, lo que se ajusta directamente a las 13 semanas y al equipo de 5 personas.
* **Desventaja principal:** Escala y falla como un bloque: un pico de búsquedas en el catálogo obliga a replicar toda la aplicación, una falla en un módulo (p. ej. Reseñas) puede degradar el sistema completo (contrario a ESC-01) y el chatbot de IA (integración con Gemini y herramientas) no puede ajustarse ni desplegarse sin redesplegar el núcleo (contrario a ESC-05).

### 1.2 Alternativa B: Microservicios Orientados a Eventos

* **Estilo arquitectónico:** Microservicios por *Bounded Context* con comunicación híbrida: síncrona REST y asíncrona orientada a eventos (Pub/Sub).
* **Idea general de estructura:** Cinco microservicios independientes en Python + FastAPI (SRS §3.6.1), desplegados como contenedores en Kubernetes (k3s) detrás de un API Gateway (Traefik) que centraliza TLS, validación de JWT, *rate limiting* y CORS. Las operaciones de respuesta inmediata usan REST/JSON; las tareas no críticas (correos, métricas, auditoría) se desacoplan mediante RabbitMQ y el chatbot de IA se consume como un servicio independiente. Cada servicio gestiona su propio almacén (*Database-per-Service*): PostgreSQL (con PostGIS y JSONB) y Valkey.
* **Ventaja principal:** Escalabilidad y aislamiento de fallos por servicio: el Catálogo puede escalar de forma independiente en temporada alta (ESC-02, ESC-08), una falla en Reseñas no interrumpe catálogo ni reservas (ESC-01) y el chatbot de IA se ajusta o se reemplaza sin detener el núcleo transaccional (ESC-05).
* **Desventaja principal:** Mayor complejidad técnica y operativa: más contenedores, consistencia eventual entre servicios, necesidad de observabilidad distribuida y una curva de aprendizaje significativa para el equipo (riesgo R-01), lo que alarga el tiempo de implementación.

---

## 2. Tabla Comparativa

Escala de calificación de **1 a 5**, donde **5 es siempre el valor más favorable** para el proyecto. En los criterios de costo, tiempo y complejidad, 5 significa *más barato*, *más rápido* y *menos complejo*, respectivamente. Puntaje ponderado = Peso × Calificación.

| Criterio | Peso (1–5) | A: Monolito Modular — Calificación | A: Ponderado | B: Microservicios — Calificación | B: Ponderado |
|---|:---:|:---:|:---:|:---:|:---:|
| **Costo relativo** | 3 | 5 (Costo **bajo**) | 15 | 3 (Costo **medio**) | 9 |
| **Tiempo de implementación** | 3 | 5 (Corto) | 15 | 2 (Largo) | 6 |
| **Escalabilidad** | 5 | 3 (Replicación completa) | 15 | 5 (Independiente por servicio) | 25 |
| **Seguridad** | 5 | 4 (Menor superficie de ataque) | 20 | 3 (Mayor superficie, mejor aislamiento de datos) | 15 |
| **Complejidad técnica** | 2 | 4 (Baja) | 8 | 2 (Alta) | 4 |
| **Disponibilidad** *(criterio adicional)* | 5 | 3 (Falla en bloque) | 15 | 5 (Aislamiento de fallos) | 25 |
| **Mantenibilidad / Evolución** *(criterio adicional)* | 4 | 3 (Despliegue conjunto) | 12 | 5 (Despliegue independiente) | 20 |
| **PUNTAJE FINAL** | **27** | | **100 / 135** | | **104 / 135** |

**Justificación de los pesos:**

* **Escalabilidad (5):** RNF-02 es *Must*; ESC-02 exige atender 500 solicitudes concurrentes por segundo en temporada alta y ESC-08 exige duplicar esa capacidad añadiendo réplicas solo de los servicios presionados, y la inestabilidad en picos de demanda es una de las problemáticas que origina el proyecto (SRS §2.1).
* **Seguridad (5):** RNF-04 y RNF-10 son *Must*; la plataforma trata datos personales bajo la Ley 1581 de 2012 y documentos legales de prestadores (RNT, RUT).
* **Disponibilidad (5):** RNF-01 y ESC-01 exigen aislar componentes degradados sin interrumpir catálogo ni reservas durante la temporada alta.
* **Mantenibilidad / Evolución (4):** RNF-05 y ESC-05 exigen ajustar el chatbot de IA (herramientas, parámetros o versión del modelo de Gemini) sin alterar el núcleo, y el SRS §1.2 define la IA como un componente desacoplado.
* **Costo relativo (3):** Ambas alternativas caben holgadamente dentro del techo de USD 20.000 (el Escenario A del SRS, Apéndice D, usa USD 6.900); el costo diferencia, pero no es restrictivo.
* **Tiempo de implementación (3):** El horizonte es de 13 semanas, pero la meta del prototipo está acotada a $\ge 60\%$ de los casos de uso *Must* (SRS, Apéndice D, Fase 4) y la asignación de un responsable por servicio (SRS, Apéndice C) permite trabajo en paralelo (R-05).
* **Complejidad técnica (2):** Se mitiga con decisiones de proceso (un solo lenguaje para todos los servicios, plantilla base, entorno local con Docker Compose, R-01) y no compromete por sí misma un atributo de calidad.

> [!NOTE]
> **Análisis de sensibilidad:** El resultado depende del horizonte de evaluación. Si se evaluara solo el prototipo académico, asignando peso 5 a *Tiempo de implementación* y a *Complejidad técnica*, el Monolito Modular obtendría **122** frente a **114** de los Microservicios. El equipo adopta como horizonte el **despliegue piloto institucional de 12 meses** (SRS, Apéndice D, Escenario B), en el cual la escalabilidad, la disponibilidad y la evolución del sistema pesan más que la velocidad de construcción inicial.

---

## 3. Decisión Justificada

**Alternativa seleccionada: B — Microservicios Orientados a Eventos**, con un puntaje de **104** frente a **100** del Monolito Modular.

**Criterios determinantes:**

1. **Escalabilidad (25 vs. 15):** La demanda turística de Santa Marta es estacional y se concentra en el catálogo; escalar solo los servicios presionados es la respuesta directa a RNF-02, ESC-02 y ESC-08.
2. **Disponibilidad (25 vs. 15):** El aislamiento de fallos garantiza que la caída de un servicio secundario (Reseñas, IA) no interrumpa las búsquedas ni las reservas (ESC-01).
3. **Mantenibilidad / Evolución (20 vs. 12):** El servicio del chatbot de IA evoluciona y se despliega de forma independiente del núcleo transaccional (ESC-05, RNF-08).

La diferencia es estrecha (4 puntos) y se reconoce explícitamente: los Microservicios pierden en costo, tiempo, complejidad y seguridad, y esas desventajas se gestionan con las mitigaciones de la Sección 4.4.

---

## 4. Análisis de Trade-offs

### 4.1 Influencia de las restricciones

* **Económicas (SRS §2.4.2):** El techo de USD 20.000 no descarta ninguna alternativa. Los Microservicios incrementan el costo de infraestructura (más contenedores, broker, varias bases de datos), pero el Escenario A (SRS, Apéndice D) demuestra que el prototipo es viable con USD 6.900 y el Escenario B financia la operación en alta disponibilidad durante 12 meses. El modelo sin pagos en línea (SRS §1.2) evita además costos de certificación PCI-DSS en cualquiera de las dos alternativas.
* **Técnicas (SRS §2.4.1):** La exigencia de software libre y de despliegue en contenedores es compatible con ambas, pero la combinación de un núcleo transaccional y un servicio de IA (chatbot sobre la API de Gemini) favorece una arquitectura que admita despliegues independientes. La exigencia de RNF-02 (*Must*) inclina la decisión hacia la escalabilidad por servicio.
* **Sociales (SRS §2.4.3):** La inclusión de prestadores con baja alfabetización digital (RF-08), el soporte bilingüe (RF-10) y la operación con conectividad limitada mediante la PWA (RNF-13, ADR-004) se resuelven en la capa de presentación y no diferencian a las alternativas. Sí influye el carácter de bien público de la plataforma: su caída en temporada alta afectaría a turistas y a pequeños prestadores, lo que refuerza el peso de la disponibilidad.
* **Normativas (SRS §2.4.5):** La Ley 1581 de 2012 favorece aislar los datos personales y los documentos legales en el servicio de IAM con su propia base de datos, limitando el alcance de una eventual brecha.

### 4.2 Qué se gana y qué se sacrifica con cada alternativa

| Alternativa | Qué se gana | Qué se sacrifica |
|---|---|---|
| **A: Monolito Modular** | Construcción más rápida, menor costo de infraestructura, transacciones ACID locales, depuración y despliegue simples, menor superficie de ataque. | Escalabilidad selectiva, aislamiento de fallos y despliegue independiente del servicio de IA; mayor riesgo de acoplamiento con el tiempo. |
| **B: Microservicios** *(seleccionada)* | Escalado independiente en temporada alta, aislamiento de fallos, evolución y despliegue independiente de la IA, un responsable por servicio, aislamiento de datos sensibles. | Mayor tiempo de implementación, complejidad operativa (broker, varias bases de datos, observabilidad), consistencia eventual entre servicios y mayor superficie de ataque interna. |

### 4.3 Restricciones que más influyeron en la decisión

1. **Picos de demanda en temporada alta** (problemática 6, RNF-02 y RNF-01): fue la restricción decisiva, ya que escalabilidad y disponibilidad concentran 50 de los 104 puntos de la alternativa seleccionada.
2. **Desacople del servicio de IA** (SRS §1.2, ESC-05): el chatbot de recomendaciones debe operar de forma independiente del núcleo, de modo que una indisponibilidad de Gemini no afecte catálogo ni reservas.
3. **Tiempo de 13 semanas con 5 integrantes** (SRS §2.4.2): fue la principal restricción en contra de la alternativa seleccionada y la que motivó acotar el alcance del prototipo y adoptar las mitigaciones de la Sección 4.4.

### 4.4 Equilibrio entre costo, tiempo y atributos de calidad

* **Calidad priorizada:** Se privilegian escalabilidad, disponibilidad y mantenibilidad porque son atributos *Must*/*Should* verificables (ESC-01, ESC-02, ESC-05, ESC-08) y difíciles de incorporar después en un monolito.
* **Tiempo controlado:**
  * Meta de prototipo acotada a $\ge 60\%$ de los casos de uso *Must* (SRS, Apéndice D, Fase 4).
  * Un solo lenguaje y framework (Python + FastAPI), una plantilla base común para los microservicios y un `docker-compose` de desarrollo local antes del despliegue en k3s (mitigación de R-01).
  * Propiedad de cada componente por un integrante (SRS Apéndice C), lo que permite desarrollo en paralelo con sprints de 2 semanas (mitigación de R-05).
* **Costo controlado:**
  * En el prototipo, las bases de datos de cada servicio se alojan como bases lógicas separadas dentro de una misma instancia de PostgreSQL, conservando el principio *Database-per-Service* sin multiplicar servidores.
  * Despliegue en un clúster k3s de un solo nodo en el Escenario A (USD 6.900), que ya ofrece escalado automático y actualizaciones sin interrupción; el Escenario B agrega nodos para alta disponibilidad (ADR-005).
* **Seguridad compensada:** La mayor superficie de ataque se mitiga con validación perimetral de JWT en el API Gateway, políticas de red de Kubernetes que solo permiten el tráfico previsto, cifrado Argon2id y bitácora de auditoría inmutable (RNF-04, RNF-10, R-02).
