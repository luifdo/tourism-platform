# Documentación — Plataforma Digital de Turismo Santa Marta

**Proyecto:** Plataforma Digital para la Gestión Integrada y Sostenible del Turismo en Santa Marta  
**Curso:** Arquitectura de Software  
**Programa:** Ingeniería de Sistemas — Universidad del Magdalena  

**Integrantes:** Luis Fernando Barraza Sanchez · Alvaro David Ospino Sanchez · Valentina Sarait Nieves Hernandez · Andres Felipe Gamero Sanchez · Juan Francisco Gonzalez Pacheco ([roles](./Requirements_docIEEE.md#apéndice-d-equipo-de-trabajo-y-asignación-de-roles))

---

## Documentos

| # | Documento | Contenido | Fase / Entregable |
|---|---|---|---|
| 1 | [Especificación de Requerimientos (SRS)](./Requirements_docIEEE.md) | Documento principal bajo ISO/IEC/IEEE 29148:2018: contexto, stakeholders, restricciones, requerimientos funcionales y no funcionales, casos de uso, escenarios de calidad, arquitectura, modelo de datos, verificación, trazabilidad, riesgos, roles y plan del proyecto. | Fase 1: Requerimientos |
| 2 | [Plan de Desarrollo de Software](./Plan_de_Desarrollo_de_Software.md) | Equipo y roles, cronograma de 14 semanas, metodología Scrum y su justificación, modelo de negocio y presupuestos (USD 6.900 / USD 20.000). | Gestión del proyecto |
| 3 | [Comparación y Selección de Alternativas Arquitectónicas](./Comparacion_Alternativas_Arquitectonicas.md) | Monolito modular vs. microservicios: tabla comparativa ponderada, decisión justificada y análisis de *trade-offs*. | Fase 2: Comparación Arquitectónica |

## Orden de lectura recomendado

1. **SRS**, secciones 1 a 3: qué problema se resuelve y qué debe cumplir el sistema (alto nivel, incluyendo la exclusión justificada de pagos en §1.2.1).
2. **Comparación de alternativas**: por qué se eligió la arquitectura de microservicios.
3. **SRS §3.6**: visión de arquitectura seleccionada y fronteras de los 5 microservicios.
4. **Plan de Desarrollo** (o SRS, Apéndice E): cómo, cuándo y con qué recursos se construye.

## Diagramas

| Diagrama | Dónde se usa |
|---|---|
| [Problemáticas y solución](./Diagrama_Problematicas_Solucion.svg) | SRS §2.1 |
| [Casos de uso — vista general](./CasosDeUso_PlataformaTurismoSantaMarta.svg) | SRS §3.2.3 (referencia; las vistas por actor están en el SRS) |
| [Arquitectura de microservicios](./Diagrama_Arquitectura_Microservicios.svg) | SRS §3.6.1 |
| [Responsabilidades por módulo](./Diagrama_Modulos_Responsabilidades.svg) | SRS §3.6.1 |
| [Modelo de datos entidad-relación](./Diagrama_Modelo_Datos_ER.svg) | SRS §3.7 |
| [Trazabilidad global](./Diagrama_Trazabilidad_Global.svg) | SRS Apéndice A |
| [Cronograma (Gantt)](./Diagrama_Cronograma_Gantt.svg) | Plan §2.1 y SRS Apéndice E |
| [Distribución del presupuesto](./Diagrama_Distribucion_Presupuesto.svg) | Plan §5 |
