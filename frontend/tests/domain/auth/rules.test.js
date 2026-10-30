import { describe, expect, it } from 'vitest'
import {
  crearSesion, emailValido, evaluarPassword, normalizarEmail, rutaSegura, sesionVigente, validarLogin, validarNuevaPassword,
  validarRegistro, vencerSesion,
} from '../../../src/domain/auth/rules.js'

const valido = { email: 'maria.perez@example.com', password: 'Tayrona2026', nombre: 'María Pérez', rol: 'Turista', habeasDataAceptado: true, esMayorDeEdad: true }
const codigos = (datos) => validarRegistro(datos).map((e) => e.codigo)

describe('correo', () => {
  it('se normaliza como lo guarda el servidor: sin espacios y en minúsculas', () => {
    expect(normalizarEmail('  Maria.Perez@Example.COM ')).toBe('maria.perez@example.com')
    expect(normalizarEmail(undefined)).toBe('')
  })
  it('valida el formato local@dominio.tld', () => {
    for (const ok of ['a@b.co', 'maria.perez@example.com', ' x@y.zz ']) expect(emailValido(ok), ok).toBe(true)
    for (const mal of ['', 'sin-arroba', 'a@b', 'a@@b.co', 'a b@c.co', '@b.co', 'a@.co'.replace('.co', '')]) expect(emailValido(mal), mal).toBe(false)
  })
  it('no admite más de 254 caracteres', () => {
    expect(emailValido(`${'a'.repeat(242)}@example.com`)).toBe(true) // 254
    expect(emailValido(`${'a'.repeat(243)}@example.com`)).toBe(false) // 255
  })
})

describe('política de contraseña (8–128, con letra y número)', () => {
  it('acepta una contraseña correcta', () => expect(evaluarPassword('Tayrona2026').valida).toBe(true))
  it('exige al menos 8 caracteres', () => {
    expect(evaluarPassword('Abc1234').longitud).toBe(false) // 7
    expect(evaluarPassword('Abc12345').valida).toBe(true) // 8
  })
  it('admite hasta 128 caracteres', () => {
    expect(evaluarPassword(`a1${'x'.repeat(126)}`).valida).toBe(true) // 128
    expect(evaluarPassword(`a1${'x'.repeat(127)}`).valida).toBe(false) // 129
  })
  it('exige una letra y un número, y lo informa por separado', () => {
    expect(evaluarPassword('12345678')).toMatchObject({ longitud: true, letra: false, numero: true, valida: false })
    expect(evaluarPassword('abcdefgh')).toMatchObject({ longitud: true, letra: true, numero: false, valida: false })
  })
  it('reconoce letras con tilde y la ñ', () => expect(evaluarPassword('contraseñá1').valida).toBe(true))
  it('un valor vacío o indefinido no es válido ni falla', () => {
    expect(evaluarPassword('').valida).toBe(false)
    expect(evaluarPassword(undefined).valida).toBe(false)
  })
})

describe('registro (UC1 + UC6)', () => {
  it('acepta un registro completo', () => expect(validarRegistro(valido)).toEqual([]))
  it('el prestador también se puede autorregistrar', () => expect(validarRegistro({ ...valido, rol: 'Prestador' })).toEqual([]))
  it('no se autorregistran Entidad ni Admin', () => {
    for (const rol of ['Entidad', 'Admin', '', undefined]) expect(codigos({ ...valido, rol }), String(rol)).toEqual(['ROL_NO_PERMITIDO'])
  })
  it('exige aceptar el tratamiento de datos (Ley 1581)', () => {
    expect(codigos({ ...valido, habeasDataAceptado: false })).toEqual(['HABEAS_DATA_REQUERIDO'])
  })
  it('exige ser mayor de 18 años', () => {
    expect(codigos({ ...valido, esMayorDeEdad: false })).toEqual(['MAYORIA_DE_EDAD_REQUERIDA'])
  })
  it('el nombre debe tener entre 2 y 150 caracteres, sin contar espacios a los lados', () => {
    expect(codigos({ ...valido, nombre: ' A ' })).toEqual(['NOMBRE_INVALIDO'])
    expect(codigos({ ...valido, nombre: 'Al' })).toEqual([])
    expect(codigos({ ...valido, nombre: 'a'.repeat(150) })).toEqual([])
    expect(codigos({ ...valido, nombre: 'a'.repeat(151) })).toEqual(['NOMBRE_INVALIDO'])
  })
  it('devuelve todos los problemas a la vez, cada uno en su campo', () => {
    const errores = validarRegistro({ email: 'x', password: 'abc', nombre: '', rol: 'Admin', habeasDataAceptado: false, esMayorDeEdad: false })
    expect(errores.map((e) => e.campo).sort()).toEqual(['email', 'habeasData', 'mayorDeEdad', 'nombre', 'password', 'rol'])
    expect(new Set(errores.map((e) => e.campo)).size).toBe(errores.length)
  })
})

