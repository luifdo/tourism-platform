# Especificación de Requerimientos de Software (SRS)
## Conforme al Estándar ISO/IEC/IEEE 29148:2018

**Proyecto:** Plataforma Digital para la Gestión Integrada y Sostenible del Turismo en Santa Marta  
**Curso:** Arquitectura de Software   
**Programa:** Ingeniería de Sistemas — Universidad del Magdalena  
**Versión:** 1.0 (Estructura Estándar ISO/IEC/IEEE 29148:2018)  
**Fecha:** Agosto 2026  


> * INTEGRANTES:
> * **Luis Fernando Barraza Sanchez** 
> * **Alvaro David Ospino Sanchez**
> * **Valentina  Sarait Nieves Hernandez** 
> * **Andres Felipe Gamero Sanchez**
> * **Juan Francisco Gonzalez Pacheco**
---

## 1. Introducción

### 1.1 Propósito del documento

El presente documento constituye la **Especificación de Requerimientos de Software (SRS)** para la **Plataforma Digital para la Gestión Integrada y Sostenible del Turismo en Santa Marta**, estructurado bajo los lineamientos y directrices del estándar internacional **ISO/IEC/IEEE 29148:2018** (*Systems and software engineering — Life cycle processes — Requirements engineering*).

El propósito primordial de esta especificación es definir de manera formal, no ambigua, completa, consistente y verificable los requerimientos funcionales, requerimientos no funcionales (atributos de calidad), restricciones de diseño y arquitectura, casos de uso, interfaces externas y modelos conceptuales que regirán el desarrollo, validación y evaluación del prototipo del sistema. 

Este documento sirve como acuerdo formal entre el equipo de desarrollo de ingeniería de sistemas, los evaluadores académicos y los actores institucionales y comunitarios del ecosistema turístico de Santa Marta, estableciendo la base técnica para las fases subsiguientes de diseño arquitectónico, implementación, pruebas de carga y verificación de calidad.

---

### 1.2 Alcance del sistema

El sistema consiste en el diseño y desarrollo del prototipo funcional de una **Plataforma Digital para la Gestión Integrada y Sostenible del Turismo en Santa Marta**, fundamentada en una **arquitectura de microservicios basada 100% en Software Libre y de Código Abierto (FOSS)**.

El sistema garantiza atributos de calidad esenciales como escalabilidad elástica, alta disponibilidad, interoperabilidad abierta, seguridad integral (conforme a la Ley 1581 de 2012) y mantenibilidad evolutiva.

* **Desacople del Servicio de Inteligencia Artificial (RF-06):** La IA actúa como un componente analítico auxiliar e independiente del núcleo transaccional. La inferencia de recomendaciones personalizadas opera de forma asíncrona mediante colas de mensajería (RabbitMQ / Redis Streams), impidiendo que el cómputo del modelo bloquee la experiencia del usuario.
* **Moderación Inteligente Embebida:** La clasificación y filtrado de reseñas no requiere un microservicio de IA pesado; se resuelve mediante una heurística liviana/modelo embebido en el módulo de reseñas para pre-marcar lenguaje ofensivo antes de la revisión humana.
* **Estrategia de Datos Sintéticos y Abiertos:** Debido a las restricciones de acceso a historiales privados de visitantes, el entrenamiento y validación del sistema de recomendación utilizará un dataset sintético estructurado por el equipo (perfiles de turista, matrices de interacción simuladas), enriquecido con datos geográficos de OpenStreetMap y estadísticas abiertas del portal nacional de Datos Abiertos de Colombia.

> [!NOTE]
> **Alcance Delimitado (Exclusiones Justificadas del Prototipo):**
> * **Pasarela de Pagos en Línea (UC34 / UC35):** Fuera de alcance en esta iteración. El prototipo opera bajo un modelo de solicitud y confirmación de reserva; las transacciones monetarias se efectúan de manera directa e independiente entre el turista y el prestador de servicios.
> * **Registro de Menores de Edad:** Restringido formalmente a mayores de 18 años para resguardar el marco normativo de Habeas Data infantil.
> * **Repositorio documental en GitHub:** https://github.com/luifdo/tourism-platform/tree/Documents/Documents/Pages

---

### 1.3 Definiciones, acrónimos y abreviaturas

A continuación se definen los términos, abreviaturas y acrónimos empleados a lo largo de este documento:

* **ACID:** *Atomicity, Consistency, Isolation, Durability* (Atomicidad, Consistencia, Aislamiento, Durabilidad), conjunto de propiedades que garantizan que las transacciones en bases de datos se procesen de manera confiable.
* **API:** *Application Programming Interface* (Interfaz de Programación de Aplicaciones), conjunto de definiciones y protocolos que permiten la comunicación entre componentes de software.
* **Argon2id:** Algoritmo criptográfico de derivación de claves y hashing de contraseñas, resistente a ataques de canal lateral y optimizado contra ataques basados en GPU/ASIC.
* **Bounded Context:** Límite conceptual explícito dentro del cual un modelo de dominio particular es aplicable y consistente, propio del Diseño Guiado por el Dominio (DDD).
* **CDN:** *Content Delivery Network* (Red de Entrega de Contenidos), red distribuida geográficamente de servidores proxy para acelerar la entrega de contenido estático.
* **CORS:** *Cross-Origin Resource Sharing* (Intercambio de Recursos de Origen Cruzado), mecanismo de seguridad de navegadores web para permitir o restringir peticiones entre diferentes dominios.
* **Cotelco:** Asociación Hotelera y Turística de Colombia (Capítulo Magdalena).
* **FOSS:** *Free and Open Source Software* (Software Libre y de Código Abierto), software que respeta la libertad de los usuarios y desarrolladores para ejecutar, copiar, distribuir, estudiar, cambiar y mejorar el software.
* **GIS:** *Geographic Information System* (Sistema de Información Geográfica), sistema para capturar, almacenar, manipular, analizar y presentar datos georreferenciados.
* **Habeas Data:** Derecho fundamental que otorga a toda persona la facultad de conocer, actualizar y rectificar las informaciones que se hayan recogido sobre ellas en bancos de datos.
* **I18n:** Internacionalización (*Internationalization*), proceso de diseñar software para que pueda adaptarse a diferentes idiomas y regiones sin cambios de ingeniería.
* **IAM:** *Identity and Access Management* (Gestión de Identidades y Accesos), marco de procesos y tecnologías que facilita la gestión de identidades electrónicas y permisos.
* **INDETUR:** Instituto Distrital de Turismo de Santa Marta.
* **ISO/IEC/IEEE 29148:2018:** Estándar internacional para la ingeniería de requerimientos en procesos del ciclo de vida del software y sistemas.
* **JWT:** *JSON Web Token* (RFC 7519), estándar abierto que define una forma compacta y autónoma para transmitir información de forma segura entre partes como un objeto JSON.
* **MinCIT:** Ministerio de Comercio, Industria y Turismo de Colombia.
* **MongoDB:** Base de datos NoSQL orientada a documentos semiestructurados en formato BSON/JSON.
* **MoSCoW:** Método de priorización de requerimientos categorizados en: *Must have* (Debe tener), *Should have* (Debería tener), *Could have* (Podría tener) y *Won't have* (No tendrá por ahora).
* **ODbL:** *Open Database License*, licencia de datos abiertos utilizada por el proyecto OpenStreetMap.
* **OpenAPI (OAS):** Especificación estándar para la descripción formal y documentación de APIs RESTful independientes del lenguaje de programación.
* **OSM:** *OpenStreetMap*, proyecto colaborativo y abierto para crear mapas editables y libres del mundo.
* **OWASP:** *Open Web Application Security Project*, comunidad abierta dedicada a habilitar a las organizaciones a desarrollar y mantener aplicaciones confiables.
* **PostGIS:** Extensión espacial para el sistema de base de datos objeto-relacional PostgreSQL que añade soporte para objetos geográficos.
* **PostgreSQL:** Sistema de gestión de bases de datos relacional de código abierto potente y compatible con estándares SQL y ACID.
* **Pub/Sub:** *Publish/Subscribe*, patrón de diseño de mensajería asíncrona donde los emisores de mensajes (publicadores) no dirigen mensajes directamente a receptores específicos.
* **RBAC:** *Role-Based Access Control* (Control de Acceso Basado en Roles), método para restringir el acceso al sistema a usuarios autorizados en función de sus roles asignados.
* **REST:** *Representational State Transfer*, estilo de arquitectura de software para sistemas de hipermedios distribuidos.
* **RFC:** *Request for Comments*, publicaciones que describen métodos, comportamientos, investigaciones o innovaciones aplicables al funcionamiento de Internet y sistemas conectados.
* **RNT:** Registro Nacional de Turismo (Colombia), mecanismo de inscripción obligatorio para todos los prestadores de servicios turísticos que efectúen operaciones en Colombia.
* **RPO:** *Recovery Point Objective* (Objetivo de Punto de Recuperación), cantidad máxima aceptable de pérdida de datos medida en tiempo tras un incidente.
* **RTO:** *Recovery Time Objective* (Objetivo de Tiempo de Recuperación), duración máxima de tiempo aceptable para restaurar el servicio tras un desastre o falla técnica.
* **RUT:** Registro Único Tributario (Colombia), mecanismo administrado por la DIAN para identificar, ubicar y clasificar a personas y entidades tributarias.
* **SIC:** Superintendencia de Industria y Comercio de Colombia (autoridad nacional de protección de datos personales).
* **SITUR:** Sistema de Información Turística (SITUR Magdalena).
* **SRS:** *Software Requirements Specification* (Especificación de Requerimientos de Software).
* **SSL / TLS:** *Secure Sockets Layer / Transport Layer Security*, protocolos criptográficos diseñados para proporcionar seguridad en las comunicaciones sobre una red informática.
* **WAF:** *Web Application Firewall*, cortafuegos que monitorea, filtra o bloquea el tráfico HTTP/HTTPS hacia y desde una aplicación web.
* **WCAG:** *Web Content Accessibility Guidelines*, pautas desarrolladas por el W3C para hacer el contenido web más accesible para personas con discapacidad.

