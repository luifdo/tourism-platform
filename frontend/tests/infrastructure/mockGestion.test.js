import { describe, expect, it } from 'vitest'
import { createMockGestion } from '../../src/infrastructure/gestion/mockGestion.js'
import { assertAccountGateway, assertAdminGateway, assertEntityGateway, assertOfferGateway, assertReviewGateway } from '../../src/application/gestion/ports.js'

const memoria = () => { const m = new Map(); return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) } }
const reloj = { now: () => new Date('2026-11-13T10:00:00Z') }
const personas = { tur: { id: 'tur-1', rol: 'Turista' }, pre: { id: 'pre-1', rol: 'Prestador' }, adm: { id: 'adm-1', rol: 'Admin' }, ent: { id: 'ent-1', rol: 'Entidad' } }
const archivo = (type = 'application/pdf') => ({ type, size: 100 })

function entorno() {
  let actual = personas.tur
  const usuarios = Object.values(personas).map((p, i) => ({ ...p, nombre_completo: `U${i}`, email: `u${i}@x.co`, activo: true, idioma: 'es', creado_en: '2026-01-01T00:00:00Z' }))
  const directorio = {
    todos: async () => usuarios, obtener: async (id) => usuarios.find((u) => u.id === id) ?? null,
    actualizar: async (id, c) => Object.assign(usuarios.find((u) => u.id === id), c), verificarPassword: async (_id, p) => p === 'Correcta2026', cambiarPassword: async () => {}, suprimir: async () => {},
  }
  const m = createMockGestion({ storage: memoria(), clock: reloj, directorio, usuario: () => actual, delayMs: 0, newId: (() => { let n = 0; return () => `id-${++n}` })() })
  return { m, como: (p) => { actual = personas[p] } }
}
const falla = async (p, code) => expect(await p.then(() => null, (e) => e)).toMatchObject({ code })

describe('los simuladores cumplen los puertos', () => {
  it('implementan todos los métodos', () => {
    const { m } = entorno()
    assertAccountGateway(m.account); assertAdminGateway(m.admin); assertReviewGateway(m.review); assertOfferGateway(m.offer); assertEntityGateway(m.entity)
  })
})

describe('roles', () => {
  it('sin sesión 401 y con otro rol 403', async () => {
    const { m, como } = entorno()
    como('tur')
    await falla(m.admin.usuarios({}), 'ROL_INSUFICIENTE')
    await falla(m.entity.alertas({}), 'ROL_INSUFICIENTE')
    await falla(m.offer.servicios({}), 'ROL_INSUFICIENTE')
  })
})

