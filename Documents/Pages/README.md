# Documentación — Plataforma Digital de Turismo Santa Marta

**Proyecto:** Plataforma Digital para la Gestión Integrada y Sostenible del Turismo en Santa Marta  
**Curso:** Arquitectura de Software  
**Programa:** Ingeniería de Sistemas — Universidad del Magdalena  

**Integrantes:** Luis Fernando Barraza Sanchez · Alvaro David Ospino Sanchez · Valentina Sarait Nieves Hernandez · Andres Felipe Gamero Sanchez · Juan Francisco Gonzalez Pacheco ([roles](./Requirements_docIEEE.md#apéndice-c-equipo-de-trabajo-y-asignación-de-roles))

---

## Documentos

| # | Documento | Contenido | Fase / Entregable |
|---|---|---|---|
| 1 | [Especificación de Requerimientos (SRS)](./Requirements_docIEEE.md) | Documento principal bajo ISO/IEC/IEEE 29148:2018: contexto, stakeholders, restricciones, requerimientos funcionales y no funcionales, casos de uso, escenarios de calidad, arquitectura, modelo de datos, verificación, trazabilidad, riesgos, roles y plan del proyecto (Apéndice D: proceso, cronograma y presupuesto). | Fase 1: Requerimientos |
| 2 | [Comparación y Selección de Alternativas Arquitectónicas](./Comparacion_Alternativas_Arquitectonicas.md) | Monolito modular vs. microservicios: tabla comparativa ponderada, decisión justificada y análisis de *trade-offs*. | Fase 2: Comparación Arquitectónica |
| 3 | [Registro de Decisiones Arquitectónicas (ADR)](./Registro_Decisiones_Arquitectonicas.md) | Metodología, estilo, tipo de base de datos, estrategia de conectividad (PWA), plataforma de despliegue (k3s), lenguaje, gateway, mensajería, observabilidad e IA. | Fase 3: Diseño Arquitectónico |
| 4 | [Plan de Implementación](./Plan_de_Implementacion.md) | Arquitectura interna por módulo, stack, contratos REST y de eventos, DDL, flujos clave, despliegue en k3s y estrategia de pruebas. | Fases 3 y 4 |
| 5 | [Guía Técnica del Módulo 5 (IA)](./Guia_Tecnica_Modulo_IA.md) | Guion de trabajo interno del chatbot con Gemini y tools: tools, validaciones, pruebas y dependencias con otros módulos. | Apoyo al equipo |

## Orden de lectura recomendado

1. **SRS**, secciones 1 a 3: qué problema se resuelve y qué debe cumplir el sistema (alto nivel, incluyendo la exclusión justificada de pagos en §1.2.1).
2. **Comparación de alternativas**: por qué se eligió la arquitectura de microservicios.
3. **Registro de decisiones (ADR)**: con qué plataforma, lenguaje, persistencia y estrategia de conectividad se materializa.
4. **SRS §3.6**: visión de la arquitectura seleccionada y fronteras de los 5 microservicios.
5. **Plan de Implementación**: cómo funciona cada servicio por dentro y cómo se despliega.
6. **SRS, Apéndice D**: cuándo y con qué recursos se construye.

## Diagramas

| Diagrama | Dónde se usa | Fuente |
|---|---|---|
| [Problemáticas y solución](./Diagrama_Problematicas_Solucion.svg) | SRS §2.1 | SVG original |
| [Casos de uso — vista general](./CasosDeUso_PlataformaTurismoSantaMarta.svg) | SRS §3.2.3 (referencia) | [`casos_uso_general.puml`](./fuentes/casos_uso_general.puml) |
| [Casos de uso — Turista](./CasosDeUso_Turista.svg) | SRS §3.2.3 | [`casos_uso_turista.puml`](./fuentes/casos_uso_turista.puml) |
| [Casos de uso — Prestador](./CasosDeUso_Prestador.svg) | SRS §3.2.3 | [`casos_uso_prestador.puml`](./fuentes/casos_uso_prestador.puml) |
| [Casos de uso — Entidad de Gestión](./CasosDeUso_Entidad.svg) | SRS §3.2.3 | [`casos_uso_entidad.puml`](./fuentes/casos_uso_entidad.puml) |
| [Casos de uso — Administrador](./CasosDeUso_Administrador.svg) | SRS §3.2.3 | [`casos_uso_administrador.puml`](./fuentes/casos_uso_administrador.puml) |
| [Arquitectura de microservicios](./Diagrama_Arquitectura_Microservicios.svg) | SRS §3.6.1, Plan §2.1 | [`generar_svg_arquitectura.py`](./fuentes/generar_svg_arquitectura.py) |
| [Responsabilidades por módulo](./Diagrama_Modulos_Responsabilidades.svg) | SRS §3.6.1 | [`generar_svg_arquitectura.py`](./fuentes/generar_svg_arquitectura.py) |
| [Máquina de estados de la reserva](./Diagrama_Maquina_Estados_Reserva.svg) | SRS §3.6.1, Plan §6.4 | [`maquina_estados_reserva.mmd`](./fuentes/maquina_estados_reserva.mmd) |
| [Despliegue — infraestructura](./Diagrama_Despliegue_Kubernetes.svg) | SRS §3.6.5, Plan §7.2 | [`despliegue_k3s.puml`](./fuentes/despliegue_k3s.puml) |
| [Despliegue — Turista](./Diagrama_Despliegue_Turista.svg) | SRS §3.6.5 | [`despliegue_turista.puml`](./fuentes/despliegue_turista.puml) |
| [Despliegue — Prestador](./Diagrama_Despliegue_Prestador.svg) | SRS §3.6.5 | [`despliegue_prestador.puml`](./fuentes/despliegue_prestador.puml) |
| [Despliegue — Entidad de Gestión](./Diagrama_Despliegue_Entidad.svg) | SRS §3.6.5 | [`despliegue_entidad.puml`](./fuentes/despliegue_entidad.puml) |
| [Despliegue — Administrador](./Diagrama_Despliegue_Administrador.svg) | SRS §3.6.5 | [`despliegue_administrador.puml`](./fuentes/despliegue_administrador.puml) |
| [Paquetes de un microservicio](./Diagrama_Paquetes_Microservicio.svg) | Plan §2.2 | [`paquetes_microservicio.puml`](./fuentes/paquetes_microservicio.puml) |
| [Modelo de datos entidad-relación](./Diagrama_Modelo_Datos_ER.svg) | SRS §3.7 | [`modelo_datos_er.mmd`](./fuentes/modelo_datos_er.mmd) |
| [Trazabilidad global](./Diagrama_Trazabilidad_Global.svg) | SRS Apéndice A | [`generar_svg_gestion.py`](./fuentes/generar_svg_gestion.py) |
| [Cronograma (Gantt)](./Diagrama_Cronograma_Gantt.svg) | SRS Apéndice D | [`generar_svg_gestion.py`](./fuentes/generar_svg_gestion.py) |
| [Distribución del presupuesto (Escenarios A y B)](./Diagrama_Distribucion_Presupuesto.svg) | SRS Apéndice D | [`generar_svg_gestion.py`](./fuentes/generar_svg_gestion.py) |

Para regenerar los diagramas después de editar una fuente, ver [`fuentes/generar_diagramas.sh`](./fuentes/generar_diagramas.sh).
