# Documento de Requerimientos Iniciales

**Proyecto:** Plataforma Digital para la Gestión Integrada y Sostenible del Turismo en Santa Marta

**Curso:** Arquitectura de Software — Experiencia Final de Diseño 

**Programa:** Ingeniería de Sistemas — Unimagdalena

**Versión:** 0.1 

**Fecha:** Agosto 2026

---

## 1. Contexto del Problema

Santa Marta es uno de los principales destinos turísticos del Caribe colombiano, y recibe anualmente un alto volumen de visitantes nacionales e internacionales atraídos por sus playas, el Centro Histórico, el Parque Nacional Natural Tayrona, la Sierra Nevada de Santa Marta y su oferta de turismo cultural, ecológico y de naturaleza.

Este crecimiento turístico representa una oportunidad de desarrollo económico y social, pero también genera retos relacionados con la gestión, integración y disponibilidad oportuna de información para la toma de decisiones de turistas, prestadores de servicios y actores responsables de la gestión del destino.

### 1.1 Problemáticas identificadas

- Concentración excesiva de turistas en ciertos atractivos y zonas durante temporadas de alta demanda.
- Baja integración entre la oferta de hoteles, restaurantes, operadores turísticos, actividades y atractivos.
- Poca visibilidad de pequeños y medianos prestadores de servicios turísticos.
- Información dispersa y heterogénea sobre disponibilidad, horarios, eventos y condiciones de los atractivos.
- Ausencia de mecanismos integrados de consulta y gestión de disponibilidad de servicios.
- Dificultad de los visitantes para seleccionar actividades según sus preferencias, restricciones y disponibilidad.
- Falta de indicadores para que entidades y operadores analicen el comportamiento de la demanda.
- Dificultad para mantener un servicio confiable durante períodos de alta concurrencia (picos de consulta, reserva y acceso).

### 1.2 Propuesta de solución

Se propone el diseño y desarrollo de un **prototipo funcional de una plataforma digital** para la gestión inteligente de información y servicios turísticos de Santa Marta. El núcleo del proyecto es la **arquitectura de software** capaz de integrar diversas fuentes de información y soportar los procesos de consulta, recomendación, disponibilidad y reserva de servicios turísticos, considerando escalabilidad, disponibilidad, interoperabilidad, seguridad, mantenibilidad, rendimiento y capacidad de evolución.

La inteligencia artificial **no es el objetivo principal**, sino un servicio complementario desacoplado del resto de la arquitectura sin embargo es un requisito funcional del proyecto a trabajar. Nuestro equipo busca desarrollar una forma de integrar la IA en el proyecto, (NO decidido) como ejemplo estan las siguientes:

- Recomendación personalizada de atractivos y actividades.
- Clasificación automática de opiniones/comentarios de visitantes.
- Predicción básica de ocupación o demanda.
- Chatbot turístico basado en información controlada.

---

## 2. Identificación de Stakeholders

La identificación y clasificación de los interesados (*stakeholders*) permite comprender sus necesidades, delimitar los límites del sistema y asegurar la trazabilidad hacia los requerimientos funcionales, atributos de calidad y restricciones del proyecto (conforme a la norma ISO/IEC/IEEE 29148:2018).

