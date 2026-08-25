# Adendo al Documento de Requerimientos — v0.2 (propuesta de cierre)

**Proyecto:** Plataforma Digital para la Gestión Integrada y Sostenible del Turismo en Santa Marta

**Basado en:** Documento de Requerimientos Iniciales v0.1 

**Propósito de este documento:** proponer respuestas realistas a las decisiones pendientes, para que el equipo las revise, ajuste y apruebe en la reunión de cierre.


---

## A. Decisiones pendientes del equipo

### A.1 Arquitectura

| # | Decisión a tomar | Decisión final | Justificación |
|---|---|---|---|
| 1 | Persistencia única vs. políglota | **Propuesta — ajustable:** políglota moderada — PostgreSQL como base relacional para los servicios con datos estructurados y transaccionales (Seguridad/usuarios, y el futuro núcleo de catálogo/reservas si se confirma como servicio aparte); MongoDB para el módulo de **Anotaciones** (comentarios, calificaciones, estados de moderación — datos semiestructurados que cambian de forma con el tiempo); Redis como caché (sesiones, resultados de consulta frecuentes, rate limiting). | Encaja con RNF-03 (interoperabilidad) y RNF-05 (mantenibilidad): cada microservicio es dueño de su propia base, evitando acoplamiento por base de datos compartida. Mongo es más natural para comentarios/opiniones porque su estructura varía (respuestas anidadas, adjuntos, banderas de moderación) sin forzar migraciones constantes. |
| 2 | Estilo de comunicación entre componentes | **Ya definida por el equipo: híbrida.** REST síncrono para operaciones que el usuario espera con respuesta inmediata (login, consultas de catálogo/disponibilidad, perfil). Mensajería asíncrona (cola/eventos) para lo que no requiere respuesta inmediata y beneficia el desacople: envío de eventos al servicio de IA para generar recomendaciones, notificaciones, y registro de auditoría/bitácora. | Un servicio de IA acoplado por REST síncrono obligaría al resto del sistema a esperar el tiempo de inferencia; con eventos, el resultado se entrega cuando está listo sin bloquear al usuario. Cumple el requisito explícito de RF (IA desacoplada del núcleo). |
| 3 | Estilo arquitectónico base | **Ya definida por el equipo: microservicios**, organizados inicialmente en 4 módulos: **Inicio de sesión / Autenticación**, **IA**, **Anotaciones (reseñas y calificaciones)** y **Seguridad**. | Permite escalar de forma independiente el servicio más costoso computacionalmente (IA) sin sobredimensionar el resto, y separa responsabilidades de forma clara entre equipo. **Ver advertencia abajo.** |
| 4 | Proveedor(es) cloud | **Propuesta — ajustable:** AWS, aprovechando el free-tier académico (AWS Educate / GitHub Student Pack), usando servicios gestionados básicos (RDS para Postgres, un servicio gestionado de Mongo tipo Atlas fuera de AWS si no se quiere pagar DocumentDB, ElastiCache o Redis en contenedor, SQS/SNS para mensajería, ECS/Fargate para desplegar los microservicios sin administrar servidores). | Reduce curva de aprendizaje si el equipo ya tiene experiencia previa con AWS (SQS, IAM, RDS); el free-tier ayuda a mantenerse dentro del presupuesto. Es una preferencia, no una obligación — GCP o Azure también cumplirían si el equipo tiene créditos académicos allí. |

> **Nota importante para el equipo:** los 4 módulos mencionados (Login, IA, Anotaciones, Seguridad) no cubren directamente los casos de uso de **catálogo/búsqueda (UC7-UC10), reservas (UC11-UC13, UC19-UC20)** ni los **indicadores para la Entidad de gestión (UC23-UC25)**. O bien falta un quinto módulo tipo "Catálogo y Reservas" / "Gestión Turística", o esos casos de uso quedan repartidos entre los 4 módulos existentes (por ejemplo, dentro de Seguridad o como parte de un backend compartido). Esto **debe cerrarse antes de la Fase 2**, porque cambia los límites de cada microservicio y el modelo de datos.

### A.2 Metodología y gestión de proyecto

| # | Decisión a tomar | Decisión final | Justificación |
|---|---|---|---|
| 1 | Metodología de desarrollo | **Propuesta — ajustable:** Scrum adaptado (no Scrum puro), con reuniones de seguimiento semanales en vez de diarias, dado que es un equipo de estudiantes con otras materias en paralelo. | Da estructura de sprints con entregables verificables (relevante para sustentaciones parciales del curso), sin exigir la disciplina de daily standups que rara vez se sostiene en proyectos académicos. |
| 2 | Herramienta de gestión | **Propuesta — ajustable:** GitHub Projects (tablero Kanban ligado directamente a los repos y *issues* de cada microservicio), gratuito con GitHub Education. | Evita mantener dos herramientas separadas (código + gestión); todo el equipo ya usa GitHub para el código. |
| 3 | Duración de iteraciones/sprints | **Propuesta — ajustable:** sprints de 2 semanas. | Encaja con el cronograma ajustado de 6 meses (~12 sprints), suficiente margen para entregar valor visible sin generar sobrecarga de ceremonias. |

