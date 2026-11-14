/**
 * Formulario de una oferta (UC17 registrar, UC18 editar). Traduce entre el formulario plano de la pantalla y el cuerpo
 * `ServicioGuardar` de catalog.yaml, y valida lo que el servicio exige para no mandar peticiones que sabemos que
 * responderán 400. Todo son funciones puras; los textos de las etiquetas los pone la interfaz con los códigos.
 */
export const TIPOS = Object.freeze({
  HOTEL: { categoria: 'ALOJAMIENTO', bloque: 'alojamiento' },
  HOSTAL: { categoria: 'ALOJAMIENTO', bloque: 'alojamiento' },
  POSADA_ECOHOTEL: { categoria: 'ALOJAMIENTO', bloque: 'alojamiento' },
  GLAMPING_CAMPING: { categoria: 'ALOJAMIENTO', bloque: 'alojamiento' },
  APARTAMENTO_TURISTICO: { categoria: 'ALOJAMIENTO', bloque: 'alojamiento' },
  RESTAURANTE: { categoria: 'GASTRONOMIA', bloque: 'gastronomia' },
  CAFE_BAR: { categoria: 'GASTRONOMIA', bloque: 'gastronomia' },
  EXPERIENCIA_GASTRONOMICA: { categoria: 'GASTRONOMIA', bloque: 'experiencia' },
  TOUR_GUIADO: { categoria: 'AVENTURA', bloque: 'experiencia' },
  SENDERISMO: { categoria: 'AVENTURA', bloque: 'experiencia' },
  DEPORTE_ACUATICO: { categoria: 'AVENTURA', bloque: 'experiencia' },
  AVISTAMIENTO: { categoria: 'NATURALEZA', bloque: 'experiencia' },
  RESERVA_PARQUE: { categoria: 'NATURALEZA', bloque: 'entrada' },
  ACCESO_PLAYA: { categoria: 'PLAYA', bloque: 'entrada' },
  ALQUILER_EQUIPO: { categoria: 'PLAYA', bloque: 'alquiler' },
  TOUR_CULTURAL: { categoria: 'CULTURA', bloque: 'experiencia' },
  EXPERIENCIA_COMUNITARIA: { categoria: 'CULTURA', bloque: 'experiencia' },
  MUSEO_SITIO: { categoria: 'CULTURA', bloque: 'entrada' },
  EVENTO_FESTIVAL: { categoria: 'CULTURA', bloque: 'entrada' },
  TRANSPORTE_MARITIMO: { categoria: 'TRANSPORTE', bloque: 'transporte' },
  TRASLADO_TERRESTRE: { categoria: 'TRANSPORTE', bloque: 'transporte' },
})
export const UNIDADES_TARIFA = Object.freeze(['POR_PERSONA', 'POR_NOCHE', 'POR_GRUPO', 'POR_UNIDAD', 'POR_HORA', 'POR_DIA'])

/**
 * Campos de cada bloque: [nombre, clase, obligatorio, opciones?].
 * Clases: txt (texto es/en), int, num, bool, hora, sel (una opción), multi (varias opciones), horas (lista de horas),
 * habitaciones, tarifas.  `bool`: null = no informado (no se envía).
 */
