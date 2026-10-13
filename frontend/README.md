# Frontend Web (PWA)

Responsable: Juan Francisco Gonzalez Pacheco (@JuanFranG)

Aplicación web progresiva en **Vue.js 3 + Workbox**: responsiva, bilingüe (ES/EN, RF-10), accesible (WCAG 2.1 AA, RNF-07) y con operación sin conexión (RNF-13, ADR-004). Consume únicamente la API del Gateway, nunca los servicios directamente.

* **Catálogo sin conexión:** caché del catálogo ya consultado (*stale-while-revalidate*) con la fecha de la última actualización; solo las teselas del mapa ya visualizadas.
* **Formularios diferidos:** perfil, reseña, oferta y cupos se guardan en IndexedDB como "Pendiente de envío" y se envían al recuperar la conexión, con `Idempotency-Key`.
* **Requieren conexión:** solicitar y confirmar reservas.

Detalle en el [Plan de Implementación](../Documents/Pages/Plan_de_Implementacion.md) §6.8.
