# Contexto del Módulo 5

> Módulo 5 · [Índice](./README.md)

Este documento explica qué se quiere crear, por qué, dónde se usará, cómo se quiere construir y qué se espera obtener. Los demás documentos de esta carpeta parten de aquí.

## Qué se quiere crear

`recommendation-service`: un **chatbot turístico** para la Plataforma Digital de Turismo de Santa Marta. El turista le escribe en lenguaje natural, en español o en inglés, y recibe recomendaciones personalizadas de atractivos, actividades y servicios, cada una con su justificación.

Es el Módulo 5 (IA & Recomendación) de los cinco microservicios de la plataforma. Corresponde al requerimiento RF-06 y al caso de uso UC14, y tiene como responsable a Alvaro Ospino.

El chatbot **no entrena ni aloja un modelo propio**. Usa un modelo de lenguaje externo a través de una API. Cuando necesita datos de la plataforma, el modelo los pide mediante **tools** (funciones de solo lectura) y el servicio las ejecuta. Son siete: búsqueda y detalle de servicios, disponibilidad, historial del turista, reseñas, capacidad de carga y alertas oficiales.

## Por qué se quiere crear

**El problema.** El turismo en Santa Marta se concentra en pocos destinos, como el Parque Tayrona y la Sierra Nevada. Esto satura las áreas protegidas, mientras que los destinos emergentes reciben poco. Además, el turista encuentra la información dispersa y poco confiable.

**La respuesta del módulo.**
* Orienta al turista con información real y consolidada de la plataforma, no de la memoria del modelo.
* Contribuye a dispersar los flujos de visitantes: prioriza destinos con baja presión de capacidad de carga y evita zonas con alertas oficiales activas.
* Explica sus recomendaciones (RNF-08), de modo que el turista entienda por qué se le sugiere algo.
* No favorece comercialmente a un operador sobre otro.

**Por qué es un microservicio aparte.** La IA es complementaria al núcleo transaccional (catálogo, reservas, reseñas, usuarios). Si el proveedor de IA falla, solo falla el chatbot; el resto de la plataforma sigue funcionando (ESC-01). Y se puede actualizar sin tumbar catálogo ni reservas (ESC-05).

## Dónde se usará

* **Quién lo usa:** el turista, nacional o internacional, desde la ventana de chat de la PWA.
* **Cómo llega:** `POST /api/recommendations/chat`, a través del API Gateway (Traefik), que valida el JWT y reenvía la identidad en el encabezado `X-Usuario-Id`.
* **Con quién se relaciona:** consulta por REST a catalog, booking y review, y al proveedor de IA. No participa en el bus de eventos de RabbitMQ.
* **Dónde corre:** como contenedor en Kubernetes (k3s), con al menos una réplica siempre activa. En desarrollo, con Docker Compose.
* **Qué guarda:** las recomendaciones entregadas en su propia base `recommendation_db` (PostgreSQL) y las sesiones de chat en Valkey (últimos 10 mensajes, 24 horas). No guarda el texto completo de las conversaciones.

## Cómo se quiere construir

* **Servicio independiente.** Con su propia base de datos, su propio contenedor y su propio contrato REST. Ningún servicio importa su código.
* **Python 3.12 + FastAPI**, con arquitectura hexagonal, igual que los otros cuatro servicios y siguiendo la estructura del monorepo.
* **Sin atarse a un proveedor de IA.** El servicio depende de una interfaz propia, y cada proveedor es un adaptador intercambiable. El equipo eligió **Groq** como primer proveedor (el SRS preveía Gemini; ver [Simulación y proveedor de IA](./08-simulacion.md)).
* **Desarrollo aislado.** Los demás servicios todavía no existen, así que se simulan con un contenedor mock. El proveedor de IA se conecta al final.
* **Trabajo en ramas propias** (`feature/modulo-ia` y una de desarrollo), sin tocar `develop`, `main` ni el trabajo de los demás.
* **Contrato primero.** Se define `contracts/openapi/recommendation.yaml` antes de escribir el código, como exige el proyecto.

## Qué se espera

**Resultado.** Un servicio que corre en su contenedor y responde conversaciones completas, con recomendaciones justificadas y registradas.

**Reglas que debe cumplir:**
* Solo lectura: no crea, modifica ni cancela reservas; orienta al turista hacia la plataforma.
* Solo recomienda servicios que salieron de una tool, y cada recomendación lleva su justificación.
* Responde únicamente sobre turismo en Santa Marta y la plataforma.
* La identidad del turista la define el servidor, nunca el modelo.
* Máximo 6 llamadas a tools por consulta, mensajes de hasta 1000 caracteres y límite de tasa.
* Al proveedor de IA solo se le envía el mínimo necesario: nunca nombre, correo ni documento del turista (Ley 1581).

**Calidad que se verificará:**
* `/health` y `/metrics` disponibles (RNF-12).
* Actualización sin errores 5xx en el núcleo (ESC-05).
* Unas 30 conversaciones tipo, pruebas de seguridad (inyección de instrucciones, datos de otro turista), de equidad y en ambos idiomas.

**Qué no se espera:** entrenar modelos, construir datasets de entrenamiento, reservar desde el chat, voz ni imágenes.

## Tiempos

* Construcción del prototipo (Fase 4): hasta el 1 de noviembre.
* Validación y cierre (Fase 5): del 2 al 14 de noviembre.
* Sustentación: del 15 al 17 de noviembre.

## Fuentes

* [SRS](../../Documents/Pages/Requirements_docIEEE.md): RF-06, RNF-05, RNF-08, RNF-12, ESC-05, UC14 y la descripción del Módulo 5.
* [Plan de Implementación](../../Documents/Pages/Plan_de_Implementacion.md): arquitectura, flujo 6, despliegue y pruebas.
* [Guía Técnica del Módulo 5](../../Documents/Pages/Guia_Tecnica_Modulo_IA.md): tools, validaciones y privacidad.
* [Registro de Decisiones Arquitectónicas](../../Documents/Pages/Registro_Decisiones_Arquitectonicas.md): ADR-010.

---
[Alcance →](./01-alcance.md)