export const CAMPOS = Object.freeze({
  comunes: [['horario', 'txt'], ['incluye', 'txt'], ['no_incluye', 'txt'], ['accesible', 'bool'], ['mascotas', 'bool'], ['apto_ninos', 'bool'], ['practicas_sostenibles', 'txt']],
  alojamiento: [['check_in', 'hora', true], ['check_out', 'hora', true], ['habitaciones', 'habitaciones', true], ['amenidades', 'multi', false, ['WIFI', 'AIRE_ACONDICIONADO', 'VENTILADOR', 'AGUA_CALIENTE', 'PISCINA', 'PARQUEADERO', 'COCINA_COMPARTIDA', 'LAVANDERIA']], ['desayuno_incluido', 'bool']],
  experiencia: [['duracion_minutos', 'int', true], ['nivel_fisico', 'sel', true, ['BAJO', 'MEDIO', 'ALTO']], ['punto_encuentro', 'txt'], ['edad_minima', 'int'], ['grupo_maximo', 'int'], ['incluye_guia', 'bool'], ['incluye_transporte', 'bool'], ['incluye_equipo', 'bool'], ['que_llevar', 'txt'], ['requisitos', 'txt']],
  gastronomia: [['tipos_cocina', 'multi', true, ['CARIBENA', 'DE_MAR', 'COLOMBIANA', 'INTERNACIONAL', 'VEGETARIANA', 'CAFE_Y_POSTRES', 'COMIDA_RAPIDA']], ['opciones_dietarias', 'multi', false, ['VEGETARIANA', 'VEGANA', 'SIN_GLUTEN', 'SIN_LACTOSA']], ['precio_min_persona', 'num'], ['precio_max_persona', 'num'], ['requiere_reserva', 'bool'], ['puestos', 'int'], ['domicilio', 'bool']],
  entrada: [['tarifas', 'tarifas'], ['temporadas_cierre', 'txt'], ['reglas', 'txt'], ['servicios_en_sitio', 'multi', false, ['BANOS', 'DUCHAS', 'SALVAVIDAS', 'COMIDA', 'PARQUEADERO', 'CASILLEROS']]],
  alquiler: [['equipos', 'txt', true], ['deposito', 'num'], ['requiere_documento', 'bool']],
  transporte: [['origen', 'txt', true], ['destino', 'txt', true], ['duracion_minutos', 'int', true], ['capacidad_vehiculo', 'int', true], ['horarios_salida', 'horas'], ['incluye_chaleco_salvavidas', 'bool']],
})
export const TIPOS_HABITACION = Object.freeze(['PRIVADA', 'COMPARTIDA', 'DORMITORIO', 'SUITE', 'CABANA', 'CARPA'])
export const TIPOS_VISITANTE = Object.freeze(['GENERAL', 'NACIONAL', 'EXTRANJERO', 'NINO', 'ESTUDIANTE', 'ADULTO_MAYOR'])
export const MEDIOS_PAGO = Object.freeze(['EFECTIVO', 'TARJETA', 'TRANSFERENCIA'])
export const SENALES = Object.freeze(['CON_SENAL', 'INTERMITENTE', 'SIN_SENAL'])
export const RECOMENDACIONES_DINERO = Object.freeze(['EFECTIVO', 'DIGITAL', 'CUALQUIERA'])
const HORA = /^([01]\d|2[0-3]):[0-5]\d$/

const txt = (v) => ({ es: v?.es ?? '', en: v?.en ?? '' })
const textoLleno = (v) => String(v?.es ?? '').trim() !== ''

/** Bloque obligatorio de un tipo (`null` si el tipo no existe). */
export const bloqueDeTipo = (tipo) => TIPOS[tipo]?.bloque ?? null
/** Bloques que el formulario edita para un tipo: comunes, el del tipo y pagos. */
export const bloquesDeTipo = (tipo) => (TIPOS[tipo] ? ['comunes', TIPOS[tipo].bloque, 'pagos'] : ['comunes', 'pagos'])

function bloqueVacio(nombre) {
  const b = {}
  for (const [k, clase] of CAMPOS[nombre] ?? []) {
    b[k] = clase === 'txt' ? txt() : clase === 'bool' ? null : ['multi', 'habitaciones', 'tarifas'].includes(clase) ? [] : clase === 'horas' ? '' : ''
  }
  return b
}

/** Formulario vacío para registrar una oferta. */
export function formularioVacio() {
  const bloques = {}
  for (const n of Object.keys(CAMPOS)) bloques[n] = bloqueVacio(n)
  return {
    nombre: txt(), descripcion: txt(), tipo: '', ubicacion: { lat: '', lon: '' }, tarifa_base: '', unidad_tarifa: 'POR_PERSONA', capacidad_aforo_diario: '',
    imagenes_urls: [], bloques, pagos: { senal_internet: '', medios_pago: [], recomendacion_dinero: '' },
  }
}

const aTxtForm = (v) => (typeof v === 'string' ? { es: v, en: '' } : txt(v))

