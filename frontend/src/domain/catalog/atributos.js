/**
 * Atributos de un servicio (contrato: AtributosServicio). El catálogo los manda en bloques según el tipo de servicio;
 * aquí se ordenan en secciones y filas listas para mostrar. No sabe de idiomas: las filas llevan el nombre del
 * campo (la interfaz lo traduce) y el valor ya viene en el idioma pedido (textos) o como código (las etiquetas del
 * servicio traducen los códigos).
 *
 * Cada campo es [nombre, clase]. Clases: texto, lista (textos o códigos), codigo, si-no, minutos, dinero, hora, numero.
 */
const BLOQUES = [
  ['comunes', [['horario', 'texto'], ['incluye', 'texto'], ['no_incluye', 'texto'], ['idiomas_atencion', 'idiomas'], ['accesible', 'si-no'], ['mascotas', 'si-no'], ['apto_ninos', 'si-no'], ['practicas_sostenibles', 'texto'], ['certificacion_sostenible', 'texto']]],
  ['alojamiento', [['check_in', 'hora'], ['check_out', 'hora'], ['habitaciones', 'habitaciones'], ['amenidades', 'lista'], ['desayuno_incluido', 'si-no']]],
  ['experiencia', [['duracion_minutos', 'minutos'], ['nivel_fisico', 'codigo'], ['punto_encuentro', 'texto'], ['salidas_por_dia', 'numero'], ['edad_minima', 'numero'], ['grupo_minimo', 'numero'], ['grupo_maximo', 'numero'], ['incluye_guia', 'si-no'], ['idiomas_guia', 'idiomas'], ['incluye_transporte', 'si-no'], ['incluye_equipo', 'si-no'], ['que_llevar', 'texto'], ['requisitos', 'texto']]],
  ['gastronomia', [['tipos_cocina', 'lista'], ['opciones_dietarias', 'lista'], ['precio_min_persona', 'dinero'], ['precio_max_persona', 'dinero'], ['requiere_reserva', 'si-no'], ['puestos', 'numero'], ['domicilio', 'si-no']]],
  ['entrada', [['tarifas', 'tarifas'], ['temporadas_cierre', 'texto'], ['reglas', 'texto'], ['servicios_en_sitio', 'lista']]],
  ['alquiler', [['equipos', 'texto'], ['deposito', 'dinero'], ['requiere_documento', 'si-no']]],
  ['transporte', [['origen', 'texto'], ['destino', 'texto'], ['duracion_minutos', 'minutos'], ['capacidad_vehiculo', 'numero'], ['horarios_salida', 'horas'], ['incluye_chaleco_salvavidas', 'si-no']]],
  // El aviso de pagos ya lo resume la ficha; aquí solo los medios y la señal, que son datos sueltos útiles.
  ['pagos', [['senal_internet', 'codigo'], ['medios_pago', 'lista']]],
]

const vacio = (v) => v == null || v === '' || (Array.isArray(v) && v.length === 0)

/** Normaliza el valor de un campo a lo que la interfaz sabe pintar, o `undefined` si no hay nada que mostrar. */
function valorDe(clase, v, etiquetas) {
  const et = (c) => etiquetas?.[c] ?? String(c)
  switch (clase) {
    case 'texto': return typeof v === 'string' ? v : undefined
    case 'codigo': return typeof v === 'string' ? et(v) : undefined
    case 'lista': return Array.isArray(v) ? v.map((x) => et(x)) : undefined
    case 'idiomas': return Array.isArray(v) ? v.map((x) => String(x).toUpperCase()) : undefined
    case 'horas': return Array.isArray(v) ? v.map(String) : undefined
    case 'hora': return typeof v === 'string' ? v : undefined
    case 'si-no': return typeof v === 'boolean' ? v : undefined // null = el prestador no lo informó: no se muestra
    case 'minutos': case 'dinero': case 'numero': return Number.isFinite(Number(v)) ? Number(v) : undefined
    case 'habitaciones': return Array.isArray(v) ? v.map((h) => ({ tipo: et(h.tipo), capacidad: Number(h.capacidad_personas), cantidad: Number(h.cantidad ?? 1) })) : undefined
    case 'tarifas': return Array.isArray(v) ? v.map((t) => ({ visitante: et(t.tipo_visitante), valor: Number(t.valor) })) : undefined
    default: return undefined
  }
}

/**
 * @param {object|null} atributos  `atributos` de la ficha (ya en el idioma pedido)
 * @param {Record<string,string>} etiquetas  código fijo -> texto en el idioma pedido
 * @returns {{id: string, filas: {campo: string, clase: string, valor: any}[]}[]} solo secciones con algo que mostrar
 */
export function seccionesDeAtributos(atributos, etiquetas = {}) {
  if (!atributos || typeof atributos !== 'object') return []
  const secciones = []
  for (const [id, campos] of BLOQUES) {
    const bloque = atributos[id]
    if (!bloque || typeof bloque !== 'object') continue
    const filas = []
    for (const [campo, clase] of campos) {
      if (vacio(bloque[campo])) continue
      const valor = valorDe(clase, bloque[campo], etiquetas)
      if (valor !== undefined && !vacio(valor)) filas.push({ campo, clase, valor })
    }
    if (filas.length) secciones.push({ id, filas })
  }
  return secciones
}
