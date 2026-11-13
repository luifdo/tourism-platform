import { describe, expect, it } from 'vitest'
import { seccionesDeAtributos } from '../../../src/domain/catalog/atributos.js'

describe('seccionesDeAtributos', () => {
  it('sin atributos no hay secciones', () => {
    expect(seccionesDeAtributos(null)).toEqual([])
    expect(seccionesDeAtributos({})).toEqual([])
    expect(seccionesDeAtributos({ comunes: {} })).toEqual([])
  })

  it('ordena por bloques y traduce códigos con las etiquetas del servicio', () => {
    const s = seccionesDeAtributos(
      { experiencia: { duracion_minutos: 240, nivel_fisico: 'MEDIO', que_llevar: 'Agua' }, comunes: { incluye: 'Guía', idiomas_atencion: ['es', 'en'] } },
      { MEDIO: 'Medio' },
    )
    expect(s.map((x) => x.id)).toEqual(['comunes', 'experiencia'])
    expect(s[0].filas).toEqual([{ campo: 'incluye', clase: 'texto', valor: 'Guía' }, { campo: 'idiomas_atencion', clase: 'idiomas', valor: ['ES', 'EN'] }])
    expect(s[1].filas.find((f) => f.campo === 'nivel_fisico').valor).toBe('Medio')
    expect(s[1].filas.find((f) => f.campo === 'duracion_minutos').valor).toBe(240)
  })

  it('un código sin etiqueta se muestra tal cual', () => {
    const [s] = seccionesDeAtributos({ gastronomia: { tipos_cocina: ['DE_MAR'] } }, {})
    expect(s.filas[0].valor).toEqual(['DE_MAR'])
  })

  it('el sí/no que el prestador no informó (null) no se muestra, el falso sí', () => {
    const [s] = seccionesDeAtributos({ comunes: { accesible: null, mascotas: false, apto_ninos: true } })
    expect(s.filas.map((f) => [f.campo, f.valor])).toEqual([['mascotas', false], ['apto_ninos', true]])
  })

  it('habitaciones y tarifas por visitante', () => {
    const s = seccionesDeAtributos({
      alojamiento: { habitaciones: [{ tipo: 'CABANA', capacidad_personas: 4 }, { tipo: 'CARPA', capacidad_personas: 2, cantidad: 3 }] },
      entrada: { tarifas: [{ tipo_visitante: 'NACIONAL', valor: 20000 }] },
    }, { CABANA: 'Cabaña', CARPA: 'Carpa', NACIONAL: 'Nacional' })
    expect(s[0].filas[0].valor).toEqual([{ tipo: 'Cabaña', capacidad: 4, cantidad: 1 }, { tipo: 'Carpa', capacidad: 2, cantidad: 3 }])
    expect(s[1].filas[0].valor).toEqual([{ visitante: 'Nacional', valor: 20000 }])
  })

  it('ignora bloques y campos que no conoce', () => {
    expect(seccionesDeAtributos({ inventado: { x: 1 }, comunes: { campo_nuevo: 'y' } })).toEqual([])
  })
})