### A.3 Alcance de la IA

| # | Pregunta | Decisión final | Justificación |
|---|---|---|---|
| 1 | ¿Cuál función de IA se implementa en el prototipo? | **Propuesta — ajustable:** recomendación personalizada de atractivos/actividades (RF-06) como función principal del módulo de IA. Clasificación de opiniones se sugiere *no* como módulo de IA independiente, sino como una regla simple o modelo liviano embebido en el propio servicio de **Anotaciones** (p. ej. para pre-marcar comentarios ofensivos antes de moderación humana), para no duplicar responsabilidades entre dos módulos. | La recomendación es la función con mayor valor percibido por el turista (stakeholder principal) y es la que mejor demuestra el desacople arquitectónico exigido por el curso. Un chatbot o predicción de demanda son más costosos de construir bien en el tiempo disponible. |
| 2 | ¿Cómo se garantiza el desacople del núcleo? | **Propuesta — ajustable:** microservicio propio de IA, que recibe solicitudes vía cola de eventos (no REST síncrono) y publica el resultado (recomendación) para que el módulo correspondiente lo consuma. Si el modelo se entrena/sirve por fuera (p. ej. un notebook empaquetado como servicio Python separado del resto del stack, que puede estar en Java/Node), mejor aún: aísla el runtime de ML del resto de la arquitectura. | Coherente con la decisión de comunicación híbrida ya tomada, y con RNF-05 (mantenibilidad: se puede reemplazar o reentrenar el modelo sin tocar los demás servicios). |
| 3 | ¿Con qué datos se entrena o alimenta? | **Propuesta — ajustable:** datos sintéticos/mockeados generados por el equipo para el entrenamiento inicial (perfiles de turista ficticios, historial de "visitas" simulado), complementados si el tiempo alcanza con datos públicos abiertos de turismo en Colombia (p. ej. portales de datos abiertos del Ministerio de Comercio, Industria y Turismo o de la Alcaldía de Santa Marta, si existen y son accesibles). | Es poco realista conseguir datos reales de turistas para un prototipo académico; usar datos sintéticos es una práctica aceptada y debe documentarse explícitamente como limitación del prototipo (relevante para la sección de conclusiones/validación). |

### A.4 Presupuesto (USD 20.000 tope)

| Rubro | Estimado (USD) | Justificación |
|---|---|---|
| Infraestructura cloud (cómputo, storage, BD) | **4.500** | Estimado para ~6 meses considerando que buena parte queda cubierta por el free-tier de AWS Educate, pero dejando margen para lo que exceda el free-tier en picos de prueba/demo. |
| Servicios de terceros (mapas, notificaciones) | **1.200** | Se propone usar OpenStreetMap (gratuito) en lugar de Google Maps para el mapa de zonas (UC16), lo que reduce este rubro; se reserva presupuesto para un servicio de notificaciones por correo de bajo costo (p. ej. AWS SES) si se decide incluir UC36. |
| Herramientas de desarrollo/colaboración | **300** | La mayoría de herramientas (GitHub, Figma, Postman) tiene planes gratuitos suficientes para un equipo de 5; este rubro cubre imprevistos menores (p. ej. algún plugin o licencia puntual). |
| Contingencia (15%) | **900** | Sobre el subtotal de 6.000, siguiendo el rango sugerido en el documento original. |
| **Total** | **≈ 6.900** | Queda muy por debajo del tope de USD 20.000. Esto es intencional: al ser un prototipo académico apoyado en free-tier y software libre, no tiene sentido presupuestar como si fuera producción comercial. Vale la pena declarar explícitamente esta holgura en el documento, para que quede claro que no se "ejecuta" todo el presupuesto disponible. |

### A.5 Cronograma realista