| Tipo | Stakeholder | Rol frente al sistema | Intereses / Necesidades principales |
|---|---|---|---|
| **Actor Directo** | **Turista nacional / internacional** | Usuario final — consulta, compara y reserva servicios. | • Información confiable y actualizada.<br>• Recomendaciones personalizadas.<br>• Proceso de reserva simple y seguro.<br>• Disponibilidad en español e inglés.<br>• Accesibilidad digital. |
| **Actor Directo** | **Prestador de servicios turísticos** *(hoteles, restaurantes, operadores, guías)* | Proveedor de información y disponibilidad. | • Visibilidad equitativa en la plataforma.<br>• Gestión sencilla de su oferta, tarifas y disponibilidad.<br>• Protección de su información comercial sensible. |
| **Actor Directo** | **Entidad de gestión del destino** *(Secretarías de Turismo, Cámara de Comercio, entes territoriales)* | Usuario institucional — planificación y monitoreo. | • Indicadores de demanda, ocupación y tendencias.<br>• Datos para diseño de políticas de turismo sostenible.<br>• Control y monitoreo de capacidad de carga en zonas sensibles. |
| **Actor Directo** | **Administradores de la plataforma** | Gestión operativa y técnica del sistema. | • Gestión integral de usuarios, roles y permisos.<br>• Seguridad, trazabilidad y bitácoras de auditoría.<br>• Monitoreo de desempeño y alta disponibilidad del servicio. |
| **Stakeholder Indirecto / Normativo** | **Ente regulador** *(Protección de datos personales / SIC)* | Stakeholder normativo — no interactúa directamente. | • Cumplimiento estricto de la Ley Estatutaria 1581 de 2012.<br>• Tratamiento transparente y seguro de datos personales (*Habeas Data*). |
| **Stakeholder Indirecto / Proveedor** | **Proveedor de infraestructura / servicios cloud** | Soporte técnico de despliegue, hosting y operación. | • Garantizar disponibilidad mínima del sistema (≥ 99%).<br>• Escalabilidad elástica en picos de temporada.<br>• Operación contenida dentro del presupuesto límite definido (USD 20.000). |

> **Nota**: Un actor directo se refiere a que manipula directamente el sistema y un actor indirecto se refiere a que no manipula directamente el sistema pero tiene intereses en él o recibe algún beneficio del mismo sin manipular directamente el sistema.
---

## 3. Diagramas de Casos de Uso

### 3.1 Actores identificados

- **Turista** (`Tur`): Usuario final (visitante nacional o internacional) que consulta, reserva y califica servicios turísticos.
- **Entidad de Gestión del Destino** (`Entidad`): Secretarías de turismo, entidades territoriales y organismos de planificación interesados en indicadores de demanda, capacidad de carga y alertas.
- **Prestador de Servicios Turísticos** (`Prest`): Hoteles, restaurantes, operadores turísticos y guías que publican y gestionan su oferta de servicios, disponibilidad y tarifas.
- **Administrador de la Plataforma** (`Admin`): Encargado del mantenimiento técnico, gestión de usuarios/roles, moderación de contenidos, seguridad, auditoría e integraciones externas.

### 3.2 Casos de Uso Identificados

| Código | Caso de Uso | Actor(es) Principal(es) | Relaciones (`include` / `extend`) |
|---|---|---|---|
| **UC1** | Registrarse | Turista, Prestador | `<<include>>` UC6 |
| **UC2** | Iniciar sesión | Turista, Entidad, Prestador, Admin | Punto de acceso autenticado |
| **UC3** | Recuperar / cambiar contraseña | Turista | - |
| **UC4** | Gestionar perfil propio | Turista | - |
| **UC5** | Cambiar idioma (Español / Inglés) | Turista, Entidad | - |
| **UC6** | Aceptar tratamiento de datos personales | Sistema / Transversal | Incluido en UC1 |
| **UC7** | Consultar atractivos, actividades y eventos | Turista | Incluido en UC8, UC9 |
| **UC8** | Buscar y filtrar servicios según preferencias | Turista | `<<include>>` UC7 |
| **UC9** | Consultar detalle de sitio (comida, costo, habitaciones, promociones) | Turista | `<<include>>` UC7 |
| **UC10** | Consultar disponibilidad de servicio/actividad | Turista | Incluido en UC11 |
| **UC11** | Reservar actividad o servicio | Turista | `<<include>>` UC2, `<<include>>` UC10 |
| **UC12** | Cancelar / modificar reserva | Turista | `<<include>>` UC13 |
| **UC13** | Consultar historial de reservas | Turista | Extendido por UC14, Incluido en UC12 |
| **UC14** | Recibir recomendaciones personalizadas | Turista | `<<extend>>` UC13 |
| **UC15** | Calificar / comentar experiencia | Turista | Extendido por UC29 |
| **UC16** | Consultar mapa de zonas y capacidad | Turista | - |
| **UC17** | Registrar / publicar servicio | Prestador | `<<include>>` UC2, `<<include>>` UC28 |
| **UC18** | Editar información de su servicio | Prestador | - |
| **UC19** | Gestionar disponibilidad y precios | Prestador | `<<include>>` UC2 |
| **UC20** | Gestionar reservas recibidas | Prestador | - |
| **UC21** | Responder comentarios de visitantes | Prestador | - |
| **UC22** | Consultar indicadores de su oferta | Prestador | - |
| **UC23** | Consultar indicadores de demanda y ocupación | Entidad | Incluido en UC25 |
| **UC24** | Consultar capacidad de carga de zonas turísticas | Entidad | Incluido en UC25 |
| **UC25** | Generar reportes de planificación turística | Entidad | `<<include>>` UC23, `<<include>>` UC24 |
| **UC26** | Publicar alertas o recomendaciones oficiales | Entidad | - |
| **UC27** | Gestionar usuarios y roles | Admin | - |
| **UC28** | Aprobar / verificar prestadores nuevos | Admin | Incluido en UC17 |
| **UC29** | Moderar opiniones y contenido publicado | Admin | `<<extend>>` UC15 |
| **UC30** | Configurar integración de fuentes externas | Admin | - |
| **UC31** | Monitorear disponibilidad y desempeño del sistema | Admin | - |
| **UC32** | Gestionar seguridad y control de acceso | Admin | - |
| **UC33** | Consultar bitácora de auditoría | Admin | - |