---

### 1.4 Referencias

Para la elaboración y validación de esta especificación se han considerado las siguientes normas técnicas, marcos legales y referencias documentales:

1. **ISO/IEC/IEEE 29148:2018:** *Systems and software engineering — Life cycle processes — Requirements engineering*. IEEE Computer Society / ISO / IEC.
2. **Ley Estatutaria 1581 de 2012 (Congreso de la República de Colombia):** *Por la cual se dictan disposiciones generales para la protección de datos personales (Habeas Data)*.
3. **Decreto Reglamentario 1377 de 2013 (República de Colombia):** *Por el cual se reglamenta parcialmente la Ley 1581 de 2012 sobre recolección, almacenamiento y tratamiento de datos personales*.
4. **Ley 300 de 1996 (Congreso de la República de Colombia):** *Ley General de Turismo*.
5. **Ley 2068 de 2020 (Congreso de la República de Colombia):** *Por la cual se modifica la Ley 300 de 1996 y se dictan otras disposiciones en materia de sostenibilidad y reactivación del turismo*.
6. **W3C (World Wide Web Consortium):** *Web Content Accessibility Guidelines (WCAG) 2.1*. W3C Recommendation (Nivel de conformidad AA).
7. **IETF RFC 7519:** *JSON Web Token (JWT)*. Internet Engineering Task Force.
8. **IETF RFC 9110:** *HTTP Semantics / REST Architecture Specifications*.
9. **OpenAPI Initiative:** *OpenAPI Specification v3.0.3 (OAS)*. Linux Foundation.
10. **OpenStreetMap Foundation:** *Open Database License (ODbL) 1.0*. OSM Geo-Data Licensing.
11. **SITUR Magdalena & Cotelco:** *Boletines Estadísticos de Ocupación Hotelera y Flujo Turístico en Santa Marta*. Sistema de Información Turística del Magdalena.

---

## 2. Descripción General

### 2.1 Perspectiva del producto

Santa Marta es uno de los principales destinos turísticos del Caribe colombiano, recibiendo anualmente un alto volumen de visitantes nacionales e internacionales atraídos por sus playas, el Centro Histórico, el Parque Nacional Natural Tayrona, la Sierra Nevada de Santa Marta y su diversa oferta de turismo cultural, gastronómico, ecológico y de aventura.

Este dinamismo turístico representa un motor esencial para el desarrollo socioeconómico regional, pero también introduce desafíos críticos relacionados con la gobernanza, integración de servicios, sostenibilidad ambiental y disponibilidad oportuna de información para la toma de decisiones informadas por parte de turistas, prestadores de servicios y entidades gubernamentales.

![Diagrama de Problemáticas y Solución](./Diagrama_Problematicas_Solucion.svg)

<details>
<summary><b>Ver especificación de código Mermaid del diagrama</b></summary>

```mermaid
flowchart TB
    classDef probBox fill:#fff1f2,stroke:#e11d48,stroke-width:2px,color:#9f1239,font-weight:600,rx:8px,ry:8px;
    classDef solBox fill:#ecfdf5,stroke:#059669,stroke-width:2px,color:#065f46,font-weight:600,rx:8px,ry:8px;

    subgraph Problematicas["Problemáticas del Ecosistema Turístico"]
        direction TB
        P1["Concentración excesiva en sitios icónicos"]:::probBox
        P2["Información dispersa y desactualizada"]:::probBox
        P3["Exclusión digital de MiPyMEs turísticas"]:::probBox
        P4["Falta de control de capacidad de carga"]:::probBox
        P5["Inestabilidad en picos de demanda"]:::probBox
    end

    subgraph Solucion["Solución: Plataforma Digital Integrada (FOSS)"]
        direction TB
        S1["Recomendación inteligente & dispersión de flujos"]:::solBox
        S2["Catálogo unificado, transparente y georreferenciado"]:::solBox
        S3["Inclusión comunitaria y panel sin barreras técnicas"]:::solBox
        S4["Monitoreo de aforo & analítica institucional"]:::solBox
        S5["Arquitectura de microservicios elástica y desacoplada"]:::solBox
    end

    P1 ==>|Resuelve con| S1
    P2 ==>|Resuelve con| S2
    P3 ==>|Resuelve con| S3
    P4 ==>|Resuelve con| S4
    P5 ==>|Resuelve con| S5
```
</details>

#### Problemáticas Identificadas

1. **Saturación y sobrecarga en zonas sensibles:** Concentración excesiva de turistas en atractivos tradicionales durante temporadas altas, impactando negativamente ecosistemas frágiles (ej. Parque Tayrona, Minca).
2. **Fragmentación y heterogeneidad de la oferta:** Baja integración entre hoteles, restaurantes, operadores y guías, con datos dispersos sobre disponibilidad, horarios, tarifas y normativas.
3. **Brecha digital y visibilidad inequitativa:** Limitada presencia tecnológica de micro, pequeños y medianos prestadores turísticos frente a grandes cadenas.
4. **Ausencia de gestión integrada de reservas y aforos:** Dificultad para consultar disponibilidad centralizada y gestionar solicitudes de reserva de forma anticipada.
5. **Déficit de inteligencia turística y datos para la toma de decisiones:** Carencia de indicadores consolidados de demanda, ocupación y capacidad de carga para la formulación de políticas públicas.
6. **Inestabilidad del servicio en picos de demanda:** Riesgo de degradación de sistemas digitales convencionales ante la concurrencia estacional masiva.

> [!NOTE]
> **Definición de Temporada Alta y Respaldo Cuantitativo:** Se contempla complementar la caracterización del problema con estadísticas oficiales del Sistema de Información Turística (SITUR Magdalena), Cotelco Magdalena y la Secretaría de Desarrollo Económico y Sostenibilidad de Santa Marta antes de la sustentación final.

---

### 2.2 Funciones del producto

La plataforma articula sus capacidades a través de un conjunto integrado de funciones principales que resuelven las problemáticas del ecosistema:

1. **Catálogo Unificado y Búsqueda Geoespacial Multicriterio (RF-01, RF-02):** Centralización de atractivos turísticos, actividades culturales y oferta gastronómica/hotelera con navegación georreferenciada sobre mapas abiertos y filtros por zona, precio y categoría.
2. **Control Atómico de Disponibilidad y Solicitud de Reservas (RF-03, RF-04, RF-05):** Motor transaccional para consulta de cupos en tiempo real, emisión de solicitudes de reserva por parte de turistas y gestión de confirmaciones/cancelaciones por parte de prestadores verificados.
3. **Recomendación Inteligente Explicable y Dispersión Sostenible (RF-06):** Sistema de recomendación desacoplado basado en filtrado híbrido que sugiere actividades personalizadas acompañadas de justificaciones legibles, fomentando la redistribución de visitantes hacia destinos emergentes.
4. **Inteligencia de Negocios y Tableros para Gobernanza del Destino (RF-07, RF-13):** Consolidación analítica de métricas de demanda, cálculo estimativo de presión sobre capacidades de carga y exportación de reportes estructurados (CSV/PDF) para autoridades turísticas.
5. **Inclusión Digital de Prestadores Comunitarios (RF-08):** Formularios simplificados y asistidos para que pequeños operadores locales y comunitarios publiquen sus servicios sin barreras técnicas.
6. **Seguridad Integral, IAM y Auditoría Inmutable (RF-09, RF-12):** Gestión perimetral de identidades bajo OAuth2/JWT, control estricto de roles (RBAC), verificación documental (RNT, RUT) y registro auditable de eventos críticos.
7. **Internacionalización y Accesibilidad (RF-10):** Soporte bilingüe completo (Español/Inglés) con estándares de contraste y adaptabilidad WCAG 2.1 AA.
8. **Mensajería Transaccional Asíncrona (RF-11):** Despacho automatizado de notificaciones por correo electrónico ante cambios en el ciclo de vida de las reservas.

---

### 2.3 Características de los usuarios / Stakeholders

Conforme al estándar ISO/IEC/IEEE 29148:2018, los interesados del sistema se clasifican para delimitar el alcance, las responsabilidades operativas y la trazabilidad de requerimientos.

| Tipo | Stakeholder | Rol frente al Sistema | Intereses y Necesidades Principales |
|---|---|---|---|
| **Actor Directo** | **Turista** *(Nacional / Internacional)* | Usuario final que explora, consulta, solicita reservas y califica servicios turísticos. | • Información veraz, consolidada y en tiempo real.<br>• Recomendaciones inteligentes y contextuales.<br>• Proceso de solicitud de reserva ágil e intuitivo.<br>• Interfaz bilingüe (Español/Inglés) y accesible. |
| **Actor Directo** | **Prestador Turístico** *(Hoteles, restaurantes, guías, operadores)* | Proveedor de información que publica ofertas, gestiona disponibilidad y atiende solicitudes. | • Canal de visibilidad digital gratuito y equitativo.<br>• Administración simplificada de cupos y tarifas.<br>• Protección de su información comercial.<br>• Interacción directa con las reseñas de sus clientes. |
| **Actor Directo** | **Entidad de Gestión del Destino** *(Secretaría de Turismo, INDETUR, Corpoteyrona)* | Actor institucional responsable de la gobernanza, sostenibilidad y políticas turísticas. | • Acceso a analítica de demanda, tendencias y aforos.<br>• Herramientas de alerta y comunicación oficial.<br>• Reportes estructurados para toma de decisiones. |
| **Actor Directo** | **Administrador del Sistema** | Gestor técnico y operativo de la plataforma. | • Control de identidades, roles (RBAC) y permisos.<br>• Verificación de legitimidad de prestadores.<br>• Auditoría de seguridad y monitoreo de desempeño. |
| **Actor Indirecto / Normativo** | **Ente Regulador** *(Superintendencia de Industria y Comercio - SIC)* | Autoridad de supervisión de datos personales. | • Cumplimiento riguroso de la Ley Estatutaria 1581 de 2012 y Habeas Data.<br>• Trazabilidad de consentimientos informados. |
| **Actor Indirecto / Externo** | **Servicios de Cartografía Abierta** *(OpenStreetMap / Nominatim)* | Proveedor de infraestructura geoespacial FOSS. | • Geolocalización, cálculo de distancias y visualización de capas de mapas sin costos de licenciamiento comercial. |
| **Actor Indirecto / Externo** | **Servicio de Notificaciones** *(SMTP / Postal / SES)* | Proveedor de entrega de correos transaccionales. | • Entrega confiable de correos de confirmación de reserva y avisos de seguridad. |

