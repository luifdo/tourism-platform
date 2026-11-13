/** Presentación de fechas según el idioma de la interfaz (no es una regla de negocio). */
export const fmtDate = (iso, locale, opts = { weekday: 'long', day: 'numeric', month: 'long' }) =>
  new Intl.DateTimeFormat(locale, { ...opts, timeZone: 'UTC' }).format(new Date(`${iso}T12:00:00Z`))

/** Fondo de las tarjetas y fichas sin foto: un degradado fijo por categoría (el listado no trae imágenes). */
const DEGRADADOS = {
  PLAYA: ['#0189C7', '#5D9A92'], NATURALEZA: ['#009767', '#0E3064'], CULTURA: ['#C7A781', '#5D9A92'],
  GASTRONOMIA: ['#F99C00', '#C7A781'], AVENTURA: ['#0E3064', '#0189C7'], ALOJAMIENTO: ['#5D9A92', '#0E3064'], TRANSPORTE: ['#0189C7', '#0E3064'],
}
export const degradado = (categoria) => {
  const [a, b] = DEGRADADOS[categoria] ?? ['#0189C7', '#5D9A92']
  return `linear-gradient(135deg, ${a}, ${b})`
}

/** Enlace a OpenStreetMap con el punto marcado (la plataforma solo usa mapas abiertos). */
export const urlMapa = ({ lat, lon }) => `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=16/${lat}/${lon}`