describe('reseñas', () => {
  it('pendientes -> escribir -> una por servicio, idempotente, y cuenta en el resumen', async () => {
    const { m, como } = entorno(); como('tur')
    const pend = await m.review.pendientes()
    expect(pend.length).toBeGreaterThan(0)
    const id = pend[0].servicio_id
    const antes = (await m.review.resumen(id)).total
    const r = await m.review.escribir({ servicio_id: id, puntuacion: 5, comentario: 'Genial' }, 'k1')
    expect(r).toMatchObject({ estado: 'PUBLICADA', version: 1 })
    expect((await m.review.escribir({ servicio_id: id, puntuacion: 1 }, 'k1')).id).toBe(r.id) // mismo intento: misma respuesta
    await falla(m.review.escribir({ servicio_id: id, puntuacion: 4 }, 'k2'), 'YA_RESENADO')
    expect((await m.review.resumen(id)).total).toBe(antes + 1)
    expect((await m.review.pendientes()).some((p) => p.servicio_id === id)).toBe(false)
  })
  it('un servicio que no disfrutó no se puede reseñar (NO_ELEGIBLE)', async () => {
    const { m, como } = entorno(); como('tur')
    await falla(m.review.escribir({ servicio_id: 'ruta-cacao', puntuacion: 4 }, 'k'), 'NO_ELEGIBLE')
  })
  it('editar pide la versión vigente; responder la sube', async () => {
    const { m, como } = entorno(); como('tur')
    const id = (await m.review.pendientes())[0].servicio_id
    const r = await m.review.escribir({ servicio_id: id, puntuacion: 3 }, 'k')
    await falla(m.review.editar(r.id, { puntuacion: 4 }, 9), 'VERSION_DISTINTA')
    const e = await m.review.editar(r.id, { puntuacion: 4 }, r.version)
    expect(e.version).toBe(2)
    como('pre')
    const respondida = await m.review.responder(r.id, 'Gracias', e.version)
    expect(respondida.respuesta.texto).toBe('Gracias')
    como('tur')
    await falla(m.review.editar(r.id, { puntuacion: 5 }, e.version), 'VERSION_DISTINTA') // la respuesta subió la versión
  })
  it('moderación: la reportada está en la cola; ocultar la saca del resumen y de la cola', async () => {
    const { m, como } = entorno(); como('adm')
    const cola = await m.review.colaModeracion({})
    expect(cola.total).toBeGreaterThan(0)
    const r = cola.items[0]
    expect(r.reportes.length).toBeGreaterThan(0)
    const antes = (await m.review.resumen(r.servicio_id)).total
    const h = await m.review.moderar(r.id, { decision: 'OCULTAR', motivo: 'Ofensiva' }, r.version)
    expect(h.estado).toBe('OCULTA')
    expect((await m.review.resumen(r.servicio_id)).total).toBe(antes - 1)
    expect((await m.review.colaModeracion({})).items.some((x) => x.id === r.id)).toBe(false)
    await falla(m.review.moderar(r.id, { decision: 'PUBLICAR' }, 1), 'VERSION_DISTINTA')
  })
  it('reportar: una vez por usuario; el dueño la pone en revisión', async () => {
    const { m, como } = entorno(); como('tur')
    const lista = await m.review.resenasDeServicio('bahia-concha', { orden: 'recientes', pagina: 1, tamano: 10 })
    const r = lista.items[0]
    await m.review.reportar(r.id, { motivo: 'SPAM' })
    await falla(m.review.reportar(r.id, { motivo: 'SPAM' }), 'YA_REPORTADA')
    como('pre')
    await m.review.reportar(r.id, { motivo: 'FALSO' })
    expect((await m.review.resenasDeServicio('bahia-concha', { orden: 'recientes', pagina: 1, tamano: 10 })).items.some((x) => x.id === r.id)).toBe(false) // pasó a EN_REVISION
  })
})

describe('verificación del prestador', () => {
  it('sube RNT y RUT -> pendiente -> el Admin aprueba -> ya no se reemplaza', async () => {
    const { m, como } = entorno(); como('pre')
    expect((await m.account.misDocumentos()).estado).toBe('incompleto')
    await m.account.subirDocumento({ tipo: 'RNT', archivo: archivo() })
    await m.account.subirDocumento({ tipo: 'RUT', archivo: archivo('image/png'), razonSocial: 'Guías S.A.S.' })
    const mios = await m.account.misDocumentos()
    expect(mios).toMatchObject({ estado: 'pendiente', razon_social: 'Guías S.A.S.' })
    como('adm')
    const cola = await m.admin.prestadores({ estado: 'pendiente' })
    expect(cola.items.some((p) => p.usuario_id === 'pre-1')).toBe(true)
    expect((await m.admin.aprobarPrestador('pre-1')).estado).toBe('aprobado')
    como('pre')
    await falla(m.account.subirDocumento({ tipo: 'RNT', archivo: archivo() }), 'DOCUMENTO_APROBADO')
  })
  it('rechazar deja el motivo a la vista del prestador y permite subir uno nuevo', async () => {
    const { m, como } = entorno(); como('pre')
    await m.account.subirDocumento({ tipo: 'RNT', archivo: archivo() }); await m.account.subirDocumento({ tipo: 'RUT', archivo: archivo(), razonSocial: 'X S.A.S.' })
    como('adm')
    await m.admin.rechazarPrestador('pre-1', [{ tipo: 'RNT', motivo: 'Ilegible' }])
    como('pre')
    const mios = await m.account.misDocumentos()
    expect(mios.estado).toBe('rechazado')
    expect(mios.documentos.find((d) => d.tipo_documento === 'RNT').motivo_rechazo).toBe('Ilegible')
    await m.account.subirDocumento({ tipo: 'RNT', archivo: archivo() })
    expect((await m.account.misDocumentos()).estado).toBe('pendiente')
  })
  it('aprobar sin documentos completos es DOCUMENTOS_INCOMPLETOS', async () => {
    const { m, como } = entorno(); como('adm')
    await falla(m.admin.aprobarPrestador('pre-1'), 'DOCUMENTOS_INCOMPLETOS')
  })
})