> [!IMPORTANT]
> **Restricción Normativa de Registro (Habeas Data):** El registro en la plataforma está formalmente restringido a personas **mayores de 18 años**. El tratamiento de datos de menores de edad queda fuera de alcance en esta iteración para simplificar el régimen legal aplicable.

---

### 2.4 Restricciones generales

#### 2.4.1 Restricciones Técnicas
* **Arquitectura de Microservicios:** Despliegue obligatorio de los 6 microservicios definidos en la Sección 3.6 mediante contenedores Docker.
* **Persistencia Políglota FOSS:** Uso exclusivo de PostgreSQL + PostGIS, MongoDB Community Edition y Redis / Valkey.
* **Integración Abierta:** Prohibición del uso de APIs privativas de mapas con costos por consumo (ej. Google Maps API); uso estricto del ecosistema OpenStreetMap.
* **Compatibilidad Multiplataforma:** Interfaz web responsiva compatible con navegadores móviles y de escritorio modernos sin requerir instalación de aplicativos nativos.

#### 2.4.2 Restricciones Económicas y de Recursos
* **Techo Presupuestal:** Límite financiero estricto de **USD 20.000**, con esquemas de ejecución transparente para prototipo académico (USD 6.900) o despliegue institucional piloto (USD 20.000).
* **Talento Humano:** Proyecto ejecutado por un equipo de 5 ingenieros en un marco temporal de 14 semanas lectivas.
* **Modelo Gratuito:** Sin monetización directa ni comisiones sobre transacciones de reserva.

#### 2.4.3 Restricciones Sociales y de Accesibilidad
* **Inclusión de la Economía Popular:** Interfaces intuitivas diseñadas para prestadores turísticos tradicionales con baja alfabetización digital (RF-08).
* **Internacionalización:** Soporte bilingüe completo (Español / Inglés) en catálogo y flujos transaccionales.
* **Límite de Edad:** Registro exclusivo para personas mayores de 18 años para resguardar la privacidad infantil.

#### 2.4.4 Restricciones Ambientales y de Sostenibilidad
* **Protección de Ecosistemas Vulnerables:** Los algoritmos de recomendación deben priorizar la dispersión de flujos turísticos hacia destinos emergentes para mitigar la saturación de áreas protegidas de la Sierra Nevada y el Parque Tayrona.
* **Monitoreo de Capacidad de Carga:** Indicadores analíticos para apoyar las restricciones de ingreso dictadas por autoridades ambientales.

#### 2.4.5 Restricciones Normativas y Legales
* **Ley 1581 de 2012 (Protección de Datos Personales):** Consentimiento informado previo, almacenamiento cifrado de datos sensibles y derecho de actualización/supresión (Habeas Data).
* **Ley General de Turismo (Ley 300 de 1996 / Ley 2068 de 2020):** Exigencia del Registro Nacional de Turismo (RNT) como requisito de verificación para prestadores comerciales.

#### 2.4.6 Restricciones Éticas en Inteligencia Artificial
* **Explicabilidad Algorítmica (RNF-08):** Prohibición de modelos de caja negra impenetrables; toda sugerencia turística debe indicar su lógica de recomendación al usuario final.
* **Equidad y Neutralidad:** El algoritmo no debe aplicar sesgos discriminatorios ni favorecer comercialmente a ningún operador sobre otro.

---

### 2.5 Supuestos y dependencias

1. **Supuesto de Datos Sintéticos:** Debido a restricciones de confidencialidad y a la inexistencia de un repositorio público con historiales de transacciones individuales de turistas en Santa Marta, el entrenamiento, ajuste y pruebas de carga del sistema de recomendación (RF-06) se sustentan en la generación de un dataset sintético representativo (matrices de interacción usuario-ítem simuladas), enriquecido con datos geográficos reales de OpenStreetMap y estadísticas macroeconómicas del portal nacional de Datos Abiertos de Colombia.
2. **Dependencia de la Infraestructura de Cartografía Abierta (OSM / Nominatim):** El módulo de Catálogo y GIS depende operativamente de los servidores de teselas (*tiles*) y APIs de geocodificación de OpenStreetMap y Nominatim, asumiendo su disponibilidad bajo las políticas de uso justo del ecosistema FOSS.
3. **Dependencia del Servicio de Transporte de Correo (SMTP):** El despacho de correos electrónicos transaccionales de confirmación de reserva (UC36, RF-11) y restablecimiento de credenciales depende de la conectividad con un servidor de correo saliente SMTP (o servicio FOSS compatible como Postal / AWS SES).
4. **Dependencia de Verificación Administrativa Humana:** La activación pública de las ofertas de prestadores depende del proceso de revisión y validación manual de los documentos de acreditación legal (RNT, RUT) por parte del rol Administrador del Sistema.
5. **Dependencia de Información Oficial de Destino:** La calibración de los límites de aforo y alertas institucionales asume la provisión periódica de lineamientos de capacidad de carga por parte de la Entidad de Gestión (INDETUR, Corpoteyrona, Parques Nacionales Naturales).

---

## 3. Requerimientos Específicos

### 3.1 Requerimientos funcionales

A continuación se detalla la especificación completa de los requerimientos funcionales del sistema, priorizados bajo la metodología MoSCoW:

| ID | Requerimiento Funcional | Prioridad | Módulo Asignado | Stakeholder | Criterio de Verificación |
|---|---|---|---|---|---|
| **RF-01** | Consultar catálogo de atractivos, actividades y eventos turísticos. | **Must** | Módulo 2: Catálogo & GIS | Turista | Visualización completa del catálogo con filtros básicos sin requerir autenticación. |
| **RF-02** | Buscar y filtrar servicios por categoría, ubicación espacial, tarifa y disponibilidad. | **Must** | Módulo 2: Catálogo & GIS | Turista | Los filtros combinados devuelven resultados exactos en un tiempo inferior a 1.5s. |
| **RF-03** | Consultar la disponibilidad actualizada de cupos de un servicio. | **Must** | Módulo 3: Reservas & Cupos | Turista | El calendario refleja en tiempo real los cupos habilitados por el prestador. |
| **RF-04** | Registrar solicitudes de reserva de actividades o servicios turísticos. | **Must** | Módulo 3: Reservas & Cupos | Turista | Se genera una reserva en estado `Solicitada` visible en el panel del turista y del prestador. |
| **RF-05** | Permitir a los prestadores registrar y actualizar su oferta y cupos. | **Must** | Módulo 2 y 3 | Prestador | Un prestador verificado crea y edita servicios visualizándose inmediatamente en el catálogo. |
| **RF-06** | Generar recomendaciones personalizadas explicables mediante IA desacoplada. | **Should** | Módulo 5: IA & Recomendación | Turista | El usuario recibe sugerencias basadas en su historial/preferencias junto con la justificación explicativa (RNF-08). |
| **RF-07** | Generar tableros e indicadores agregados de demanda y aforo para planificación. | **Should** | Módulo 6: Analítica & Destino | Entidad | La entidad visualiza gráficos de demanda por zonas y estimación de concentración turística. |
| **RF-08** | Incorporación asistida y sin barreras técnicas para prestadores comunitarios. | **Should** | Módulo 1 y 2 | Prestador | El formulario de registro y carga de servicios no requiere más de 3 pasos sencillos. |
| **RF-09** | Gestión de identidades, control de acceso RBAC y bitácora de auditoría. | **Must** | Módulo 1: Seguridad & IAM | Admin | Intentos de acceso no autorizados devuelven HTTP 403 y quedan registrados en la bitácora. |
| **RF-10** | Disponibilidad de la interfaz en idiomas Español e Inglés (I18n). | **Should** | Transversal | Turista, Entidad | Conmutación instantánea de idioma traduciendo etiquetas, menús y contenidos base. |
| **RF-11** | Enviar notificaciones por correo de confirmación/cancelación de reservas. | **Should** | Módulo 6 / Broker | Turista, Prestador | Tras confirmarse la reserva (UC20), se despacha un correo formateado en menos de 10s. |
| **RF-12** | Permitir a prestadores adjuntar documentos de verificación legal (RNT, RUT). | **Should** | Módulo 1: Seguridad & IAM | Prestador, Admin | El prestador sube archivos PDF/imagen que son auditados por el administrador antes de publicar. |
| **RF-13** | Exportar reportes analíticos e indicadores en formatos estándar (CSV / PDF). | **Could** | Módulo 6: Analítica & Destino | Entidad | Descarga funcional de archivos estructurados con métricas del destino. |

---

### 3.2 Casos de uso

#### 3.2.1 Actores del Sistema
* **Turista (`Tur`):** Usuario final autenticado o anónimo que interactúa con el catálogo, solicita reservas y aporta reseñas.
* **Prestador de Servicios Turísticos (`Prest`):** Actor comercial verificado que administra servicios, cupos y atiende reservas.
* **Entidad de Gestión del Destino (`Entidad`):** Actor gubernamental o institucional que analiza métricas y emite avisos oficiales.
* **Administrador (`Admin`):** Custodio técnico de la seguridad, roles, moderación y observabilidad.
* **Sistema / Servicios Externos (`SysExt`):** Motor de colas, proveedor de mapas OSM y pasarela de correo SMTP.

