import { describe, expect, it, vi } from 'vitest'
import { createAccountUseCases, createAdminUseCases, createEntityUseCases, createOfferUseCases, createReviewUseCases } from '../../src/application/gestion/useCases.js'
import { ACCOUNT_METHODS, ADMIN_METHODS, ENTITY_METHODS, OFFER_METHODS, REVIEW_METHODS } from '../../src/application/gestion/ports.js'
import { formularioVacio } from '../../src/domain/gestion/servicio.js'

const falso = (metodos) => Object.fromEntries(metodos.map((m) => [m, vi.fn(async () => ({ ok: true }))]))
const archivo = (type, size) => ({ type, size })
const rechaza = async (p, campo, mensaje) => {
  const e = await p.then(() => null, (x) => x)
  expect(e, 'debía rechazar').toBeTruthy()
  expect(e.code).toBe('VALIDACION')
  expect(e.campos).toContainEqual({ campo, mensaje })
}

describe('cuenta (UC4, UC37)', () => {
  it('cambiar contraseña valida antes de llamar al servicio', async () => {
    const gw = falso(ACCOUNT_METHODS); const uc = createAccountUseCases({ gateway: gw })
    await rechaza(uc.cambiarContrasena({ actual: '', nueva: 'Tayrona2026', confirmacion: 'Tayrona2026' }), 'actual', 'REQUERIDO')
    await rechaza(uc.cambiarContrasena({ actual: 'Vieja2026', nueva: 'corta', confirmacion: 'corta' }), 'nueva', 'PASSWORD_INVALIDA')
    await rechaza(uc.cambiarContrasena({ actual: 'Vieja2026', nueva: 'Nueva2026', confirmacion: 'Otra2026' }), 'confirmacion', 'NO_COINCIDEN')
    await rechaza(uc.cambiarContrasena({ actual: 'Tayrona2026', nueva: 'Tayrona2026', confirmacion: 'Tayrona2026' }), 'nueva', 'IGUAL_A_LA_ACTUAL')
    expect(gw.cambiarContrasena).not.toHaveBeenCalled()
    await uc.cambiarContrasena({ actual: 'Vieja2026', nueva: 'Nueva2026', confirmacion: 'Nueva2026' })
    expect(gw.cambiarContrasena).toHaveBeenCalledWith({ actual: 'Vieja2026', nueva: 'Nueva2026' })
  })
  it('editar perfil recorta el nombre y exige algún cambio', async () => {
    const gw = falso(ACCOUNT_METHODS); const uc = createAccountUseCases({ gateway: gw })
    await rechaza(uc.editarPerfil({ nombre: ' ' }), 'nombre', 'NOMBRE_INVALIDO')
    await rechaza(uc.editarPerfil({}), 'nombre', 'SIN_CAMBIOS')
    await uc.editarPerfil({ nombre: '  Ana Gómez ', idioma: 'en' })
    expect(gw.editarPerfil).toHaveBeenCalledWith({ nombre: 'Ana Gómez', idioma: 'en' })
  })
  it('documentos: tipo de archivo, 5 MB y razón social con el RUT', async () => {
    const gw = falso(ACCOUNT_METHODS); const uc = createAccountUseCases({ gateway: gw })
    await rechaza(uc.subirDocumento({ tipo: 'RNT', archivo: archivo('text/plain', 10) }), 'archivo', 'TIPO_ARCHIVO_NO_PERMITIDO')
    await rechaza(uc.subirDocumento({ tipo: 'RNT', archivo: archivo('application/pdf', 6 * 1024 * 1024) }), 'archivo', 'ARCHIVO_DEMASIADO_GRANDE')
    await rechaza(uc.subirDocumento({ tipo: 'RUT', archivo: archivo('application/pdf', 100), razonSocial: ' ' }), 'razon_social', 'RAZON_SOCIAL_INVALIDA')
    await uc.subirDocumento({ tipo: 'RNT', archivo: archivo('application/pdf', 100), razonSocial: 'ignorada' })
    expect(gw.subirDocumento).toHaveBeenCalledWith({ tipo: 'RNT', archivo: archivo('application/pdf', 100), razonSocial: undefined })
  })
})

describe('administración', () => {
  it('rechazar un prestador exige un motivo por documento', async () => {
    const gw = falso(ADMIN_METHODS); const uc = createAdminUseCases({ gateway: gw })
    await rechaza(uc.rechazarPrestador('u1', [{ tipo: 'RNT', motivo: '  ' }]), 'motivo_RNT', 'MOTIVO_REQUERIDO')
    await uc.rechazarPrestador('u1', [{ tipo: 'RUT', motivo: ' Ilegible ' }])
    expect(gw.rechazarPrestador).toHaveBeenCalledWith('u1', [{ tipo: 'RUT', motivo: 'Ilegible' }])
  })
  it('la bitácora no acepta un rango invertido', async () => {
    const uc = createAdminUseCases({ gateway: falso(ADMIN_METHODS) })
    await rechaza(uc.bitacora({ desde: '2026-11-10T00:00:00Z', hasta: '2026-11-01T00:00:00Z' }), 'desde', 'RANGO_INVERTIDO')
  })
  it('cambiar el rol valida el catálogo de roles', async () => {
    const uc = createAdminUseCases({ gateway: falso(ADMIN_METHODS) })
    await rechaza(uc.cambiarRol('u1', { rol: 'Superuser' }), 'rol', 'ROL_INVALIDO')
  })
})