### 3.3 Diagrama de Casos de Uso

**Visualización del Diagrama:**

![Diagrama de Casos de Uso - Plataforma Digital de Turismo Santa Marta](./CasosDeUso_PlataformaTurismoSantaMarta.svg)

> *Nota: También disponible en formato PNG de alta resolución: [CasosDeUso_PlataformaTurismoSantaMarta.png](./CasosDeUso_PlataformaTurismoSantaMarta.png)*

<details>
<summary><b>Haz clic aquí para ver el código fuente PlantUML</b></summary>

```plantuml
@startuml CasosDeUso_PlataformaTurismoSantaMarta

skinparam dpi 300
skinparam packageStyle rectangle
skinparam actorStyle awesome
skinparam ranksep 15
skinparam nodesep 10
hide stereotype

actor Turista as Tur
actor "Entidad de Gestión\ndel Destino" as Entidad

actor "Prestador de\nServicios Turísticos" as Prest
actor "Administrador de\nla Plataforma" as Admin

rectangle "Plataforma Digital de Turismo - Santa Marta" {

  ' ===== COLUMNA IZQUIERDA (Turista + Entidad) =====
  usecase "Registrarse" as UC1
  usecase "Iniciar sesión" as UC2
  usecase "Recuperar / cambiar contraseña" as UC3
  usecase "Gestionar perfil propio" as UC4
  usecase "Cambiar idioma\n(Español / Inglés)" as UC5
  usecase "Aceptar tratamiento\nde datos personales" as UC6
  usecase "Consultar atractivos,\nactividades y eventos" as UC7
  usecase "Buscar y filtrar servicios\nsegún preferencias" as UC8
  usecase "Consultar detalle de sitio\n(comida, costo, habitaciones,\npromociones)" as UC9
  usecase "Consultar disponibilidad\nde servicio/actividad" as UC10
  usecase "Reservar actividad o servicio" as UC11
  usecase "Cancelar / modificar reserva" as UC12
  usecase "Consultar historial\nde reservas" as UC13
  usecase "Recibir recomendaciones\npersonalizadas" as UC14
  usecase "Calificar / comentar\nexperiencia" as UC15
  usecase "Consultar mapa de\nzonas y capacidad" as UC16
  usecase "Consultar indicadores\nde demanda y ocupación" as UC23
  usecase "Consultar capacidad de carga\nde zonas turísticas" as UC24
  usecase "Generar reportes de\nplanificación turística" as UC25
  usecase "Publicar alertas o\nrecomendaciones oficiales" as UC26

  ' Encadenado invisible para forzar apilado vertical (columna izquierda)
  UC1 -[hidden]-> UC2
  UC2 -[hidden]-> UC3
  UC3 -[hidden]-> UC4
  UC4 -[hidden]-> UC5
  UC5 -[hidden]-> UC6
  UC6 -[hidden]-> UC7
  UC7 -[hidden]-> UC8
  UC8 -[hidden]-> UC9
  UC9 -[hidden]-> UC10
  UC10 -[hidden]-> UC11
  UC11 -[hidden]-> UC12
  UC12 -[hidden]-> UC13
  UC13 -[hidden]-> UC14
  UC14 -[hidden]-> UC15
  UC15 -[hidden]-> UC16
  UC16 -[hidden]-> UC23
  UC23 -[hidden]-> UC24
  UC24 -[hidden]-> UC25
  UC25 -[hidden]-> UC26

  ' ===== COLUMNA DERECHA (Prestador + Administrador) =====
  usecase "Registrar / publicar servicio" as UC17
  usecase "Editar información\nde su servicio" as UC18
  usecase "Gestionar disponibilidad\ny precios" as UC19
  usecase "Gestionar reservas recibidas" as UC20
  usecase "Responder comentarios\nde visitantes" as UC21
  usecase "Consultar indicadores\nde su oferta" as UC22
  usecase "Gestionar usuarios y roles" as UC27
  usecase "Aprobar / verificar\nprestadores nuevos" as UC28
  usecase "Moderar opiniones\ny contenido publicado" as UC29
  usecase "Configurar integración\nde fuentes externas" as UC30
  usecase "Monitorear disponibilidad\ny desempeño del sistema" as UC31
  usecase "Gestionar seguridad y\ncontrol de acceso" as UC32
  usecase "Consultar bitácora\nde auditoría" as UC33

  ' Encadenado invisible para forzar apilado vertical (columna derecha)
  UC17 -[hidden]-> UC18
  UC18 -[hidden]-> UC19
  UC19 -[hidden]-> UC20
  UC20 -[hidden]-> UC21
  UC21 -[hidden]-> UC22
  UC22 -[hidden]-> UC27
  UC27 -[hidden]-> UC28
  UC28 -[hidden]-> UC29
  UC29 -[hidden]-> UC30
  UC30 -[hidden]-> UC31
  UC31 -[hidden]-> UC32
  UC32 -[hidden]-> UC33

  ' Alinea el inicio de ambas columnas en la misma fila
  UC1 -[hidden]-> UC17
}

' ----- Relaciones: Turista -----
Tur --> UC1
Tur --> UC2
Tur --> UC3
Tur --> UC4
Tur --> UC5
Tur --> UC7
Tur --> UC8
Tur --> UC9
Tur --> UC10
Tur --> UC11
Tur --> UC12
Tur --> UC13
Tur --> UC14
Tur --> UC15
Tur --> UC16

' ----- Relaciones: Entidad de Gestión -----
Entidad --> UC2
Entidad --> UC5
Entidad --> UC23
Entidad --> UC24
Entidad --> UC25
Entidad --> UC26

' ----- Relaciones: Prestador -----
UC17 <-- Prest
UC18 <-- Prest
UC19 <-- Prest
UC20 <-- Prest
UC21 <-- Prest
UC22 <-- Prest
UC2 <-- Prest
UC1 <-- Prest

' ----- Relaciones: Administrador -----
UC27 <-- Admin
UC28 <-- Admin
UC29 <-- Admin
UC30 <-- Admin
UC31 <-- Admin
UC32 <-- Admin
UC33 <-- Admin
UC2 <-- Admin

' ----- Include / Extend -----
UC1 .> UC6   : <<include>>
UC11 .> UC2  : <<include>>
UC11 .> UC10 : <<include>>
UC12 .> UC13 : <<include>>
UC9 .> UC7   : <<include>>
UC8 .> UC7   : <<include>>
UC14 .> UC13 : <<extend>>
UC17 .> UC2  : <<include>>
UC17 .> UC28 : <<include>>
UC19 .> UC2  : <<include>>
UC29 .> UC15 : <<extend>>
UC25 .> UC23 : <<include>>
UC25 .> UC24 : <<include>>

@enduml
```