#### 3.2.2 Matriz Detallada de Casos de Uso

| Código | Caso de Uso | Actor Principal | Relaciones / Dependencias | Módulo Asignado |
|---|---|---|---|---|
| **UC1** | Registrarse en la plataforma (18+ años) | Turista, Prestador | `<<include>>` UC6 | Módulo 1: Seguridad & IAM |
| **UC2** | Iniciar sesión y obtener token de acceso | Todos los actores | Control de acceso perimetral | Módulo 1: Seguridad & IAM |
| **UC3** | Recuperar / restablecer contraseña | Turista, Prestador, Entidad | Verificación vía correo | Módulo 1: Seguridad & IAM |
| **UC4** | Gestionar perfil de usuario | Turista, Prestador | - | Módulo 1: Seguridad & IAM |
| **UC5** | Cambiar idioma de la interfaz (ES / EN) | Turista, Entidad | I18n transversal en frontend | Transversal (Frontend) |
| **UC6** | Aceptar política de tratamiento de datos personales | Sistema / Transversal | `<<include>>` en UC1 | Módulo 1: Seguridad & IAM |
| **UC7** | Consultar catálogo de atractivos, actividades y eventos | Turista (anónimo/autenticado) | Base de búsqueda | Módulo 2: Catálogo & GIS |
| **UC8** | Buscar y filtrar servicios (precio, zona, tipo) | Turista | `<<include>>` UC7 | Módulo 2: Catálogo & GIS |
| **UC9** | Consultar detalle de atractivo / servicio | Turista | `<<include>>` UC7 | Módulo 2: Catálogo & GIS |
| **UC10** | Consultar disponibilidad en tiempo real | Turista | `<<include>>` en UC11 | Módulo 3: Reservas & Cupos |
| **UC11** | Solicitar reserva de actividad o servicio | Turista | `<<include>>` UC2, `<<include>>` UC10 | Módulo 3: Reservas & Cupos |
| **UC12** | Cancelar / modificar solicitud de reserva | Turista | `<<include>>` UC13 | Módulo 3: Reservas & Cupos |
| **UC13** | Consultar historial de reservas propias | Turista | Extendido por UC14 | Módulo 3: Reservas & Cupos |
| **UC14** | Recibir recomendaciones personalizadas explicables | Turista | `<<extend>>` UC13, `<<async>>` | Módulo 5: IA & Recomendación |
| **UC15** | Calificar y redactar reseña de experiencia | Turista | Extendido por UC29 | Módulo 4: Anotaciones & Reseñas |
| **UC16** | Visualizar mapa interactivo de atractivos y zonas | Turista, Entidad | Integración OpenStreetMap | Módulo 2: Catálogo & GIS |
| **UC17** | Registrar nueva oferta turística | Prestador | `<<include>>` UC2, `<<include>>` UC28 | Módulo 2: Catálogo & GIS |
| **UC18** | Editar / actualizar información de servicio | Prestador | `<<include>>` UC2 | Módulo 2: Catálogo & GIS |
| **UC19** | Gestionar calendario de disponibilidad y tarifas | Prestador | `<<include>>` UC2 | Módulo 3: Reservas & Cupos |
| **UC20** | Confirmar / rechazar solicitudes de reserva | Prestador | Dispara evento a UC36 | Módulo 3: Reservas & Cupos |
| **UC21** | Responder públicamente a comentarios de turistas | Prestador | `<<include>>` UC15 | Módulo 4: Anotaciones & Reseñas |
| **UC22** | Consultar métricas de rendimiento de su oferta | Prestador | - | Módulo 6: Analítica & Destino |
| **UC23** | Consultar indicadores agregados de demanda turística | Entidad | `<<include>>` en UC25 | Módulo 6: Analítica & Destino |
| **UC24** | Monitorear estimación de capacidad de carga | Entidad | `<<include>>` en UC25 | Módulo 6: Analítica & Destino |
| **UC25** | Generar tableros de planificación turística | Entidad | `<<include>>` UC23, `<<include>>` UC24 | Módulo 6: Analítica & Destino |
| **UC26** | Publicar alertas oficiales y avisos de sostenibilidad | Entidad | - | Módulo 6: Analítica & Destino |
| **UC27** | Administrar usuarios, roles y asignación de permisos | Admin | Control RBAC central | Módulo 1: Seguridad & IAM |
| **UC28** | Aprobar / rechazar prestadores de servicios | Admin | `<<include>>` UC37 | Módulo 1: Seguridad & IAM |
| **UC29** | Moderar reseñas y contenido sensible reportado | Admin | `<<extend>>` UC15 | Módulo 4: Anotaciones & Reseñas |
| **UC30** | Configurar integraciones y orígenes de datos abiertos | Admin | - | Transversal (Config / GW) |
| **UC31** | Monitorear telemetría y métricas de salud del sistema | Admin | Prometheus + Grafana | Transversal (Observabilidad) |
| **UC32** | Gestionar políticas de seguridad y rate limiting | Admin | - | Módulo 1: Seguridad & IAM |
| **UC33** | Consultar bitácora de auditoría inmutable | Admin | Trazabilidad RNF-10 | Módulo 1: Seguridad & IAM |
| **UC36** | Despachar notificación de confirmación por correo | Sistema / SysExt | Disparado por UC20 | Módulo 6 / Worker Eventos |
| **UC37** | Cargar documentos de verificación (RNT, RUT) | Prestador | `<<include>>` en UC28 | Módulo 1: Seguridad & IAM |
| **UC38** | Exportar reportes analíticos (CSV / PDF) | Entidad | `<<extend>>` UC25 | Módulo 6: Analítica & Destino |

#### 3.2.3 Diagrama General de Casos de Uso

![Diagrama de Casos de Uso - Plataforma Digital de Turismo Santa Marta](./CasosDeUso_PlataformaTurismoSantaMarta.svg)

---

### 3.3 Requerimientos de interfaz

#### 3.3.1 Interfaces de Usuario (UI)
* **Diseño Web Responsivo:** La interfaz se construirá utilizando estándares HTML5, Vanilla CSS3 y componentes JavaScript/Vue.js, optimizada para resoluciones móviles (desde 360px de ancho) y pantallas de escritorio.
* **Internacionalización Dinámica (I18n):** Mecanismo de alternancia instantánea entre Español (idioma por defecto) e Inglés mediante archivos de recursos JSON sin recarga completa de página.
* **Accesibilidad Web:** Cumplimiento de las directrices WCAG 2.1 Nivel AA, asegurando relaciones de contraste de color mínimas de 4.5:1 para texto estándar, etiquetas descriptivas en controles interactivos (`aria-label`) y soporte de navegación por teclado.

#### 3.3.2 Interfaces de Software / APIs Externas
* **OpenStreetMap / Nominatim (API de Cartografía y Geocodificación):**
  * *Protocolo:* HTTPS / REST.
  * *Formato:* Tiles ráster/vectoriales (XYZ) y respuestas JSON para geocodificación inversa.
  * *Librería Cliente:* Leaflet.js o MapLibre GL.
  * *Finalidad:* Despliegue de capas cartográficas, marcadores interactivos de atractivos y cálculo de distancias aproximadas en el Módulo 2.
* **Servicio de Notificaciones por Correo Electrónico (SMTP / Transportador FOSS):**
  * *Protocolo:* SMTP sobre TLS (puertos 587 / 465).
  * *Formato de Contenido:* Mensajes multiparte MIME con versión HTML enriquecida y texto plano.
  * *Finalidad:* Envío de enlaces de confirmación, restablecimiento de credenciales (Módulo 1) y avisos de confirmación de reserva (Módulo 6).
* **Plataforma de Datos Abiertos de Colombia:**
  * *Protocolo:* HTTPS / REST (Socrata Open Data API - SODA) o ingesta periódica de archivos CSV/JSON.
  * *Finalidad:* Enriquecimiento de indicadores de demanda y calibración de atractivos culturales en el Módulo 6.

#### 3.3.3 Interfaces de Comunicación e Integración Interna
* **API Gateway Perimetral:**
  * *Protocolo:* HTTPS (TLS 1.3) con intercambio de cargas en JSON (RESTful).
  * *Especificación:* Contratos formales documentados bajo **OpenAPI 3.0**.
  * *Seguridad:* Inspección de cabeceras de autorización HTTP (`Authorization: Bearer <JWT>`), limitación de tasa (*Rate Limiting*) y políticas estrictas de CORS.
* **Bus de Mensajería Asíncrona (Event Bus):**
  * *Protocolo:* AMQP 0-9-1 (RabbitMQ) o Redis Protocol (RESP / Streams).
  * *Formato de Mensaje:* Esquemas JSON versionados con metadatos de timestamp, id de evento y payload serializado.
  * *Finalidad:* Desacople del modelo de IA (Módulo 5) y del despachador de correos y bitácora (Módulos 1 y 6).

---

### 3.4 Requerimientos no funcionales / atributos de calidad