describe('reseñas', () => {
  it('escribir arma el cuerpo del contrato y reutiliza la clave que se le pasa', async () => {
    const gw = falso(REVIEW_METHODS); const uc = createReviewUseCases({ gateway: gw })
    await uc.escribir('s1', { puntuacion: 4, aspectos: { LIMPIEZA: 5, ATENCION: '' }, comentario: ' Muy bien ' }, 'clave-1')
    expect(gw.escribir).toHaveBeenCalledWith({ servicio_id: 's1', puntuacion: 4, aspectos: { LIMPIEZA: 5 }, comentario: 'Muy bien' }, 'clave-1')
    await rechaza(uc.escribir('s1', { puntuacion: 0 }, 'k'), 'puntuacion', 'PUNTUACION_INVALIDA')
  })
  it('ocultar exige motivo; publicar no', async () => {
    const gw = falso(REVIEW_METHODS); const uc = createReviewUseCases({ gateway: gw })
    await rechaza(uc.moderar('r1', { decision: 'OCULTAR' }, 2), 'motivo', 'MOTIVO_REQUERIDO')
    await uc.moderar('r1', { decision: 'PUBLICAR' }, 2)
    expect(gw.moderar).toHaveBeenCalledWith('r1', { decision: 'PUBLICAR' }, 2)
  })
  it('responder y reportar validan texto y motivo', async () => {
    const uc = createReviewUseCases({ gateway: falso(REVIEW_METHODS) })
    await rechaza(uc.responder('r1', '   ', 1), 'texto', 'RESPUESTA_REQUERIDA')
    await rechaza(uc.reportar('r1', { motivo: 'NADA' }), 'motivo', 'MOTIVO_INVALIDO')
  })
})

describe('oferta del prestador', () => {
  it('no manda un servicio inválido y manda el cuerpo del contrato cuando es válido', async () => {
    const gw = falso(OFFER_METHODS); const uc = createOfferUseCases({ gateway: gw, nuevaClave: () => 'k-auto' })
    const e = await uc.crearServicio(formularioVacio()).then(() => null, (x) => x)
    expect(e.code).toBe('VALIDACION')
    expect(gw.crearServicio).not.toHaveBeenCalled()
    const f = formularioVacio()
    Object.assign(f, { tipo: 'RESTAURANTE', tarifa_base: 30000, capacidad_aforo_diario: 40, ubicacion: { lat: 11.24, lon: -74.2 } })
    f.nombre.es = 'La Sirena'; f.descripcion.es = 'Cocina de mar'; f.bloques.gastronomia.tipos_cocina = ['DE_MAR']
    await uc.crearServicio(f)
    expect(gw.crearServicio).toHaveBeenCalledWith(expect.objectContaining({ tipo: 'RESTAURANTE', atributos: { gastronomia: { tipos_cocina: ['DE_MAR'] } } }), 'k-auto')
  })
  it('subir imagen valida tipo y tamaño; las métricas, el rango', async () => {
    const uc = createOfferUseCases({ gateway: falso(OFFER_METHODS) })
    await rechaza(uc.subirImagen(archivo('image/gif', 10)), 'imagen', 'TIPO_IMAGEN_NO_PERMITIDO')
    await rechaza(uc.metricas({ desde: '2026-11-10', hasta: '2026-11-01' }), 'desde', 'RANGO_INVERTIDO')
  })
})

describe('entidad', () => {
  it('una alerta lleva destino (zona o servicio, no ambos) y fecha válida', async () => {
    const gw = falso(ENTITY_METHODS); const uc = createEntityUseCases({ gateway: gw })
    const base = { nivel: 'PREVENTIVA', mensaje: { es: 'Oleaje', en: '' }, fechaExpiracion: '2026-12-01T10:00' }
    await rechaza(uc.crearAlerta({ ...base }), 'destino', 'DESTINO_REQUERIDO')
    await rechaza(uc.crearAlerta({ ...base, zona: 'taganga', servicioId: 's1' }), 'destino', 'DESTINO_UNICO')
    await uc.crearAlerta({ ...base, zona: 'taganga' })
    expect(gw.crearAlerta).toHaveBeenCalledWith({ nivel: 'PREVENTIVA', mensaje: { es: 'Oleaje' }, zona: 'taganga', fecha_expiracion: new Date('2026-12-01T10:00').toISOString() })
  })
  it('el tablero y el reporte exigen un rango válido', async () => {
    const uc = createEntityUseCases({ gateway: falso(ENTITY_METHODS) })
    await rechaza(uc.tablero({ desde: 'x', hasta: '2026-11-01' }), 'desde', 'FECHA_INVALIDA')
    await rechaza(uc.reporteCsv({ desde: '2025-01-01', hasta: '2026-12-31' }), 'desde', 'RANGO_LARGO')
  })
})