</details>

---

## 4. Especificación de Requerimientos (base ISO/IEC/IEEE 29148:2018)

> Estructura preliminar. Debe completarse siguiendo el estándar ISO/IEC/IEEE 29148:2018 para especificación de requisitos (incluye trazabilidad, criterios de verificación y priorización).

### 4.1 Requerimientos funcionales (borrador)

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-01 | El sistema debe permitir consultar atractivos, actividades y eventos turísticos de Santa Marta. | Alta |
| RF-02 | El sistema debe permitir buscar y filtrar servicios turísticos por categoría, ubicación, precio y disponibilidad. | Alta |
| RF-03 | El sistema debe permitir consultar la disponibilidad de un servicio o actividad en tiempo (razonablemente) actualizado. | Alta |
| RF-04 | El sistema debe permitir a un turista reservar una actividad o servicio. | Alta |
| RF-05 | El sistema debe permitir a un prestador registrar y gestionar su oferta de servicios. | Alta |
| RF-06 | El sistema debe generar recomendaciones de atractivos/actividades según preferencias del visitante (funcionalidad de IA seleccionada). | Media |
| RF-07 | El sistema debe generar indicadores/reportes de demanda para apoyar la planificación turística. | Media |
| RF-08 | El sistema debe permitir la incorporación de pequeños y medianos prestadores con recursos tecnológicos limitados. | Media |
| RF-09 | El sistema debe gestionar usuarios, roles y control de acceso. | Alta |
| RF-10 | El sistema debe estar disponible en español e inglés. | Media |