| ID | Atributo | Requerimiento No Funcional | Prioridad | Estándar / Verificación |
|---|---|---|---|---|
| **RNF-01** | **Disponibilidad** | El sistema debe mantener una tasa de disponibilidad operativa $\ge 99.0\%$ durante su ventana de servicio. | **Should** | Monitoreo continuo mediante sondas de salud (Healthchecks en `/health`). |
| **RNF-02** | **Escalabilidad** | La arquitectura de microservicios debe escalar horizontalmente ante incrementos de tráfico en temporada alta. | **Must** | Pruebas de carga simulada con herramientas FOSS (k6 / Locust / JMeter). |
| **RNF-03** | **Interoperabilidad** | La plataforma debe exponer APIs REST documentadas bajo especificación OpenAPI 3.0. | **Must** | Validación con esquemas Swagger/OpenAPI y consumo desacoplado. |
| **RNF-04** | **Seguridad** | Autenticación basada en JWT, cifrado de credenciales con Argon2id y cumplimiento de la Ley 1581 de 2012. | **Must** | Pruebas de vulnerabilidad estática y registro explícito de consentimiento (UC6). |
| **RNF-05** | **Mantenibilidad** | El desacople entre microservicios debe permitir modificar o reentrenar módulos sin alterar el núcleo. | **Should** | Tiempo estimado de incorporación de un nuevo servicio $\le 5$ días-persona. |
| **RNF-06** | **Rendimiento** | El tiempo de respuesta para el 95% de las consultas de catálogo debe ser inferior a 2.0 segundos. | **Must** | Medición de latencia percentil 95 ($p95$) bajo concurrencia controlada. |
| **RNF-07** | **Accesibilidad** | Las interfaces deben satisfacer pautas de diseño accesible (WCAG 2.1 Nivel AA básico: contraste, texto escalable). | **Should** | Evaluación con herramientas de auditoría accesible (Lighthouse / axe-core). |
| **RNF-08** | **Transparencia Ética** | Toda recomendación automática generada por el módulo de IA debe ser explicable y auditable. | **Should** | Cada recomendación incluye la entidad de justificación visible al turista. |
| **RNF-09** | **Respaldo & Recuperación** | Mecanismos de copia de seguridad periódica de las bases de datos y procedimiento de restauración validado. | **Should** | Ejecución de al menos un simulacro de restauración de datos documentado. |
| **RNF-10** | **Auditoría de Seguridad** | Registro inmutable de eventos administrativos, accesos denegados y modificaciones de estado. | **Must** | Consulta de bitácora disponible en panel administrativo (UC33). |
| **RNF-11** | **Usabilidad** | El flujo de solicitud de reserva debe completarse en un máximo de 4 pasos interactivos. | **Should** | Validación mediante pruebas de usuario guiadas (Buscar $\rightarrow$ Detalle $\rightarrow$ Solicitar $\rightarrow$ Confirmar). |
| **RNF-12** | **Portabilidad FOSS** | La solución debe ejecutarse en cualquier entorno Linux mediante contenedores Docker estándar. | **Must** | Despliegue reproducible con `docker-compose up` en servidores locales o cloud. |

---

### 3.5 Escenarios de atributos de calidad

Formato de especificación formal: **Fuente $\rightarrow$ Estímulo $\rightarrow$ Ambiente $\rightarrow$ Artefacto $\rightarrow$ Respuesta $\rightarrow$ Medida de Respuesta**.

| ID | Atributo | Escenario Formal |
|---|---|---|
| **ESC-01** | **Disponibilidad** | *Fuente:* Caída imprevista de un nodo de servicio. *Estímulo:* Falla en el contenedor del Módulo de Reseñas. *Ambiente:* Operación normal. *Artefacto:* API Gateway y clúster. *Respuesta:* El Gateway aísla el microservicio degradado sin interrumpir la navegación en catálogo ni las reservas. *Medida:* Disponibilidad global del sistema $\ge 99.0\%$, tiempo de aislamiento $< 5$ segundos. |
| **ESC-02** | **Rendimiento & Carga** | *Fuente:* Turistas concurrentes en temporada de vacaciones. *Estímulo:* 500 solicitudes concurrentes por segundo en búsqueda de catálogo. *Ambiente:* Pico estacional. *Artefacto:* Módulo 2 (Catálogo) + Caché Redis. *Respuesta:* El sistema atiende las consultas apoyándose en caché en memoria. *Medida:* Tiempo de respuesta $p95 < 2.0$ segundos sin errores HTTP 5xx. |
| **ESC-03** | **Interoperabilidad** | *Fuente:* Desarrollador / Administrador. *Estímulo:* Integración de una nueva fuente de datos abiertos de eventos culturales. *Ambiente:* Mantenimiento evolutivo. *Artefacto:* Módulo 2 (Catálogo). *Respuesta:* Ingesta de datos vía API REST sin modificar la estructura del esquema relacional base. *Medida:* Incorporación funcional completada en $\le 3$ días hábiles. |
| **ESC-04** | **Seguridad & Auditoría** | *Fuente:* Usuario no autorizado / Atacante externo. *Estímulo:* Intento de acceso a endpoints de reportes institucionales sin token o con rol inválido. *Ambiente:* Operación normal. *Artefacto:* Módulo 1 (IAM) y API Gateway. *Respuesta:* Bloqueo inmediato de la petición con HTTP 403 Forbidden y registro detallado del evento (IP, timestamp, usuario) en la bitácora. *Medida:* 100% de los accesos indebidos registrados en la bitácora de auditoría inmutable. |
| **ESC-05** | **Mantenibilidad** | *Fuente:* Equipo de ingeniería. *Estímulo:* Sustitución o ajuste del algoritmo de recomendación en el microservicio de IA. *Ambiente:* Ciclo de desarrollo. *Artefacto:* Módulo 5 (IA). *Respuesta:* Reentrenamiento y despliegue del nuevo worker de IA sin reiniciar ni alterar los microservicios de Reservas o Catálogo. *Medida:* Cero tiempo de inactividad (*zero-downtime*) en el núcleo transaccional. |
| **ESC-06** | **Recuperación ante Fallos** | *Fuente:* Administrador del sistema. *Estímulo:* Simulación de corrupción de la base de datos de reservas. *Ambiente:* Prueba de contingencia. *Artefacto:* Script de respaldo y PostgreSQL. *Respuesta:* Restauración del último volcado (*dump*) programado. *Medida:* Tiempo de recuperación objetivo ($RTO) \le 30$ minutos; pérdida máxima de datos ($RPO) \le 24$ horas. |
| **ESC-07** | **Usabilidad** | *Fuente:* Turista primerizo. *Estímulo:* Búsqueda, selección y envío de solicitud de reserva para un tour ecológico. *Ambiente:* Dispositivo móvil con conexión estándar 4G. *Artefacto:* Interfaz de usuario web. *Respuesta:* Navegación guiada en un flujo de 4 pantallas consecutivas sin bloqueos. *Medida:* Tasa de éxito en la tarea $\ge 90\%$ en pruebas de usabilidad asistidas. |

---

### 3.6 Requerimientos de diseño y restricciones de arquitectura

#### 3.6.1 Estilo Arquitectónico Base y Descomposición Modular

Se adopta una **Arquitectura de Microservicios Desacoplada**, organizada en **6 microservicios funcionales bien delimitados (*Bounded Contexts*)**, un **API Gateway perimetral** y una **Capa Transversal de Mensajería y Observabilidad**, garantizando una separación nítida de responsabilidades y compatibilidad total con licenciamiento libre.

![Diagrama de Arquitectura de Microservicios FOSS](./Diagrama_Arquitectura_Microservicios.svg)

<details>
<summary><b>Ver especificación de código Mermaid del diagrama de arquitectura</b></summary>

```mermaid
flowchart TB
    classDef clientStyle fill:#eff6ff,stroke:#2563eb,stroke-width:2px,color:#1e40af,font-weight:bold,rx:8px,ry:8px;
    classDef gatewayStyle fill:#f5f3ff,stroke:#7c3aed,stroke-width:2px,color:#5b21b6,font-weight:bold,rx:8px,ry:8px;
    classDef msCoreStyle fill:#f0fdf4,stroke:#16a34a,stroke-width:2px,color:#14532d,font-weight:bold,rx:8px,ry:8px;
    classDef msAiStyle fill:#fdf4ff,stroke:#c026d3,stroke-width:2px,color:#701a75,font-weight:bold,rx:8px,ry:8px;
    classDef brokerStyle fill:#fffbeb,stroke:#d97706,stroke-width:2px,color:#78350f,font-weight:bold,rx:8px,ry:8px;
    classDef dbStyle fill:#f8fafc,stroke:#475569,stroke-width:2px,color:#0f172a,font-weight:bold,rx:5px,ry:5px;
    classDef cacheStyle fill:#fff1f2,stroke:#e11d48,stroke-width:2px,color:#881337,font-weight:bold,rx:5px,ry:5px;

    Clients["Clientes Web Responsivos & Móviles<br><i>(Turistas, Prestadores, Entidades, Admins)</i>"]:::clientStyle
    APIGW["API Gateway & Reverse Proxy<br><i>(Nginx / Traefik — TLS, JWT Validation, Rate Limiting, CORS)</i>"]:::gatewayStyle

    Clients ==>|HTTPS / REST| APIGW

    subgraph Microservicios["Ecosistema de Microservicios FOSS"]
        direction TB
        MS1["Módulo 1: Seguridad & IAM<br><i>(Auth, RBAC, Auditoría, Verificación RNT)</i>"]:::msCoreStyle
        MS2["Módulo 2: Catálogo & GIS<br><i>(Atractivos, Búsqueda, OpenStreetMap)</i>"]:::msCoreStyle
        MS3["Módulo 3: Reservas & Disponibilidad<br><i>(Calendario de Cupos, Solicitudes)</i>"]:::msCoreStyle
        MS4["Módulo 4: Reseñas & Moderación<br><i>(Opiniones, Calificaciones, Pre-filtro)</i>"]:::msCoreStyle
        MS5["Módulo 5: IA & Recomendación<br><i>(Worker Asíncrono, Filtrado Híbrido, Explicabilidad)</i>"]:::msAiStyle
        MS6["Módulo 6: Analítica & Gobernanza<br><i>(Métricas de Destino, Alertas, Notificaciones)</i>"]:::msCoreStyle
    end

    APIGW -->|Valida Tokens / IAM| MS1
    APIGW -->|Enruta Catálogo| MS2
    APIGW -->|Enruta Reservas| MS3
    APIGW -->|Enruta Reseñas| MS4
    APIGW -->|Enruta Analítica| MS6

    subgraph EventBus["Bus de Mensajería & Eventos Asíncronos"]
        Broker["Message Broker<br><i>(RabbitMQ / Redis Streams — Pub/Sub)</i>"]:::brokerStyle
    end

    MS3 -.->|Publica: Reserva Creada/Confirmada| Broker
    MS4 -.->|Publica: Nueva Reseña| Broker
    Broker -.->|Consume Eventos de Preferencia| MS5
    Broker -.->|Consume Eventos de Correo/Aviso| MS6

    subgraph Persistencia["Persistencia Políglota FOSS (Database-per-Service)"]
        direction LR
        DB1[("PostgreSQL<br>IAM & Seguridad")]:::dbStyle
        DB2[("PostgreSQL + PostGIS<br>Catálogo & Capas Espaciales")]:::dbStyle
        DB3[("PostgreSQL<br>Reservas & Cupos")]:::dbStyle
        DB4[("MongoDB Community<br>Reseñas & Comentarios")]:::dbStyle
        Cache[("Redis / Valkey<br>Caché & Sesiones")]:::cacheStyle
    end

    MS1 --- DB1
    MS2 --- DB2
    MS3 --- DB3
    MS4 --- DB4
    MS1 & MS2 & MS3 --- Cache
```
</details>