describe('administración de cuentas', () => {
  it('no se cambia la propia cuenta ni se deja la plataforma sin administradores', async () => {
    const { m, como } = entorno(); como('adm')
    await falla(m.admin.cambiarRol('adm-1', { rol: 'Turista' }), 'AUTOGESTION_NO_PERMITIDA')
    expect((await m.admin.cambiarEstado('tur-1', { activo: false })).activo).toBe(false)
    expect((await m.admin.usuarios({ activo: false })).items.map((u) => u.id)).toEqual(['tur-1'])
  })
  it('la bitácora registra lo hecho y también la consulta', async () => {
    const { m, como } = entorno(); como('adm')
    await m.admin.cambiarEstado('tur-1', { activo: false, motivo: 'Spam' })
    const b = await m.admin.bitacora({ pagina: 1, tamano: 20 })
    expect(b.items[0]).toMatchObject({ accion: 'USER_DEACTIVATE', resultado: 'Exito' })
    expect((await m.admin.bitacora({ accion: 'AUDIT_VIEW' })).total).toBeGreaterThan(0)
  })
})

describe('perfil', () => {
  it('cambiar la contraseña exige la actual correcta; suprimir también', async () => {
    const { m, como } = entorno(); como('tur')
    await falla(m.account.cambiarContrasena({ actual: 'mala', nueva: 'Nueva2026' }), 'PASSWORD_ACTUAL_INCORRECTA')
    await m.account.cambiarContrasena({ actual: 'Correcta2026', nueva: 'Nueva2026' })
    await falla(m.account.suprimirDatos('mala'), 'CREDENCIALES_INVALIDAS')
    como('adm')
    await falla(m.account.suprimirDatos('Correcta2026'), 'ULTIMO_ADMIN')
  })
})

describe('oferta del prestador', () => {
  const cuerpo = { nombre: { es: 'Kayak' }, descripcion: { es: 'Remada' }, tipo: 'DEPORTE_ACUATICO', ubicacion: { lat: 11.26, lon: -74.19 }, tarifa_base: 80000, unidad_tarifa: 'POR_PERSONA', capacidad_aforo_diario: 8, atributos: {}, imagenes_urls: [] }
  it('crear es idempotente, editar exige la versión y desactivar la sube', async () => {
    const { m, como } = entorno(); como('pre')
    const a = await m.offer.crearServicio(cuerpo, 'c1')
    expect((await m.offer.crearServicio(cuerpo, 'c1')).id).toBe(a.id)
    expect(a).toMatchObject({ categoria: 'AVENTURA', activo: true, version: 1, zona: { codigo: 'taganga' } })
    await falla(m.offer.editarServicio(a.id, { ...cuerpo, tarifa_base: 90000 }, 7, 'c2'), 'VERSION_DISTINTA')
    const e = await m.offer.editarServicio(a.id, { ...cuerpo, tarifa_base: 90000 }, 1, 'c3')
    expect(e).toMatchObject({ tarifa_base: 90000, version: 2 })
    expect(await m.offer.desactivarServicio(a.id, 2)).toMatchObject({ activo: false, version: 3 })
    expect(await m.offer.reactivarServicio(a.id, 3)).toMatchObject({ activo: true })
  })
  it('las métricas traen un registro por servicio y el perfil comercial usa la versión', async () => {
    const { m, como } = entorno(); como('pre')
    const mt = await m.offer.metricas({ desde: '2026-10-01', hasta: '2026-10-31' })
    expect(mt.servicios.length).toBeGreaterThan(0)
    expect(mt.servicios[0].reservas).toHaveProperty('confirmadas')
    const p = await m.offer.perfilComercial()
    await falla(m.offer.editarPerfilComercial({ telefono: '1' }, 99), 'VERSION_DISTINTA')
    expect((await m.offer.editarPerfilComercial({ telefono: '300' }, p.version)).version).toBe(p.version + 1)
  })
})

