/*
 * Catálogo de demostración del simulador: tres experiencias reservables de Santa Marta, con sus textos en
 * español e inglés. Es lo que responde el adaptador simulado (VITE_API_MOCK=true, como la PWA de GitHub Pages);
 * con el backend real nada de esto se usa. Los ids son los que conoce el booking simulado (demoServices.js).
 */
const REGLA_CANCELACION = {
  es: 'Puedes cancelar hasta las 23:59 del día anterior a la reserva.',
  en: 'You can cancel until 11:59 pm the day before the booking.',
}

export const CATEGORIAS_DEMO = {
  PLAYA: { es: 'Playas', en: 'Beaches' },
  NATURALEZA: { es: 'Ríos y selva', en: 'Rivers and jungle' },
  CULTURA: { es: 'Cultura', en: 'Culture' },
}

export const DEMO_SERVICIOS = [
  {
    id: 'bahia-concha', categoria: 'PLAYA', tipo: 'DEPORTE_ACUATICO',
    tipoEtiqueta: { es: 'Deporte acuático', en: 'Water sports' },
    zona: { codigo: 'taganga', nombre: 'Taganga' }, ubicacion: { lat: 11.3245, lon: -74.095 },
    tarifaBase: 130000, capacidadDiaria: 20, ocupacion: 42, calificacion: 4.8, totalResenas: 36,
    prestador: { id: 'demo-prestador-1', razonSocial: 'Asociación de Pescadores de Taganga', telefono: '+57 300 000 0001' },
    es: {
      nombre: 'Santuario Coralino Bahía Concha',
      descripcion: 'Un recorrido a pie por el sendero hasta Bahía Concha para sembrar fragmentos de coral cuerno de ciervo junto a pescadores locales. Incluye charla de biología marina, equipo de snorkel y refrigerio.',
      politica: 'Cancelación gratuita hasta las 23:59 del día anterior. Pasado ese plazo, contacta al prestador.',
    },
    en: {
      nombre: 'Bahía Concha Coral Sanctuary',
      descripcion: 'A trail walk to Bahía Concha to plant staghorn coral fragments alongside local fishers. Includes a marine biology talk, snorkel gear and a snack.',
      politica: 'Free cancellation until 11:59 pm the day before. After that, contact the provider.',
    },
    alertas: [],
  },
  {
    id: 'quebrada-valencia', categoria: 'NATURALEZA', tipo: 'SENDERISMO',
    tipoEtiqueta: { es: 'Senderismo', en: 'Hiking' },
    zona: { codigo: 'guachaca', nombre: 'Guachaca' }, ubicacion: { lat: 11.288, lon: -73.95 },
    tarifaBase: 75000, capacidadDiaria: 15, ocupacion: 51, calificacion: 4.6, totalResenas: 21,
    prestador: { id: 'demo-prestador-2', razonSocial: 'Guías Comunitarios de Guachaca', telefono: '+57 300 000 0002' },
    es: {
      nombre: 'Cascadas de Quebrada Valencia',
      descripcion: 'Caminata botánica guiada por sabedores de la comunidad: reconocimiento de plantas medicinales, cascadas y pozas para refrescarse. Grupos pequeños para cuidar el cauce.',
      politica: 'Cancelación gratuita hasta las 23:59 del día anterior. La quebrada cierra los lunes.',
    },
    en: {
      nombre: 'Quebrada Valencia Waterfalls',
      descripcion: 'A botanical walk guided by community knowledge keepers: medicinal plants, waterfalls and natural pools. Small groups to protect the stream.',
      politica: 'Free cancellation until 11:59 pm the day before. The stream is closed on Mondays.',
    },
    alertas: [{
      id: 'demo-alerta-1', nivel: 'INFORMATIVA', fechaExpiracion: '2099-12-31T23:59:59Z',
      nivelEtiqueta: { es: 'Informativa', en: 'Informational' },
      mensaje: { es: 'El sendero cierra los lunes.', en: 'The trail is closed on Mondays.' },
    }],
  },
  {
    id: 'ruta-cacao', categoria: 'CULTURA', tipo: 'EXPERIENCIA_COMUNITARIA',
    tipoEtiqueta: { es: 'Experiencia comunitaria', en: 'Community experience' },
    zona: { codigo: 'rio-piedras', nombre: 'Río Piedras' }, ubicacion: { lat: 11.268, lon: -74.162 },
    tarifaBase: 195000, capacidadDiaria: 12, ocupacion: 28, calificacion: 4.9, totalResenas: 14,
    prestador: { id: 'demo-prestador-3', razonSocial: 'Finca Cacao Ancestral', telefono: '+57 300 000 0003' },
    es: {
      nombre: 'Ruta del Cacao y Sabiduría Textil',
      descripcion: 'Visita a una finca agroecológica de cacao criollo: del árbol al chocolate, con tejido tradicional y conversación sobre la cosmovisión de la Sierra Nevada.',
      politica: 'Cancelación gratuita hasta las 23:59 del día anterior.',
    },
    en: {
      nombre: 'Cacao Route and Textile Wisdom',
      descripcion: 'A visit to an agroecological heirloom-cacao farm: from tree to chocolate, with traditional weaving and a conversation about the Sierra Nevada worldview.',
      politica: 'Free cancellation until 11:59 pm the day before.',
    },
    alertas: [],
  },
]

export { REGLA_CANCELACION }