#### Detalle de Responsabilidades por Módulo

![Detalle de Responsabilidades por Módulo](./Diagrama_Modulos_Responsabilidades.svg)

<details>
<summary><b>Ver especificación de código Mermaid de responsabilidades por módulo</b></summary>

```mermaid
flowchart LR
    classDef cardIAM fill:#eff6ff,stroke:#3b82f6,stroke-width:2px,color:#1e3a8a,font-size:12px;
    classDef cardCat fill:#f0fdf4,stroke:#10b981,stroke-width:2px,color:#064e3b,font-size:12px;
    classDef cardRes fill:#fefce8,stroke:#eab308,stroke-width:2px,color:#713f12,font-size:12px;
    classDef cardRev fill:#fff1f2,stroke:#f43f5e,stroke-width:2px,color:#881337,font-size:12px;
    classDef cardAI fill:#fdf4ff,stroke:#d946ef,stroke-width:2px,color:#701a75,font-size:12px;
    classDef cardGov fill:#f5f3ff,stroke:#8b5cf6,stroke-width:2px,color:#4c1d95,font-size:12px;

    subgraph M1["Módulo 1: Seguridad & IAM"]
        direction TB
        C1["• Autenticación OAuth2 / JWT<br>• Control de acceso RBAC<br>• Verificación de prestadores (UC37/28)<br>• Bitácora de auditoría inmutable<br>• Políticas de seguridad & rate limiting"]:::cardIAM
    end

    subgraph M2["Módulo 2: Catálogo & GIS"]
        direction TB
        C2["• Gestión de atractivos y eventos<br>• Búsqueda y filtros multicriterio<br>• Capas espaciales OpenStreetMap<br>• Fichas de prestadores"]:::cardCat
    end

    subgraph M3["Módulo 3: Reservas & Cupos"]
        direction TB
        C3["• Motor de cupos en tiempo real<br>• Ciclo de vida de solicitudes<br>• Historial del turista<br>• Panel de atención del prestador"]:::cardRes
    end

    subgraph M4["Módulo 4: Reseñas & Moderación"]
        direction TB
        C4["• Calificaciones y comentarios<br>• Respuestas de prestadores<br>• Pre-moderación heurística<br>• Cola de moderación administrativa"]:::cardRev
    end

    subgraph M5["Módulo 5: IA & Recomendación"]
        direction TB
        C5["• Procesamiento asíncrono de eventos<br>• Filtrado colaborativo / contenido<br>• Motor de explicabilidad (RNF-08)<br>• Inferencia con datos sintéticos"]:::cardAI
    end

    subgraph M6["Módulo 6: Analítica & Destino"]
        direction TB
        C6["• Indicadores de demanda turística<br>• Estimación de capacidad de carga<br>• Tableros para Entidad de Gestión<br>• Despacho de correos transaccionales"]:::cardGov
    end
```
</details>

##### 1. Módulo 1: Autenticación, Seguridad y Gestión de Identidades (IAM Service)
* **Propósito:** Centralizar el control de acceso, la autenticación perimetral y la trazabilidad de seguridad del ecosistema.
* **Componentes y Funcionalidades:**
  * **Autenticación Robusta:** Emisión, firma y verificación de tokens sin estado JWT (JSON Web Tokens) bajo estándares OAuth2 / OpenID Connect.
  * **Autorización Basada en Roles (RBAC):** Control estricto de privilegios para los roles `Turista`, `Prestador`, `Entidad` y `Admin`.
  * **Seguridad Criptográfica:** Hashing de contraseñas mediante **Argon2id** (o Bcrypt con factor de costo elevado) y protección contra ataques de fuerza bruta.
  * **Verificación de Prestadores (UC28 / UC37):** Almacenamiento seguro y gestión del flujo de aprobación de documentos legales (Registro Nacional de Turismo - RNT, RUT).
  * **Bitácora Centralizada de Auditoría (UC33 / RNF-10):** Registro inmutable de eventos críticos (intentos de acceso fallidos, cambios de privilegios, aprobaciones de prestadores, exportaciones de datos).
  * **Políticas de Privacidad (UC6):** Registro auditable de la aceptación explícita de la política de tratamiento de datos personales (Ley 1581 de 2012).

##### 2. Módulo 2: Catálogo y Geolocalización Turística (Catalog & GIS Service)
* **Propósito:** Administrar la información estructurada de atractivos, actividades culturales/ecológicas, eventos y prestadores.
* **Componentes y Funcionalidades:**
  * **Motor de Búsqueda y Filtros:** Consultas indexadas por categoría, rango de precios, ubicación geográfica y etiquetas de sostenibilidad (UC7, UC8, UC9).
  * **Integración GIS Abierta:** Almacenamiento de coordenadas espaciales con **PostGIS** y renderizado de mapas interactivos vectoriales mediante **OpenStreetMap** y librerías cliente libres (**Leaflet.js** / **MapLibre GL**) (UC16).
  * **Publicación de Oferta:** Flujos de creación y actualización de fichas de servicios para prestadores habilitados (UC17, UC18).

##### 3. Módulo 3: Disponibilidad y Gestión de Reservas (Bookings & Availability Service)
* **Propósito:** Gestionar el ciclo de vida de las solicitudes de reserva y el control de cupos en tiempo real.
* **Componentes y Funcionalidades:**
  * **Control de Disponibilidad:** Consulta atómica y bloqueo temporal de cupos para evitar sobreventas (*overbooking*) (UC10, UC19).
  * **Máquina de Estados de Reserva:** Gestión de estados: `Solicitada` $\rightarrow$ `Confirmada` $\rightarrow$ `Rechazada` $\rightarrow$ `Cancelada` $\rightarrow$ `Finalizada` (UC11, UC12, UC20).
  * **Paneles de Control:** Vistas de historial para turistas (UC13) y consolas de gestión de solicitudes para prestadores (UC20).

##### 4. Módulo 4: Anotaciones, Reseñas y Moderación (Reviews & Community Service)
* **Propósito:** Fomentar la retroalimentación comunitaria garantizando un ambiente seguro y veraz.
* **Componentes y Funcionalidades:**
  * **Calificaciones y Reseñas:** Registro de puntuaciones multidimensionales (1 a 5 estrellas) y comentarios detallados (UC15).
  * **Interacción del Prestador:** Soporte para respuestas públicas y réplicas de prestadores sobre las opiniones de sus servicios (UC21).
  * **Pre-moderación Heurística Embebida:** Filtro algorítmico ligero basado en listas de palabras ofensivas y reglas semánticas para marcar automáticamente reseñas sospechosas antes de su publicación o enviarlas a la cola de moderación humana (UC29).

##### 5. Módulo 5: Inteligencia Artificial y Recomendación Desacoplada (AI Recommendation Service)
* **Propósito:** Generar sugerencias personalizadas de atractivos y actividades sin penalizar el rendimiento del núcleo transaccional.
* **Componentes y Funcionalidades:**
  * **Consumo Asíncrono de Eventos:** El servicio escucha eventos del bus de mensajería (interacciones del turista, búsquedas, reservas previas) para actualizar vectores de preferencia.
  * **Algoritmo de Filtrado Híbrido:** Combinación de filtrado basado en contenido (características de atractivos) y filtrado colaborativo simplificado alimentado por datos sintéticos.
  * **Módulo de Explicabilidad (RNF-08):** Cada recomendación genera metadatos de justificación comprensibles para el usuario (ej. *"Recomendado porque te interesan actividades al aire libre cerca de Minca"*).

##### 6. Módulo 6: Analítica y Gobernanza del Destino (Analytics & Destination Governance Service)
* **Propósito:** Proveer inteligencia de negocios turística a la Entidad de Gestión y gestionar comunicaciones transaccionales.
* **Componentes y Funcionalidades:**
  * **Monitoreo de Demanda y Capacidad de Carga:** Agregación estadística de solicitudes y visitas para calcular índices de presión turística por zona (UC23, UC24).
  * **Generación de Reportes:** Tableros de control y exportación estructurada de datos (CSV/PDF) para planificación territorial (UC25, UC38).
  * **Alertas Oficiales y Notificaciones:** Emisión de avisos institucionales (UC26) y despacho asíncrono de correos electrónicos transaccionales de confirmación de reserva (UC36).

##### 7. Capa Transversal: API Gateway, Observabilidad y Middleware
* **Propósito:** Proteger el perímetro, gestionar el enrutamiento y supervisar la salud operacional de la infraestructura.
* **Componentes y Funcionalidades:**
  * **API Gateway (Nginx / Traefik):** Enrutamiento inteligente, terminación TLS/HTTPS, validación perimetral de cabeceras JWT, limitación de tasa (*Rate Limiting*) y políticas de CORS.
  * **Observabilidad Centralizada:** Métricas en tiempo real con **Prometheus** y tableros de visualización con **Grafana**.