/** Formulario a partir de una oferta ya guardada (`ServicioEditable`: textos en ambos idiomas). */
export function formularioDeServicio(s) {
  const f = formularioVacio()
  f.nombre = txt(s.nombre); f.descripcion = txt(s.descripcion); f.tipo = s.tipo ?? ''
  f.ubicacion = { lat: s.ubicacion?.lat ?? '', lon: s.ubicacion?.lon ?? '' }
  f.tarifa_base = s.tarifa_base ?? ''; f.unidad_tarifa = s.unidad_tarifa ?? 'POR_PERSONA'; f.capacidad_aforo_diario = s.capacidad_aforo_diario ?? ''
  f.imagenes_urls = [...(s.imagenes_urls ?? [])]
  for (const [nombre, campos] of Object.entries(CAMPOS)) {
    const origen = s.atributos?.[nombre]
    if (!origen) continue
    for (const [k, clase] of campos) {
      const v = origen[k]
      if (v == null) continue
      if (clase === 'txt') f.bloques[nombre][k] = aTxtForm(v)
      else if (clase === 'horas') f.bloques[nombre][k] = (v ?? []).join(', ')
      else if (clase === 'habitaciones') f.bloques[nombre][k] = v.map((h) => ({ tipo: h.tipo, capacidad_personas: h.capacidad_personas, cantidad: h.cantidad ?? 1 }))
      else if (clase === 'tarifas') f.bloques[nombre][k] = v.map((x) => ({ tipo_visitante: x.tipo_visitante, valor: x.valor }))
      else f.bloques[nombre][k] = Array.isArray(v) ? [...v] : v
    }
  }
  const p = s.atributos?.pagos
  if (p) f.pagos = { senal_internet: p.senal_internet ?? '', medios_pago: [...(p.medios_pago ?? [])], recomendacion_dinero: p.recomendacion_dinero ?? '' }
  return f
}

const num = (v) => (v === '' || v == null ? null : Number(v))
const lleno = (v) => v !== '' && v != null

function aTextoApi(v) {
  const es = String(v?.es ?? '').trim()
  const en = String(v?.en ?? '').trim()
  return es ? { es, ...(en ? { en } : {}) } : null
}

function bloqueAApi(nombre, valores) {
  const salida = {}
  for (const [k, clase] of CAMPOS[nombre]) {
    const v = valores[k]
    switch (clase) {
      case 'txt': { const t = aTextoApi(v); if (t) salida[k] = t; break }
      case 'int': case 'num': if (lleno(v)) salida[k] = Number(v); break
      case 'bool': if (typeof v === 'boolean') salida[k] = v; break
      case 'hora': case 'sel': if (lleno(v)) salida[k] = v; break
      case 'multi': if (v?.length) salida[k] = [...new Set(v)]; break
      case 'horas': { const l = String(v ?? '').split(/[,\s]+/).filter(Boolean); if (l.length) salida[k] = [...new Set(l)]; break }
      case 'habitaciones': if (v?.length) salida[k] = v.map((h) => ({ tipo: h.tipo, capacidad_personas: Number(h.capacidad_personas), cantidad: Number(h.cantidad || 1) })); break
      case 'tarifas': if (v?.length) salida[k] = v.map((x) => ({ tipo_visitante: x.tipo_visitante, valor: Number(x.valor) })); break
    }
  }
  return salida
}

/**
 * Cuerpo `ServicioGuardar` a partir del formulario. `atributosPrevios` (al editar) conserva los bloques que el
 * formulario no maneja (p. ej. `pagos.credito` o `cajeros`) para que guardar no los borre.
 */
export function servicioAPayload(f, atributosPrevios = {}) {
  const bloque = bloqueDeTipo(f.tipo)
  const atributos = { ...atributosPrevios }
  const comunes = { ...(atributosPrevios.comunes ?? {}), ...bloqueAApi('comunes', f.bloques.comunes) }
  if (Object.keys(comunes).length) atributos.comunes = comunes; else delete atributos.comunes
  if (bloque) {
    const b = { ...(atributosPrevios[bloque] ?? {}), ...bloqueAApi(bloque, f.bloques[bloque]) }
    // un campo que el prestador vació se quita: la mezcla con lo previo solo conserva lo que el formulario no maneja
    for (const [k] of CAMPOS[bloque]) if (!(k in bloqueAApi(bloque, f.bloques[bloque]))) delete b[k]
    atributos[bloque] = b
  }
  // un cambio de tipo deja atrás los bloques del tipo anterior
  for (const n of Object.keys(CAMPOS)) if (n !== 'comunes' && n !== bloque) delete atributos[n]
  const p = f.pagos
  if (p.senal_internet && p.medios_pago.length && p.recomendacion_dinero) atributos.pagos = { ...(atributosPrevios.pagos ?? {}), senal_internet: p.senal_internet, medios_pago: [...new Set(p.medios_pago)], recomendacion_dinero: p.recomendacion_dinero }
  else delete atributos.pagos
  return {
    nombre: aTextoApi(f.nombre),
    descripcion: aTextoApi(f.descripcion),
    tipo: f.tipo,
    ubicacion: { lat: Number(f.ubicacion.lat), lon: Number(f.ubicacion.lon) },
    tarifa_base: Number(f.tarifa_base),
    unidad_tarifa: f.unidad_tarifa,
    capacidad_aforo_diario: Number(f.capacidad_aforo_diario),
    atributos,
    imagenes_urls: [...f.imagenes_urls],
  }
}