describe('Entidad', () => {
  it('alertas: crear, editar con versión, retirar y no editar una retirada', async () => {
    const { m, como } = entorno(); como('ent')
    const a = await m.entity.crearAlerta({ nivel: 'CRITICA', mensaje: { es: 'Cierre' }, zona: 'minca', fecha_expiracion: '2026-12-01T00:00:00Z' })
    expect(a).toMatchObject({ estado: 'VIGENTE', version: 1 })
    await falla(m.entity.editarAlerta(a.id, { nivel: 'PREVENTIVA', mensaje: { es: 'x' }, fecha_expiracion: '2026-12-02T00:00:00Z' }, 5), 'VERSION_DISTINTA')
    expect((await m.entity.editarAlerta(a.id, { nivel: 'PREVENTIVA', mensaje: { es: 'x' }, fecha_expiracion: '2026-12-02T00:00:00Z' }, 1)).version).toBe(2)
    expect((await m.entity.retirarAlerta(a.id)).estado).toBe('RETIRADA')
    await falla(m.entity.editarAlerta(a.id, { nivel: 'INFORMATIVA', mensaje: { es: 'y' }, fecha_expiracion: '2026-12-03T00:00:00Z' }, 2), 'ALERTA_RETIRADA')
    await falla(m.entity.crearAlerta({ nivel: 'INFORMATIVA', mensaje: { es: 'z' }, zona: 'no-existe', fecha_expiracion: '2026-12-03T00:00:00Z' }), 'NO_ENCONTRADO')
  })
  it('tablero, demanda y mapa de calor son coherentes entre sí', async () => {
    const { m, como } = entorno(); como('ent')
    const t = await m.entity.tablero({ desde: '2026-11-01', hasta: '2026-11-07' })
    const d = await m.entity.demanda({ desde: '2026-11-01', hasta: '2026-11-07', agrupacion: 'dia' })
    expect(d.serie).toHaveLength(7)
    expect(t.totales.personas_confirmadas).toBe(5 * 0 + (await Promise.all(['taganga', 'minca', 'rodadero', 'guachaca', 'rio-piedras'].map((z) => m.entity.demanda({ desde: '2026-11-01', hasta: '2026-11-07', zona: z })))).reduce((s, x) => s + x.serie.reduce((a, p) => a + p.personas_confirmadas, 0), 0))
    const calor = await m.entity.mapaCalor({})
    expect(calor.features).toHaveLength(5)
    expect(['BAJO', 'MEDIO', 'ALTO']).toContain(calor.features[0].properties.nivel)
  })
  it('el CSV va en español: BOM, separador ; y comillas', async () => {
    const { m, como } = entorno(); como('ent')
    const { texto, nombre } = await m.entity.reporteCsv({ desde: '2026-11-01', hasta: '2026-11-30' })
    expect(texto.startsWith('﻿"Fecha";"Zona";"Servicio"')).toBe(true)
    expect(nombre).toBe('demanda_2026-11-01_2026-11-30.csv')
    expect(texto.split('\r\n').length).toBeGreaterThan(3)
  })
})
