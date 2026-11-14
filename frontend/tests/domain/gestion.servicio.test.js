import { describe, expect, it } from 'vitest'
import { formularioDeServicio, formularioVacio, servicioAPayload, validarServicio } from '../../src/domain/gestion/servicio.js'

const experiencia = () => {
  const f = formularioVacio()
  f.nombre.es = 'Caminata'; f.descripcion.es = 'Por el sendero'
  f.tipo = 'SENDERISMO'; f.ubicacion = { lat: 11.3, lon: -74.1 }; f.tarifa_base = 90000; f.capacidad_aforo_diario = 12
  f.bloques.experiencia.duracion_minutos = 180; f.bloques.experiencia.nivel_fisico = 'MEDIO'
  return f
}

describe('validarServicio', () => {
  it('un formulario vacío pide lo básico', () => {
    const e = validarServicio(formularioVacio())
    expect(Object.keys(e)).toEqual(expect.arrayContaining(['nombre', 'descripcion', 'tipo', 'ubicacion', 'tarifa_base', 'capacidad_aforo_diario']))
  })
  it('una experiencia completa es válida', () => expect(validarServicio(experiencia())).toEqual({}))
  it('exige el bloque propio del tipo', () => {
    const f = experiencia(); f.bloques.experiencia.nivel_fisico = ''
    expect(validarServicio(f)).toEqual({ 'experiencia.nivel_fisico': 'REQUERIDO' })
    const a = experiencia(); a.tipo = 'HOTEL'
    expect(validarServicio(a)).toMatchObject({ 'alojamiento.check_in': 'REQUERIDO', 'alojamiento.habitaciones': 'REQUERIDO' })
  })
  it('el grupo máximo no supera el aforo diario', () => {
    const f = experiencia(); f.bloques.experiencia.grupo_maximo = 50
    expect(validarServicio(f)).toEqual({ 'experiencia.grupo_maximo': 'GRUPO_MAYOR_QUE_AFORO' })
  })
  it('las horas deben ser HH:MM y la ubicación estar en rango', () => {
    const f = experiencia(); f.tipo = 'TRASLADO_TERRESTRE'
    Object.assign(f.bloques.transporte, { origen: { es: 'A', en: '' }, destino: { es: 'B', en: '' }, duracion_minutos: 30, capacidad_vehiculo: 4, horarios_salida: '8:00, 25:00' })
    f.ubicacion.lat = 95
    expect(validarServicio(f)).toEqual({ ubicacion: 'UBICACION_INVALIDA', 'transporte.horarios_salida': 'HORA_INVALIDA' })
  })
  it('pagos: o completos y coherentes o ninguno', () => {
    const f = experiencia(); f.pagos.senal_internet = 'SIN_SENAL'
    expect(validarServicio(f).pagos).toBe('PAGOS_INCOMPLETOS')
    Object.assign(f.pagos, { medios_pago: ['EFECTIVO'], recomendacion_dinero: 'DIGITAL' })
    expect(validarServicio(f).pagos).toBe('DIGITAL_SIN_MEDIO')
    f.pagos.recomendacion_dinero = 'EFECTIVO'
    expect(validarServicio(f).pagos).toBeUndefined()
  })
})

describe('servicioAPayload', () => {
  it('arma ServicioGuardar: solo el bloque del tipo, textos es/en y sin vacíos', () => {
    const f = experiencia()
    f.nombre.en = 'Hike'; f.bloques.comunes.incluye.es = 'Guía'; f.bloques.comunes.accesible = false
    const p = servicioAPayload(f)
    expect(p).toMatchObject({ nombre: { es: 'Caminata', en: 'Hike' }, descripcion: { es: 'Por el sendero' }, tipo: 'SENDERISMO', tarifa_base: 90000, capacidad_aforo_diario: 12, unidad_tarifa: 'POR_PERSONA' })
    expect(p.atributos).toEqual({ comunes: { incluye: { es: 'Guía' }, accesible: false }, experiencia: { duracion_minutos: 180, nivel_fisico: 'MEDIO' } })
  })
  it('al editar conserva lo que el formulario no maneja y quita el bloque del tipo anterior', () => {
    const f = experiencia()
    const previos = { pagos: { senal_internet: 'SIN_SENAL', medios_pago: ['EFECTIVO'], recomendacion_dinero: 'EFECTIVO', credito: { ofrece: true, plazo_dias: 3 } }, alojamiento: { check_in: '14:00' } }
    f.pagos = { senal_internet: 'SIN_SENAL', medios_pago: ['EFECTIVO'], recomendacion_dinero: 'EFECTIVO' }
    const p = servicioAPayload(f, previos)
    expect(p.atributos.pagos.credito).toEqual({ ofrece: true, plazo_dias: 3 })
    expect(p.atributos.alojamiento).toBeUndefined()
  })
  it('ida y vuelta: el formulario de un servicio guardado reproduce su cuerpo', () => {
    const f = experiencia()
    f.bloques.experiencia.punto_encuentro = { es: 'Muelle', en: 'Pier' }
    f.imagenes_urls = ['https://s3.example/a.jpg']
    const guardado = { ...servicioAPayload(f), id: 'x' }
    expect(servicioAPayload(formularioDeServicio(guardado), guardado.atributos)).toEqual(servicioAPayload(f))
  })
})