| Fase | Entregable | Duración ajustada |
|---|---|---|
| 1. Requisitos y contexto | Documento de Requerimientos completo (congelado en v1.0) | **Semanas 1–2 (24 ago – 6 sep)** |
| 2. Comparación de arquitecturas | Documento de Comparación y Selección | **Semanas 3–4 (7–20 sep)** |
| 3. Diseño arquitectónico | Documento de Diseño Final | **Semanas 5–6 (21 sep – 4 oct)** |
| 4. Implementación del prototipo | Código + despliegue — con solo 6 semanas reales de implementación (frente a las 12 del plan de 6 meses), se propone bajar la meta a **40% de los casos de uso priorizados como "Must have"** Código + despliegue — la meta es 60% de los casos de uso priorizados como "Must have" en el MoSCoW (A.7), sin excepción (requisito del curso). Con solo 6 semanas reales de implementación frente a las 12 del plan de 6 meses, cumplir ese 60% exige que el MoSCoW de A.7 quede lo más ajustado posible desde ya: mientras menos casos de uso queden marcados como "Must have", más realista es llegar al 60% de ese subconjunto en el tiempo disponible. El recorte de alcance debe hacerse en la priorización (A.7), no en la meta de cobertura. | **Semanas 7–12 (5 oct – 15 nov)** |
| 5. Validación y cierre | Documento final + evidencia de validación + sustentación | **Semanas 13–14 (16–29 nov)** |

> La Fase 1 ya está en curso (este mismo documento), así que las 2 semanas asignadas son sobre todo para cerrar los pendientes de la sección A y B, no para empezar desde cero. Si el equipo necesita más tiempo ahí, ese tiempo sale directamente de la Fase 4 — con 14 semanas totales ya no hay colchón real, así que cualquier atraso en requisitos o diseño debe recortar alcance de implementación, no correr todo el calendario hacia adelante.

### A.6 Modelo de negocio / monetización

| Pregunta | Decisión final |
|---|---|
| ¿Quién financia/paga la operación del sistema? | **Propuesta — ajustable:** la Entidad de gestión del destino (p. ej. Secretaría de Turismo), como un servicio público digital, no como negocio con fines de lucro. |
| ¿Comisión, membresía, o gratuito? | **Gratuito** para turistas y prestadores pequeños/medianos. Esto es coherente con RF-08 ("incorporar pequeños y medianos prestadores con recursos tecnológicos limitados") y con el rol de la Entidad como stakeholder institucional. |
| ¿Afecta esto al alcance del prototipo? | **Sí, y de forma favorable para el alcance:** al no haber pagos reales dentro de la plataforma, **UC34 (Procesar pago) y UC35 (Gestionar métodos de pago) quedan explícitamente fuera de alcance** del prototipo. UC11 (Reservar) se implementa como una "solicitud de reserva" que el prestador confirma; el pago, si existe, se resuelve fuera del sistema (directamente con el prestador). Esto simplifica considerablemente el alcance y reduce riesgo de seguridad (no se maneja información de tarjetas). |

### A.7 Priorización formal (MoSCoW)

Columnas propuestas: `ID | Requerimiento | MoSCoW | Stakeholder origen | Objetivo relacionado | Criterio de verificación`

Ejemplo de cómo aplicarlo (el equipo debe completar el resto de RF/RNF siguiendo el mismo patrón):

| ID | Requerimiento | MoSCoW | Stakeholder origen | Objetivo relacionado | Criterio de verificación |
|---|---|---|---|---|---|
| RF-01 | Consultar atractivos, actividades y eventos | Must | Turista | Reducir dispersión de información | El turista puede ver una lista de atractivos sin autenticarse |
| RF-02 | Buscar y filtrar servicios | Must | Turista | Facilitar selección según preferencias | Los filtros por categoría, ubicación y precio devuelven resultados correctos |
| RF-04 | Reservar actividad o servicio | Must | Turista | Habilitar el flujo central del sistema | Una reserva creada aparece en el historial del turista y en el panel del prestador |
| RF-05 | Registrar y gestionar oferta de servicios | Must | Prestador | Dar visibilidad a prestadores | Un prestador autenticado puede crear/editar su oferta |
| RF-06 | Generar recomendaciones personalizadas | Should | Turista | Diferenciador del prototipo (módulo IA) | El sistema entrega al menos una recomendación basada en preferencias declaradas |
| RF-09 | Gestionar usuarios, roles y control de acceso | Must | Admin | Cumplir RNF-04 (seguridad) | Un usuario sin rol adecuado recibe error 403 al intentar una acción restringida |
| RNF-01 | Disponibilidad ≥99% | Should | Proveedor cloud / Admin | Confiabilidad del servicio | Medible solo en ambiente de despliegue continuo — se documenta como meta, no se certifica en el prototipo académico |
| RNF-04 | Autenticación, autorización, protección de datos (Ley 1581) | Must | Ente regulador | Cumplimiento normativo | Existe consentimiento explícito registrado (UC6) antes de crear cuenta |

---

## B. Vacíos identificados — recomendación de inclusión

### B.1 Casos de uso posiblemente faltantes

