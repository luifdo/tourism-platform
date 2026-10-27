// DATOS DE EJEMPLO para maquetar. Se reemplazan por las respuestas del Gateway:
//   experiencias -> GET /api/catalog/buscar   (RF-01, RF-02)
//   aforo        -> demanda_diaria / capacidad_aforo_diario (UC24)
export const experiences = [
  { id: 'bahia-concha', cat: 'Playa', km: 8.4, zone: 'Taganga', fee: 130000, aforo: 42, from: '#0189C7', to: '#5D9A92' },
  { id: 'quebrada-valencia', cat: 'Naturaleza', km: 32.1, zone: 'Guachaca', fee: 75000, aforo: 51, from: '#009767', to: '#0E3064' },
  { id: 'ruta-cacao', cat: 'Cultura', km: 18.5, zone: 'Río Piedras', fee: 195000, aforo: 28, from: '#C7A781', to: '#5D9A92' },
]

export const places = [
  { id: 'bahia-concha', lat: 11.3245, lng: -74.0950, aforo: 42 },
  { id: 'rio-piedras', lat: 11.2680, lng: -74.1620, aforo: 28 },
  { id: 'don-diego', lat: 11.3140, lng: -73.7160, aforo: 68 },
]

export const routes = [
  { id: 1, icon: 'hike', days: 3 },
  { id: 2, icon: 'kayak', days: 1 },
  { id: 3, icon: 'dive', days: 2 },
]

// Umbrales de DESIGN.md: < 60 % seguro, 60–85 % moderado, > 85 % saturado
export const level = (pct) => (pct < 60 ? 'ok' : pct <= 85 ? 'mid' : 'high')

// Ficha del servicio (RF-01, UC9). Reemplazar por GET /api/catalog/servicios/{id}
export const providers = {
  'bahia-concha': { name: 'Asociación de Pescadores de Taganga', phone: '+57 300 000 0001', rnt: '48291' },
  'quebrada-valencia': { name: 'Guías Comunitarios de Guachaca', phone: '+57 300 000 0002', rnt: '19034' },
  'ruta-cacao': { name: 'Finca Cacao Ancestral', phone: '+57 300 000 0003', rnt: '61822' },
}
export const capacity = { 'bahia-concha': 20, 'quebrada-valencia': 15, 'ruta-cacao': 12 }
export const findService = (id) => experiences.find((e) => e.id === id) ?? null