---

#### 3.6.2 Estilo de Comunicación entre Componentes

Se implementa un **patrón híbrido** optimizado para balancear inmediatez y resiliencia:

1. **Comunicación Síncrona (REST / JSON sobre HTTPS):**
   * Empleada en operaciones donde el usuario requiere respuesta inmediata: autenticación, navegación del catálogo, consulta de disponibilidad y registro de reservas.
   * Documentada bajo el estándar OpenAPI 3.0.
2. **Comunicación Asíncrona Orientada a Eventos (Message Broker FOSS):**
   * Implementada con **RabbitMQ** (o Redis Streams) mediante el patrón Publicador/Suscriptor (*Pub/Sub*).
   * Desacopla tareas no críticas para el hilo principal: procesamiento del modelo de recomendación de IA, despacho de correos electrónicos de confirmación (UC36) y envío de eventos a la bitácora de auditoría (UC33).

---

#### 3.6.3 Persistencia de Datos Políglota (100% FOSS)

Cada microservicio gestiona su propio almacén de datos (*Database-per-Service*), garantizando desacople y evitando bloqueos entre esquemas:

* **PostgreSQL + PostGIS (Relacional & Geoespacial):** Base de datos principal para el Módulo 1 (IAM/Seguridad), Módulo 2 (Catálogo con consultas espaciales) y Módulo 3 (Reservas transaccionales con consistencia ACID).
* **MongoDB Community Edition (Documental NoSQL):** Almacén para el Módulo 4 (Anotaciones y Reseñas), permitiendo estructuras flexibles, comentarios anidados, respuestas y banderas dinámicas de moderación.
* **Redis / Valkey (En memoria & Caché):** Almacenamiento temporal de sesiones, listas negras de tokens JWT, control de cuotas de peticiones (*Rate Limiting*) y aceleración de consultas de catálogo frecuente.

---

#### 3.6.4 Stack Tecnológico y Coherencia con Software Libre (FOSS)

> [!NOTE]
> **Estado de Definición Tecnológica (Referencia Preliminar en Evaluación):**
> La selección de tecnologías, bases de datos y herramientas de desarrollo descritas en esta sección tiene un carácter **propositivo y referencial**, formulado para establecer una estructura lógica, coherencia de diseño y orden conceptual en este documento.
>
> **El stack tecnológico definitivo aún se encuentra en etapa de análisis y decisión por parte del equipo.** La selección final será evaluada formalmente durante la **Fase 2 (Comparación y Selección de Arquitectura)**, donde se sopesarán curvas de aprendizaje, compatibilidad, rendimiento y requerimientos específicos de implementación antes de congelar las herramientas definitivas.

La plataforma se concibe orientada íntegramente sobre tecnologías de código abierto (*Open Source*) con licencias permisivas (MIT, Apache 2.0, BSD, PostgreSQL, MPL 2.0), asegurando soberanía tecnológica, ausencia de costos de licenciamiento privativo y alta interoperabilidad.

| Capa Arquitectónica | Tecnología FOSS Propuesta (Referencial) | Licencia | Rol en la Solución |
|---|---|---|---|
| **API Gateway / Proxy** | **Nginx** o **Traefik** | BSD / MIT | Enrutamiento perimetral, SSL/TLS, Rate Limiting y CORS. |
| **Backend Core Services** | **Java OpenJDK / Spring Boot** o **TypeScript / NestJS** | GPLv2+CE / Apache 2.0 / MIT | Lógica de negocio de microservicios transaccionales. |
| **Backend IA Service** | **Python (FastAPI + Scikit-Learn + Pandas)** | BSD / PSF / Apache 2.0 | Microservicio asíncrono de recomendación explicable. |
| **Persistencia Relacional** | **PostgreSQL + PostGIS** | PostgreSQL License / GPL | Almacén transaccional y consultas geoespaciales. |
| **Persistencia NoSQL** | **MongoDB Community Edition** | SSPL / FOSS Compat. | Almacén semiestructurado de reseñas y comentarios. |
| **Caché & Sesiones** | **Redis** o **Valkey** | BSD-3-Clause | Caché de alta velocidad, rate limiting y sesiones. |
| **Message Broker** | **RabbitMQ** | MPL 2.0 | Bus de mensajería asíncrona para eventos desacoplados. |
| **Mapas & GIS** | **OpenStreetMap + Leaflet.js / MapLibre** | ODbL / BSD / MIT | Cartografía interactiva sin costo por consulta. |
| **Frontend Web** | **HTML5, CSS3 Vanilla, JavaScript / Vue.js** | MIT | Interfaz de usuario responsiva, accesible y bilingüe. |
| **Contenedores & Despliegue** | **Docker + Docker Compose** | Apache 2.0 | Estandarización de entornos de desarrollo y producción. |
| **Observabilidad** | **Prometheus + Grafana** | Apache 2.0 / AGPL | Telemetría, monitoreo de métricas y alertas del sistema. |
| **Seguridad / Criptografía** | **Librerías Argon2 / JWT (RFC 7519)** | Apache 2.0 / MIT | Cifrado de credenciales y tokens de acceso seguros. |

---

### 3.7 Modelo de datos preliminar

![Diagrama Entidad-Relación por Microservicio](./Diagrama_Modelo_Datos_ER.svg)

<details>
<summary><b>Ver especificación de código Mermaid del modelo de datos</b></summary>

```mermaid
erDiagram
    USUARIO ||--o{ DOCUMENTO_VERIFICACION : "adjunta para validación"
    USUARIO ||--o{ BITACORA_AUDITORIA : "registra eventos"
    
    USUARIO {
        uuid id PK "Identificador único"
        string email UK "Correo corporativo/personal"
        string password_hash "Cifrado Argon2id"
        enum rol "Turista, Prestador, Entidad, Admin"
        boolean email_verificado "Estado de verificación"
        boolean habeas_data_aceptado "Ley 1581"
        timestamp creado_en "Fecha de registro"
    }

    DOCUMENTO_VERIFICACION {
        uuid id PK "Identificador"
        uuid usuario_id FK "Relación con Usuario"
        string tipo_documento "RNT o RUT"
        string url_almacenamiento "Ruta S3/Storage"
        enum estado "Pendiente, Aprobado, Rechazado"
        timestamp fecha_subida "Fecha de carga"
    }

    BITACORA_AUDITORIA {
        uuid id PK "ID evento"
        uuid usuario_id FK "Actor causante"
        string accion "LOGIN_FAIL, ROLE_CHANGE, EXPORT"
        string ip_origen "Dirección IP"
        jsonb detalles "Metadatos contextuales"
        timestamp fecha "Marca temporal inmutable"
    }

    PRESTADOR_PERFIL ||--o{ ATRACTIVO_SERVICIO : "publica oferta"

    PRESTADOR_PERFIL {
        uuid id PK "ID perfil"
        uuid usuario_id FK "Relación con Usuario"
        string razon_social "Nombre comercial"
        string telefono "Contacto directo"
        string direccion "Ubicación física"
    }

    ATRACTIVO_SERVICIO {
        uuid id PK "ID del servicio"
        uuid prestador_id FK "Prestador dueño"
        string nombre "Título del atractivo/actividad"
        string descripcion "Detalle completo"
        string categoria "Playa, Naturaleza, Cultura, Gastronomia"
        point coordenadas_gis "PostGIS GeoPoint (Lat, Lon)"
        decimal tarifa_base "Precio de referencia COP"
        string[] imagenes_urls "Galería de imágenes"
    }

    ATRACTIVO_SERVICIO ||--o{ DISPONIBILIDAD_CUPO : "habilita cupos"
    ATRACTIVO_SERVICIO ||--o{ SOLICITUD_RESERVA : "recibe solicitudes"

    DISPONIBILIDAD_CUPO {
        uuid id PK "ID cupo"
        uuid servicio_id FK "Servicio asociado"
        date fecha "Día de operación"
        int cupos_totales "Capacidad máxima"
        int cupos_disponibles "Cupos restantes atómicos"
    }

    SOLICITUD_RESERVA {
        uuid id PK "ID reserva"
        uuid turista_id FK "Turista solicitante"
        uuid servicio_id FK "Servicio reservado"
        date fecha_reserva "Fecha solicitada"
        int numero_personas "Cantidad de asistentes"
        enum estado "Solicitada, Confirmada, Rechazada, Cancelada"
        timestamp fecha_creacion "Fecha de solicitud"
    }

    ATRACTIVO_SERVICIO ||--o{ RESENA_OPINION : "es evaluado con"

    RESENA_OPINION {
        string _id PK "MongoDB ObjectId"
        uuid servicio_id "Referencia a Servicio"
        uuid turista_id "Referencia a Turista"
        int puntuacion "Escala de 1 a 5 estrellas"
        string comentario "Opinión redactada"
        boolean contiene_lenguaje_sensible "Bandera pre-filtro"
        enum estado_moderacion "Publicado, En_Revision, Oculto"
        string respuesta_prestador "Réplica del operador"
        timestamp creado_en "Fecha de publicación"
    }

    RECOMENDACION_LOG {
        uuid id PK "ID de recomendación"
        uuid turista_id FK "Turista receptor"
        uuid servicio_id FK "Servicio sugerido"
        float puntaje_afinidad "Score inferido (0.0 - 1.0)"
        string justificacion_explicabilidad "Motivo legible (RNF-08)"
        timestamp fecha_generacion "Marca temporal"
    }
```
</details>

---

## 4. Verificación

### 4.1 Criterios de verificación por requerimiento

Conforme a las directrices de verificación del estándar ISO/IEC/IEEE 29148:2018, cada requerimiento funcional y no funcional cuenta con un método formal de calificación y un criterio cuantitativo de aceptación asociado:

