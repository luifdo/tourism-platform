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

/** Atributos de cada servicio de demostración, con la forma del contrato y los textos ya en cada idioma. */
export const ATRIBUTOS_DEMO = {
  'bahia-concha': {
    es: {
      etiquetas: { MEDIO: 'Medio', CON_SENAL: 'Con señal', EFECTIVO: 'Efectivo', TARJETA: 'Tarjeta' },
      atributos: {
        comunes: { horario: 'Salida a las 8:00 a. m., regreso hacia el mediodía', incluye: 'Equipo de snorkel, charla de biología marina y refrigerio', no_incluye: 'Transporte hasta el sendero', idiomas_atencion: ['es', 'en'], apto_ninos: true, practicas_sostenibles: 'Solo se siembra coral con aval del grupo de restauración' },
        experiencia: { duracion_minutos: 240, nivel_fisico: 'MEDIO', punto_encuentro: 'Playa principal de Taganga, frente al muelle', grupo_maximo: 20, incluye_guia: true, incluye_equipo: true, que_llevar: 'Protector solar biodegradable, toalla y agua', requisitos: 'Saber nadar' },
        pagos: { senal_internet: 'CON_SENAL', medios_pago: ['EFECTIVO', 'TARJETA'] },
      },
    },
    en: {
      etiquetas: { MEDIO: 'Medium', CON_SENAL: 'Has signal', EFECTIVO: 'Cash', TARJETA: 'Card' },
      atributos: {
        comunes: { horario: 'Departs at 8:00 am, back around noon', incluye: 'Snorkel gear, a marine biology talk and a snack', no_incluye: 'Transport to the trailhead', idiomas_atencion: ['es', 'en'], apto_ninos: true, practicas_sostenibles: 'Coral is only planted with the restoration group’s approval' },
        experiencia: { duracion_minutos: 240, nivel_fisico: 'MEDIO', punto_encuentro: 'Main beach of Taganga, in front of the pier', grupo_maximo: 20, incluye_guia: true, incluye_equipo: true, que_llevar: 'Biodegradable sunscreen, towel and water', requisitos: 'Be able to swim' },
        pagos: { senal_internet: 'CON_SENAL', medios_pago: ['EFECTIVO', 'TARJETA'] },
      },
    },
  },
  'quebrada-valencia': {
    es: {
      etiquetas: { MEDIO: 'Medio', SIN_SENAL: 'Sin señal', EFECTIVO: 'Efectivo' },
      atributos: {
        comunes: { horario: 'Martes a domingo, desde las 7:00 a. m.', incluye: 'Guía comunitario y seguro de accidentes', idiomas_atencion: ['es'], mascotas: false },
        experiencia: { duracion_minutos: 300, nivel_fisico: 'MEDIO', punto_encuentro: 'Entrada de la vereda, en Guachaca', edad_minima: 8, grupo_maximo: 15, incluye_guia: true, que_llevar: 'Calzado cerrado, repelente y agua' },
        pagos: { senal_internet: 'SIN_SENAL', medios_pago: ['EFECTIVO'] },
      },
    },
    en: {
      etiquetas: { MEDIO: 'Medium', SIN_SENAL: 'No signal', EFECTIVO: 'Cash' },
      atributos: {
        comunes: { horario: 'Tuesday to Sunday, from 7:00 am', incluye: 'Community guide and accident insurance', idiomas_atencion: ['es'], mascotas: false },
        experiencia: { duracion_minutos: 300, nivel_fisico: 'MEDIO', punto_encuentro: 'Village entrance, in Guachaca', edad_minima: 8, grupo_maximo: 15, incluye_guia: true, que_llevar: 'Closed shoes, insect repellent and water' },
        pagos: { senal_internet: 'SIN_SENAL', medios_pago: ['EFECTIVO'] },
      },
    },
  },
  'ruta-cacao': {
    es: {
      etiquetas: { BAJO: 'Bajo', CON_SENAL: 'Con señal', EFECTIVO: 'Efectivo', TRANSFERENCIA: 'Transferencia' },
      atributos: {
        comunes: { horario: 'Todos los días, 9:00 a. m. y 2:00 p. m.', incluye: 'Degustación de chocolate y taller de tejido', idiomas_atencion: ['es', 'en'], accesible: true, apto_ninos: true },
        experiencia: { duracion_minutos: 180, nivel_fisico: 'BAJO', punto_encuentro: 'Finca Cacao Ancestral, kilómetro 12 vía a Río Piedras', salidas_por_dia: 2, grupo_minimo: 2, grupo_maximo: 12, incluye_guia: true, idiomas_guia: ['es', 'en'] },
        pagos: { senal_internet: 'CON_SENAL', medios_pago: ['EFECTIVO', 'TRANSFERENCIA'] },
      },
    },
    en: {
      etiquetas: { BAJO: 'Low', CON_SENAL: 'Has signal', EFECTIVO: 'Cash', TRANSFERENCIA: 'Bank transfer' },
      atributos: {
        comunes: { horario: 'Every day, 9:00 am and 2:00 pm', incluye: 'Chocolate tasting and weaving workshop', idiomas_atencion: ['es', 'en'], accesible: true, apto_ninos: true },
        experiencia: { duracion_minutos: 180, nivel_fisico: 'BAJO', punto_encuentro: 'Finca Cacao Ancestral, kilometer 12 on the road to Río Piedras', salidas_por_dia: 2, grupo_minimo: 2, grupo_maximo: 12, incluye_guia: true, idiomas_guia: ['es', 'en'] },
        pagos: { senal_internet: 'CON_SENAL', medios_pago: ['EFECTIVO', 'TRANSFERENCIA'] },
      },
    },
  },
}

export { REGLA_CANCELACION }