| Propuesto | Recomendación |
|---|---|
| UC34 Procesar pago de reserva | **Fuera de alcance** (ver A.6: modelo gratuito, sin pasarela de pago real) |
| UC35 Gestionar métodos de pago | **Fuera de alcance** (misma razón) |
| UC36 Recibir notificaciones | **Incluir versión básica** (solo confirmación de reserva por correo) — encaja con el módulo de Seguridad/Autenticación existente y no requiere un módulo nuevo |
| UC37 Cargar documentos de verificación | **Incluir** — encaja directamente con el módulo de **Seguridad** ya planeado (verificación de prestadores, UC28) |
| UC38 Exportar reportes de planificación | **Could have** — útil para la Entidad pero no crítico para demostrar la arquitectura; dejar para si sobra tiempo en Fase 4 |
| UC39 Configurar alertas automáticas de capacidad de carga | **Fuera de alcance en esta iteración** — depende de datos reales de aforo que el equipo no tendrá; documentar como extensión futura del módulo de IA |

### B.2 Actores externos posiblemente faltantes

- **Pasarela de pagos:** no aplica, dado el modelo gratuito (A.6).
- **Proveedor de mapas/geolocalización:** sí es necesario para UC16. Se recomienda **OpenStreetMap** en vez de Google Maps, por costo (gratuito) y porque el volumen de uso de un prototipo académico no justifica una licencia comercial.
- **Servicio de notificaciones:** sí, si se incluye UC36 básico. Se recomienda un servicio de correo de bajo costo/gratuito (AWS SES en capa gratuita, o un servicio SMTP gratuito tipo Mailtrap para pruebas).

### B.3 Requerimientos no funcionales posiblemente faltantes

| Atributo | Recomendación |
|---|---|
| Recuperación ante desastres | **Should have.** Redactar como: "El sistema debe contar con respaldo automático periódico de cada base de datos y un procedimiento documentado de restauración." Prioridad razonable dado el presupuesto/tiempo — no se exige un plan de continuidad completo, solo respaldo y restauración probada al menos una vez. |
| Auditoría | **Must have.** Ya está parcialmente cubierto por UC33 (Consultar bitácora de auditoría) del módulo de Seguridad; formalizarlo como RNF explícito para que quede trazado en la tabla de requerimientos, no solo como caso de uso. |
| Usabilidad | **Should have.** Se propone un criterio verificable inicial: completar una reserva en máximo 4 pasos (buscar → ver detalle → confirmar → recibir confirmación), ajustable tras pruebas de usuario reales si el tiempo lo permite. |
| Portabilidad | **Won't have (esta iteración).** Al fijar AWS como proveedor preferido (A.1.4) y usar servicios gestionados propios de AWS, garantizar portabilidad a dos nubes distintas sin cambios estructurales es poco realista en 6 meses con 5 personas. Documentar como decisión consciente, no como omisión. |

### B.4 Otros vacíos

- **Matriz de riesgos:** no existe todavía — se recomienda crearla como documento corto aparte (riesgos técnicos: p. ej. "el equipo no tiene experiencia previa desplegando microservicios" → mitigación: empezar con Docker Compose local antes de ECS; riesgos de alcance: cambiar de monolito a microservicios a mitad de camino; riesgos de equipo: disponibilidad desigual entre integrantes por otras materias).
- **Modelo de datos preliminar:** entidades núcleo sugeridas: `Turista`, `Prestador`, `Usuario/Rol` (Seguridad), `Servicio/Atractivo` (pendiente de dónde vive — ver advertencia en A.1), `Reserva`, `Comentario/Anotación`, `Zona`, `Recomendación` (registro de salidas del módulo de IA, útil para explicabilidad — RNF-08).
- **Matriz de trazabilidad RF/RNF ↔ stakeholder ↔ objetivo:** se genera naturalmente al completar la tabla de A.7 con todas las filas — no requiere trabajo adicional si el MoSCoW se llena con las columnas propuestas.
- **Restricción de edad/consentimiento:** se recomienda **restringir el registro a mayores de 18 años**, y documentarlo explícitamente como fuera de alcance el soporte a turistas menores de edad sin acompañante. Esto simplifica el cumplimiento de la Ley 1581 de 2012 (evita el régimen especial de tratamiento de datos de menores) y es razonable para un prototipo académico.
- **Definición cuantitativa de "temporada alta":** se recomienda buscar cifras públicas (Cotelco, Procolombia, o la propia Alcaldía de Santa Marta) sobre ocupación hotelera por temporada, para respaldar el problema con datos reales antes de congelar v1.0. Esto es investigación puntual, no una decisión de arquitectura — se puede resolver en paralelo sin bloquear el resto.
- **Mockups/wireframes:** no existen. Se recomienda producir wireframes de baja fidelidad (Figma, gratuito) para las pantallas clave — login, catálogo/búsqueda, detalle de reserva, panel de prestador, panel de entidad — antes de cerrar la Fase 3 (Diseño arquitectónico), porque ayudan a validar el modelo de datos y los límites de cada microservicio.

---


