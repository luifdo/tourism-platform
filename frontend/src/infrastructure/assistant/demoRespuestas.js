/*
 * Conocimiento del asistente simulado: los mismos servicios de demostración del catálogo simulado
 * (data/mock.js), con el nombre, la justificación y las palabras que los activan en cada idioma.
 * El servicio real consulta catalog, booking y review con herramientas; aquí es solo una coincidencia de palabras.
 */
export const DEMO_CATALOGO = [
  {
    id: 'bahia-concha',
    nombre: { es: 'Santuario Coralino Bahía Concha', en: 'Bahía Concha Coral Sanctuary' },
    palabras: ['playa', 'mar', 'snorkel', 'coral', 'bucear', 'buceo', 'nadar', 'taganga', 'pescador', 'beach', 'sea', 'swim', 'diving', 'reef', 'fisher'],
    justificacion: {
      es: 'Es una experiencia de mar con siembra de corales junto a pescadores locales, con equipo de snorkel incluido y acceso por sendero.',
      en: 'A sea experience planting corals alongside local fishers, with snorkel gear included and access by trail.',
    },
  },
  {
    id: 'quebrada-valencia',
    nombre: { es: 'Cascadas de Quebrada Valencia', en: 'Quebrada Valencia Waterfalls' },
    palabras: ['naturaleza', 'cascada', 'rio', 'quebrada', 'senderismo', 'caminata', 'caminar', 'plantas', 'flora', 'botanic', 'nature', 'waterfall', 'river', 'hike', 'hiking', 'trek', 'plants'],
    justificacion: {
      es: 'Es una caminata botánica guiada por sabedores de la comunidad, con cascadas y pozas, en grupos pequeños para cuidar el cauce.',
      en: 'A botanical walk led by community knowledge-keepers, with waterfalls and pools, in small groups to protect the stream.',
    },
  },
  {
    id: 'ruta-cacao',
    nombre: { es: 'Ruta del Cacao y Sabiduría Textil', en: 'Cacao and Textile Wisdom Route' },
    palabras: ['cultura', 'cacao', 'chocolate', 'textil', 'tejido', 'comunidad', 'finca', 'lluvia', 'llover', 'llueve', 'culture', 'cultural', 'cocoa', 'weave', 'farm', 'community', 'rain', 'rainy'],
    justificacion: {
      es: 'Es una visita a una finca agroecológica con tejido tradicional y conversación sobre la Sierra Nevada; casi toda la actividad es bajo techo, así que sirve cuando llueve.',
      en: 'A visit to an agroecological farm with traditional weaving and conversation about the Sierra Nevada; most of it is under cover, so it works when it rains.',
    },
  },
]

const SALUDOS = ['hola', 'buenas', 'buenos dias', 'buenas tardes', 'hello', 'hi', 'hey', 'good morning', 'good afternoon']

const TEXTOS = {
  es: {
    saludo: '¡Hola! Cuéntame qué te gustaría hacer en Santa Marta (playa, naturaleza, cultura…) y te recomiendo experiencias del catálogo.',
    sinCoincidencia: 'Aún no sé qué experiencia encaja contigo. ¿Prefieres mar, naturaleza o cultura? Puedes contarme también cuántas personas son o si llueve.',
    recomienda: (nombres) => `Con lo que me cuentas, te sugiero: ${nombres}. Abre la ficha para ver la disponibilidad y solicitar tu reserva; yo solo oriento, no creo ni cancelo reservas.`,
  },
  en: {
    saludo: 'Hi! Tell me what you would like to do in Santa Marta (beach, nature, culture…) and I will recommend experiences from the catalog.',
    sinCoincidencia: 'I do not know yet which experience suits you. Do you prefer sea, nature or culture? You can also tell me how many people are coming or whether it is raining.',
    recomienda: (nombres) => `Based on what you tell me, I suggest: ${nombres}. Open the listing to check availability and request your booking; I only guide you, I never create or cancel bookings.`,
  },
}

const normalizar = (s) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
const tokens = (s) => normalizar(s).split(/[^a-z0-9ñ]+/).filter(Boolean)

/** @returns {{ respuesta: string, recomendaciones: {servicio_id, nombre, justificacion_explicabilidad}[] }} */
export function responderDemo(mensaje, idioma, catalogo = DEMO_CATALOGO) {
  const lang = idioma === 'en' ? 'en' : 'es'
  const texto = normalizar(mensaje)
  const palabras = new Set(tokens(mensaje))
  const coinciden = catalogo
    .map((s) => ({ s, puntos: s.palabras.filter((p) => palabras.has(normalizar(p)) || (p.length > 4 && texto.includes(normalizar(p)))).length }))
    .filter((x) => x.puntos > 0)
    .sort((a, b) => b.puntos - a.puntos)
    .slice(0, 2)
    .map((x) => x.s)

  if (!coinciden.length) {
    const saludo = SALUDOS.some((g) => (g.includes(' ') ? texto.includes(g) : palabras.has(g)))
    return { respuesta: TEXTOS[lang][saludo ? 'saludo' : 'sinCoincidencia'], recomendaciones: [] }
  }
  return {
    respuesta: TEXTOS[lang].recomienda(coinciden.map((s) => s.nombre[lang]).join(lang === 'en' ? ' and ' : ' y ')),
    recomendaciones: coinciden.map((s) => ({ servicio_id: s.id, nombre: s.nombre[lang], justificacion_explicabilidad: s.justificacion[lang] })),
  }
}