### 4.2 Requerimientos no funcionales / atributos de calidad (borrador — ver sección 6 para escenarios medibles)

| ID | Atributo de calidad | Requerimiento |
|---|---|---|
| RNF-01 | Disponibilidad | El sistema debe tener una disponibilidad mínima del 99%. |
| RNF-02 | Escalabilidad | La arquitectura debe soportar picos de demanda en temporada alta sin degradación significativa del servicio. |
| RNF-03 | Interoperabilidad | El sistema debe integrar múltiples fuentes de información con distintas estructuras de datos. |
| RNF-04 | Seguridad | El sistema debe implementar autenticación, autorización y protección de datos personales (Ley 1581 de 2012). |
| RNF-05 | Mantenibilidad | La arquitectura debe permitir incorporar nuevos servicios/operadores sin modificaciones significativas al núcleo. |
| RNF-06 | Rendimiento | El sistema debe responder consultas dentro de tiempos aceptables incluso en alta concurrencia. |
| RNF-07 | Accesibilidad | Las interfaces deben ser accesibles para usuarios con distintos niveles de alfabetización digital y para personas con discapacidad. |
| RNF-08 | Transparencia (ético) | Las recomendaciones generadas por IA deben ser explicables al usuario. |

**Pendiente:** para cada requerimiento, agregar criterios de verificación, fuente, prioridad formal y trazabilidad hacia los objetivos y stakeholders (según ISO/IEC/IEEE 29148:2018).

---

## 5. Plan, Cronograma y Presupuesto (borrador inicial)

### 5.1 Condiciones generales del proyecto

- **Equipo:** 5 estudiantes, con roles asignados (Líder técnico/Arquitecto, Analista de requisitos, Diseñador de datos, Desarrollador principal, Responsable de validación y calidad).
- **Duración máxima:** 6 meses.
- **Presupuesto:** Máximo USD 20.000 para infraestructura del proyecto.
- **Paradigma:** Orientado a objetos.
- **Metodología:** Por definir y justificar por el equipo.

### 5.2 Cronograma preliminar (a ajustar por el equipo)

