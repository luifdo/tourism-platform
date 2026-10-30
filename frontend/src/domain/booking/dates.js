/*
 * Fechas del dominio de reservas. La unidad de reserva es el DÍA y todas las horas se calculan
 * en America/Bogota (booking.yaml). Funciones puras: el "ahora" entra siempre como parámetro.
 */
const TZ = 'America/Bogota'
const ymd = new Intl.DateTimeFormat('en-CA', { timeZone: TZ })

/** Fecha de hoy en Bogotá, 'YYYY-MM-DD' */
export const today = (now = new Date()) => ymd.format(now)

export const addDays = (iso, n) => {
  const d = new Date(`${iso}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

export const tomorrow = (now = new Date()) => addDays(today(now), 1)

/** 1 = lunes … 7 = domingo */
export const weekday = (iso) => ((new Date(`${iso}T12:00:00Z`).getUTCDay() + 6) % 7) + 1

export const monthKey = (iso) => iso.slice(0, 7)

export const daysInMonth = (key) => new Date(Date.UTC(+key.slice(0, 4), +key.slice(5, 7), 0)).getUTCDate()

/** Instante exacto en que empieza el día `iso` en Bogotá (UTC-5, sin horario de verano) */
export const startOfDay = (iso) => new Date(`${iso}T00:00:00-05:00`)
