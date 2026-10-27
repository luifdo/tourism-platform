/** Presentación de fechas según el idioma de la interfaz (no es una regla de negocio). */
export const fmtDate = (iso, locale, opts = { weekday: 'long', day: 'numeric', month: 'long' }) =>
  new Intl.DateTimeFormat(locale, { ...opts, timeZone: 'UTC' }).format(new Date(`${iso}T12:00:00Z`))