| Fase | Entregable | Duración estimada |
|---|---|---|
| 1. Requisitos y contexto | Documento de Requerimientos (este documento, completo) | Mes 1 |
| 2. Comparación de arquitecturas | Documento de Comparación y Selección de Arquitectura | Mes 2 |
| 3. Diseño arquitectónico | Documento de Diseño Arquitectónico Final | Mes 3 |
| 4. Implementación del prototipo | Código + despliegue (mínimo 60% de casos de uso priorizados) | Meses 4–5 |
| 5. Validación y cierre | Documento Final + evidencia de validación + sustentación | Mes 6 |

> Fechas para analizar, no son realistas con el semestre academico, adicional la documentación debe estar lista a mas tardar el 1 mes, los demas meses de trabajo se deberia enfocar en la implementacion del prototipo funcional.

### 5.3 Presupuesto preliminar (categorías a estimar)

- Infraestructura cloud (cómputo, almacenamiento, base(s) de datos).
- Servicios de terceros (mapas, notificaciones, si aplica).
- Herramientas de desarrollo/colaboración (mayormente software libre).
- Contingencia.

> **Pendiente:** cuantificar cada rubro y justificar frente al tope de USD 20.000.

---

## 6. Atributos de Calidad como Escenarios Medibles (borrador)

Formato sugerido: Fuente → Estímulo → Ambiente → Artefacto → Respuesta → Medida de respuesta.

| ID | Atributo | Escenario |
|---|---|---|
| ESC-01 | Disponibilidad | Ante una falla de un componente, el sistema debe seguir operativo, garantizando una disponibilidad ≥ 99% medida mensualmente. |
| ESC-02 | Escalabilidad / Rendimiento | Durante temporada alta, ante un incremento súbito de solicitudes concurrentes, el sistema debe mantener tiempos de respuesta aceptables (umbral por definir, ej. < X segundos en el 95% de las solicitudes). |
| ESC-03 | Interoperabilidad | Al incorporar una nueva fuente de información de un prestador, el sistema debe integrarla sin requerir cambios estructurales al núcleo de la plataforma. |
| ESC-04 | Seguridad | Ante un intento de acceso no autorizado a datos personales, el sistema debe rechazarlo y registrar el evento (trazabilidad). |
| ESC-05 | Mantenibilidad | Al incorporar un nuevo tipo de servicio turístico, el equipo de desarrollo debe poder hacerlo en un tiempo acotado (ej. < N días-persona) sin afectar otros componentes. |

> **Pendiente:** el equipo debe definir umbrales cuantitativos concretos y validarlos posteriormente contra el prototipo.

---

## 7. Análisis de Restricciones

### 7.1 Técnicas
- Acceso desde dispositivos móviles y Web.
- Integración con múltiples fuentes de información.
- Alta concurrencia en temporadas turísticas.
- Disponibilidad mínima del 99%.
- Arquitectura preparada para crecimiento progresivo.
- Evaluar persistencia única vs. políglota, justificando la decisión.
- Definir y justificar el estilo/tecnología de comunicación entre componentes.

### 7.2 Económicas y temporales
- Presupuesto piloto máximo: USD 20.000.
- Preferencia por software libre y servicios cloud de bajo costo.
- Equipo de 5 estudiantes.
- Plazo máximo: Fin de semestre.

### 7.3 Sociales
- Interfaces accesibles para distintos niveles de alfabetización digital.
- Disponibilidad en español e inglés.
- Inclusión de pequeños operadores con recursos tecnológicos limitados.


### 7.4 Ambientales
- Recomendación de destinos alternativos para reducir congestión.
- Reducción del impacto sobre ecosistemas sensibles.
- Difusión de buenas prácticas ambientales.
- Monitoreo de capacidad de carga turística.

### 7.5 Normativas
- Protección de datos personales — Ley 1581 de 2012.
- Protección de información comercial de los operadores.
- Gestión segura de autenticación y autorización.

### 7.6 Éticas
- Explicabilidad de las recomendaciones generadas por IA.
- Evitar sesgos sistemáticos hacia un operador específico.
- Protección de la privacidad de los turistas.
- Transparencia en el tratamiento de los datos.

---