| ID Requerimiento | Tipo | Método de Verificación | Criterio Formal de Aceptación / Aprobación |
|---|---|---|---|
| **RF-01** | Funcional | **Demostración** | Renderizado del catálogo completo de atractivos y servicios con datos maestros y filtros básicos sin requerir sesión iniciada. |
| **RF-02** | Funcional | **Prueba** | Ejecución de búsquedas combinadas multicriterio (geografía + precio + categoría) devolviendo resultados correctos con latencia $< 1.5$ s. |
| **RF-03** | Funcional | **Demostración** | Actualización atómica en el calendario de cupos reflejando inmediatamente la reserva o modificación de disponibilidad. |
| **RF-04** | Funcional | **Prueba** | Creación exitosa de la entidad `SOLICITUD_RESERVA` en estado `Solicitada`, visible simultáneamente en el panel del turista y en el del prestador. |
| **RF-05** | Funcional | **Demostración** | Formulario de prestador verificado que persiste y actualiza registros en `ATRACTIVO_SERVICIO` e impacta de inmediato el catálogo público. |
| **RF-06** | Funcional | **Prueba / Análisis** | Inferencia de recomendaciones personalizadas asociadas al perfil del turista, conteniendo el campo obligatorio `justificacion_explicabilidad` (RNF-08). |
| **RF-07** | Funcional | **Demostración** | Renderizado visual de tableros institucionales con agregaciones de demanda por sector y mapas de calor estimativos de capacidad de carga. |
| **RF-08** | Funcional | **Inspección / Demostración** | Flujo de incorporación y publicación de oferta para prestadores comunitarios completable en un máximo de 3 pasos interactivos sin fallos. |
| **RF-09** | Funcional | **Prueba** | Invocación no autenticada o con rol insuficiente a endpoints restringidos retorna HTTP 403 Forbidden y genera un registro en `BITACORA_AUDITORIA`. |
| **RF-10** | Funcional | **Demostración** | Conmutación entre Español e Inglés traduce el 100% de las cadenas estáticas de navegación y etiquetas de interfaz en menos de 100 ms. |
| **RF-11** | Funcional | **Prueba** | Despacho asíncrono y entrega efectiva de correo MIME multipart tras la confirmación de reserva (UC20) en un tiempo $\le 10$ segundos. |
| **RF-12** | Funcional | **Demostración** | Carga de archivos PDF/imagen (RNT y RUT) en almacenamiento seguro y transición de estado en panel administrativo de validación. |
| **RF-13** | Funcional | **Prueba** | Generación y descarga íntegra de archivos estructurados en formato CSV y PDF con métricas analíticas del destino sin errores de serialización. |
| **RNF-01** a **RNF-12** | No Funcional | **Prueba / Análisis** | Verificación empírica contra los escenarios formales de calidad (ESC-01 a ESC-07), pruebas de carga con k6/JMeter ($p95 < 2.0$s), auditorías WCAG 2.1 AA y despliegue reproducible en Docker Compose. |

---

## 5. Apéndices

### Apéndice A. Matriz de trazabilidad global

La trazabilidad integral de la plataforma vincula cada necesidad de los interesados con su materialización técnica en casos de uso, requerimientos, módulos de software y pruebas de calidad:

![Diagrama de Trazabilidad Global](./Diagrama_Trazabilidad_Global.svg)

<details>
<summary><b>Ver especificación de código Mermaid de trazabilidad</b></summary>

```mermaid
flowchart LR
    classDef stStyle fill:#eff6ff,stroke:#3b82f6,stroke-width:2px,color:#1e40af,font-weight:bold,rx:8px,ry:8px;
    classDef ucStyle fill:#f5f3ff,stroke:#8b5cf6,stroke-width:2px,color:#5b21b6,font-weight:bold,rx:8px,ry:8px;
    classDef reqStyle fill:#f0fdf4,stroke:#10b981,stroke-width:2px,color:#065f46,font-weight:bold,rx:8px,ry:8px;
    classDef modStyle fill:#fffbeb,stroke:#f59e0b,stroke-width:2px,color:#92400e,font-weight:bold,rx:8px,ry:8px;
    classDef escStyle fill:#ecfdf5,stroke:#059669,stroke-width:2px,color:#064e3b,font-weight:bold,rx:8px,ry:8px;

    ST["Stakeholders<br><i>(Turista, Prestador, Entidad, Admin)</i>"]:::stStyle
    UC["Casos de Uso<br><i>(UC1 - UC38)</i>"]:::ucStyle
    RF["Requerimientos<br><i>(RF-01 a 13 / RNF-01 a 12)</i>"]:::reqStyle
    MOD["Microservicios FOSS<br><i>(Módulos 1 a 6 + Gateway)</i>"]:::modStyle
    ESC["Escenarios de Calidad<br><i>(ESC-01 a ESC-07)</i>"]:::escStyle

    ST ==>|Originan| UC
    UC ==>|Especifican| RF
    RF ==>|Se implementan en| MOD
    MOD ==>|Se validan con| ESC
```
</details>

| Módulo Arquitectónico | Casos de Uso Asignados | Requerimientos Funcionales | Requerimientos No Funcionales | Escenarios de Verificación |
|---|---|---|---|---|
| **Módulo 1: Seguridad & IAM** | UC1, UC2, UC3, UC4, UC6, UC27, UC28, UC32, UC33, UC37 | RF-08, RF-09, RF-12 | RNF-04, RNF-10 | ESC-04, ESC-06 |
| **Módulo 2: Catálogo & GIS** | UC7, UC8, UC9, UC16, UC17, UC18 | RF-01, RF-02, RF-05 | RNF-02, RNF-03, RNF-06 | ESC-02, ESC-03 |
| **Módulo 3: Reservas & Cupos** | UC10, UC11, UC12, UC13, UC19, UC20 | RF-03, RF-04, RF-05 | RNF-02, RNF-06, RNF-11 | ESC-02, ESC-07 |
| **Módulo 4: Reseñas & Moderación** | UC15, UC21, UC29 | RF-01, RF-05 | RNF-01, RNF-05 | ESC-01, ESC-05 |
| **Módulo 5: IA & Recomendación** | UC14 | RF-06 | RNF-05, RNF-08 | ESC-05 |
| **Módulo 6: Analítica & Destino** | UC22, UC23, UC24, UC25, UC26, UC36, UC38 | RF-07, RF-11, RF-13 | RNF-01, RNF-03 | ESC-01, ESC-03 |
| **API Gateway & Observabilidad** | UC2, UC5, UC30, UC31 | Transversal | RNF-01, RNF-02, RNF-06, RNF-12 | ESC-01, ESC-02, ESC-04 |

---

### Apéndice B. Matriz de riesgos del proyecto

| ID | Categoría | Descripción del Riesgo | Impacto | Probabilidad | Estrategia de Mitigación Propuesta |
|---|---|---|---|---|---|
| **R-01** | **Técnico** | Curva de aprendizaje del equipo en orquestación de microservicios y colas asíncronas. | Alto | Media | Iniciar el desarrollo local con Docker Compose unificado antes de realizar cualquier despliegue en nube; establecer plantillas base para los microservicios. |
| **R-02** | **Seguridad** | Exposición de endpoints o fuga de datos sensibles de prestadores y turistas. | Crítico | Baja | Aplicación de arquitectura Zero-Trust interna, validación perimetral de JWT en API Gateway, cifrado Argon2id y auditorías automatizadas de código. |
| **R-03** | **Alcance** | Desviación del alcance por complejización innecesaria del módulo de Inteligencia Artificial. | Alto | Media | Congelamiento estricto del alcance en RF-06 (recomendación basada en filtrado híbrido con datos sintéticos y explicabilidad básica), descartando chatbots o visión artificial. |
| **R-04** | **Datos** | Falta de datasets históricos reales de visitantes en Santa Marta. | Medio | Alta | Generación controlada de datasets sintéticos enriquecidos con capas geográficas abiertas de OpenStreetMap y estadísticas de SITUR/MinCIT. |
| **R-05** | **Gestión** | Disponibilidad heterogénea de tiempo entre integrantes del equipo durante el semestre. | Alto | Media | Sprints cortos de 2 semanas con entregables modulares e independientes asignados 1:1 por microservicio, visibilizados en GitHub Projects. |

---

### Apéndice C. Lineamientos de mockups y prototipado

Para la **Fase 3 (Diseño Arquitectónico)**, se estructurarán prototipos interactivos de baja y media fidelidad en Figma cubriendo los flujos críticos del sistema:

1. **Flujo de Acceso y Consentimiento:** Pantalla de Registro con casilla obligatoria de Aceptación de Tratamiento de Datos (UC1/UC6) y Login bilingüe (UC2/UC5).
2. **Catálogo y Mapa Interactivo:** Vista de exploración con mapa OpenStreetMap integrado, capas de filtrado multicriterio y fichas resumidas (UC7, UC8, UC16).
3. **Ficha de Detalle y Disponibilidad:** Visualización de fotografías, tarifas, cupos en tiempo real y reseñas verificadas (UC9, UC10, UC15).
4. **Flujo Simplificado de Reserva:** Proceso guiado en 4 pasos (*Usabilidad RNF-11*): Selección de fecha/personas $\rightarrow$ Resumen de solicitud $\rightarrow$ Envío de reserva $\rightarrow$ Pantalla de confirmación y aviso de correo (UC11, UC36).
5. **Consola del Prestador:** Panel de control para registrar servicios (UC17), cargar documentos RNT (UC37), fijar cupos (UC19) y gestionar solicitudes de reserva entrantes (UC20).
6. **Tablero Institucional de la Entidad:** Panel analítico con indicadores de afluencia por sector, mapa de calor de demanda y herramientas de exportación (UC23, UC24, UC25, UC38).