describe('login y nueva contraseña', () => {
  it('el login solo exige que haya algo escrito (el servidor trata igual un correo mal formado que uno inexistente)', () => {
    expect(validarLogin({ email: 'cualquier cosa', password: 'x' })).toEqual([])
    expect(validarLogin({ email: '  ', password: '' }).map((e) => e.campo)).toEqual(['email', 'password'])
  })
  it('la nueva contraseña cumple la política y coincide con su confirmación', () => {
    expect(validarNuevaPassword({ password: 'NuevaClave77', confirmacion: 'NuevaClave77' })).toEqual([])
    expect(validarNuevaPassword({ password: 'corta1', confirmacion: 'corta1' })[0].campo).toBe('password')
    expect(validarNuevaPassword({ password: 'NuevaClave77', confirmacion: 'otra' })[0].campo).toBe('confirmacion')
  })
})

describe('redirección segura (evita la redirección abierta)', () => {
  it('acepta rutas internas con parámetros', () => {
    expect(rutaSegura('/mis-reservas')).toBe('/mis-reservas')
    expect(rutaSegura('/servicios/bahia-concha?x=1#y')).toBe('/servicios/bahia-concha?x=1#y')
  })
  it('rechaza sitios externos y variantes para esquivar el filtro', () => {
    for (const hostil of ['//evil.com', 'https://evil.com', 'http://evil.com/x', '/\\evil.com', 'javascript:alert(1)', 'evil.com', '', '/a\nb', '/a\u0000b'])
      expect(rutaSegura(hostil), JSON.stringify(hostil)).toBe('/')
  })
  it('tolera valores que no son texto y usa el destino por defecto indicado', () => {
    expect(rutaSegura(undefined)).toBe('/')
    expect(rutaSegura(['/a', '/b'])).toBe('/')
    expect(rutaSegura(null, '/inicio')).toBe('/inicio')
  })
})

describe('sesión', () => {
  const AHORA = new Date('2026-10-27T12:00:00Z')
  const respuesta = { access_token: 'jwt', token_type: 'bearer', expires_in: 900, usuario: { id: 'u1', email: 'a@b.co', rol: 'Turista' } }

  it('el vencimiento se calcula con expires_in (15 min en iam-service)', () => {
    expect(crearSesion(respuesta, AHORA)).toEqual({ token: 'jwt', usuario: respuesta.usuario, expiraEn: AHORA.getTime() + 900_000 })
  })
  it('vigente mientras falte más que el margen de seguridad de 30 s', () => {
    const s = crearSesion(respuesta, AHORA)
    expect(sesionVigente(s, AHORA)).toBe(true)
    expect(sesionVigente(s, new Date(AHORA.getTime() + 869_000))).toBe(true) // quedan 31 s
    expect(sesionVigente(s, new Date(AHORA.getTime() + 870_000))).toBe(false) // quedan 30 s
    expect(sesionVigente(s, new Date(AHORA.getTime() + 901_000))).toBe(false)
  })
  it('sin sesión o sin token no hay sesión vigente', () => {
    expect(sesionVigente(null, AHORA)).toBe(false)
    expect(sesionVigente(undefined, AHORA)).toBe(false)
    expect(sesionVigente({ token: '', expiraEn: Infinity }, AHORA)).toBe(false)
  })
  it('vencer una sesión borra el token pero recuerda quién era, sin mutar la original', () => {
    const s = crearSesion(respuesta, AHORA)
    const vencida = vencerSesion(s)
    expect(vencida).toMatchObject({ token: null, expiraEn: 0, usuario: respuesta.usuario })
    expect(sesionVigente(vencida, AHORA)).toBe(false)
    expect(s.token).toBe('jwt')
  })
})