/** @returns {Record<string,string>} campo -> código de error (vacío si el formulario sirve). */
export function validarServicio(f) {
  const e = {}
  if (!textoLleno(f.nombre)) e.nombre = 'REQUERIDO'
  if (!textoLleno(f.descripcion)) e.descripcion = 'REQUERIDO'
  if (!TIPOS[f.tipo]) e.tipo = 'REQUERIDO'
  const lat = num(f.ubicacion.lat); const lon = num(f.ubicacion.lon)
  if (lat == null || lon == null || Number.isNaN(lat) || Number.isNaN(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) e.ubicacion = 'UBICACION_INVALIDA'
  const tarifa = num(f.tarifa_base)
  if (tarifa == null || Number.isNaN(tarifa) || tarifa < 0) e.tarifa_base = 'TARIFA_INVALIDA'
  if (!UNIDADES_TARIFA.includes(f.unidad_tarifa)) e.unidad_tarifa = 'REQUERIDO'
  const aforo = num(f.capacidad_aforo_diario)
  if (aforo == null || !Number.isInteger(aforo) || aforo < 1) e.capacidad_aforo_diario = 'AFORO_INVALIDO'

  const bloque = bloqueDeTipo(f.tipo)
  if (bloque) {
    const v = f.bloques[bloque]
    for (const [k, clase, obligatorio] of CAMPOS[bloque]) {
      const valor = v[k]
      const clave = `${bloque}.${k}`
      const vacioCampo = clase === 'txt' ? !textoLleno(valor) : clase === 'multi' || clase === 'habitaciones' ? !valor?.length : !lleno(valor)
      if (obligatorio && vacioCampo) { e[clave] = 'REQUERIDO'; continue }
      if (vacioCampo) continue
      if (clase === 'hora' && !HORA.test(valor)) e[clave] = 'HORA_INVALIDA'
      else if (clase === 'int' && (!Number.isInteger(Number(valor)) || Number(valor) < 1) && !(k === 'edad_minima' && Number(valor) === 0)) e[clave] = 'ENTERO_INVALIDO'
      else if (clase === 'num' && (Number.isNaN(Number(valor)) || Number(valor) < 0)) e[clave] = 'NUMERO_INVALIDO'
      else if (clase === 'horas' && String(valor).split(/[,\s]+/).filter(Boolean).some((h) => !HORA.test(h))) e[clave] = 'HORA_INVALIDA'
      else if (clase === 'habitaciones' && valor.some((h) => !h.tipo || !(Number(h.capacidad_personas) >= 1))) e[clave] = 'HABITACION_INVALIDA'
      else if (clase === 'tarifas' && valor.some((x) => !x.tipo_visitante || !(Number(x.valor) >= 0) || x.valor === '')) e[clave] = 'NUMERO_INVALIDO'
    }
    if (bloque === 'experiencia' && lleno(f.bloques.experiencia.grupo_maximo) && !e.capacidad_aforo_diario && Number(f.bloques.experiencia.grupo_maximo) > aforo) e['experiencia.grupo_maximo'] = 'GRUPO_MAYOR_QUE_AFORO'
    if (bloque === 'gastronomia') {
      const g = f.bloques.gastronomia
      if (lleno(g.precio_min_persona) && lleno(g.precio_max_persona) && Number(g.precio_min_persona) > Number(g.precio_max_persona)) e['gastronomia.precio_max_persona'] = 'PRECIO_INVERTIDO'
    }
  }
  const p = f.pagos
  const algunPago = p.senal_internet || p.medios_pago.length || p.recomendacion_dinero
  if (algunPago && !(p.senal_internet && p.medios_pago.length && p.recomendacion_dinero)) e.pagos = 'PAGOS_INCOMPLETOS'
  else if (p.recomendacion_dinero === 'DIGITAL' && !p.medios_pago.some((m) => m === 'TARJETA' || m === 'TRANSFERENCIA')) e.pagos = 'DIGITAL_SIN_MEDIO'
  else if (p.recomendacion_dinero === 'EFECTIVO' && !p.medios_pago.includes('EFECTIVO')) e.pagos = 'EFECTIVO_SIN_MEDIO'
  if (f.imagenes_urls.length > 10) e.imagenes = 'DEMASIADAS_IMAGENES'
  return e
}
