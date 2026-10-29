# Alcance

> Módulo 5 · [Índice](./README.md)

**Entra:**
* `Dockerfile` de `recommendation-service`.
* Un `docker-compose.yml` propio del servicio, dentro de `services/recommendation-service/`, que levanta el servicio, su base de datos, Valkey y los simuladores.
* Simulación de los servicios catalog, booking y review.
* Conexión con el proveedor de IA a través de una interfaz propia, sin atarse a un proveedor concreto.

**Queda fuera (para después):**
* Integración con `infra/docker-compose.yml`. El servicio corre de forma independiente y esos archivos son del arquitecto (@luifdo).
* Manifiestos de Kubernetes (k3s), HPA y NetworkPolicy.
* Pipeline de CI que publica la imagen.
* Conexión con un proveedor de IA concreto (el elegido es Groq; se conecta en la Fase 5 con la clave que proporcione el equipo).

---
[← Contexto del Módulo 5](./00-contexto.md) · [Arquitectura local →](./02-arquitectura-local.md)
