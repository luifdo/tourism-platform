import { CODIGOS_GESTION as C, GestionError } from '../../domain/gestion/errors.js'
import { nuevaClave, paginar } from '../../domain/gestion/rules.js'
import { DEMO_SERVICIOS } from '../catalog/demoCatalogo.js'

/*
 * Adaptadores SIMULADOS de los puertos de gestión (VITE_API_MOCK=true, la PWA de GitHub Pages): responden como los
 * servicios reales (códigos y formas del contrato) con datos de ejemplo en memoria. Guardan su estado en el
 * almacenamiento del navegador para que la demostración sobreviva a recargar la página.
 * La identidad sale de la sesión (`usuario()`); las cuentas, del directorio del simulador de IAM.
 */
const KEY = 'mock.gestion.v1'
const err = (code, message, status = 400, extra = {}) => new GestionError(code, message, { status, ...extra })
const MIN = 60_000
const DIA = 24 * 60 * MIN

const ZONAS = [
  { id: 'z-taganga', codigo: 'taganga', nombre: { es: 'Taganga', en: 'Taganga' }, centro: { lat: 11.2667, lon: -74.1936 }, capacidad: 400 },
  { id: 'z-minca', codigo: 'minca', nombre: { es: 'Minca', en: 'Minca' }, centro: { lat: 11.1456, lon: -74.1186 }, capacidad: 250 },
  { id: 'z-rodadero', codigo: 'rodadero', nombre: { es: 'El Rodadero', en: 'El Rodadero' }, centro: { lat: 11.2, lon: -74.2283 }, capacidad: 900 },
  { id: 'z-guachaca', codigo: 'guachaca', nombre: { es: 'Guachaca', en: 'Guachaca' }, centro: { lat: 11.288, lon: -73.95 }, capacidad: 150 },
  { id: 'z-rio-piedras', codigo: 'rio-piedras', nombre: { es: 'Río Piedras', en: 'Río Piedras' }, centro: { lat: 11.268, lon: -74.162 }, capacidad: 120 },
]

// Reseñas de ejemplo por servicio de demostración
const AUTORES = ['Camila R.', 'Andrés M.', 'Laura P.', 'Julián G.', 'Sofía T.']
const COMENTARIOS = ['Una experiencia muy bien cuidada, el guía conoce cada rincón.', 'Llegamos tarde y nos esperaron sin problema. Volveríamos.', 'Bonito, pero faltó más información sobre qué llevar.', 'Excelente atención y grupo pequeño.', 'Muy recomendado para ir en familia.']

function semilla(ahora) {
  const resenas = []
  DEMO_SERVICIOS.forEach((s, i) => {
    for (let k = 0; k < 3; k++) {
      resenas.push({
        id: `r-${s.id}-${k}`, servicio_id: s.id, turista_id: `t-demo-${i}-${k}`, autor: AUTORES[(i + k) % AUTORES.length], mes_visita: ['2026-08', '2026-09', '2026-10'][k],
        puntuacion: [5, 4, 3][(i + k) % 3] + (k === 0 ? 0 : 0), aspectos: { ATENCION: 5, CALIDAD_PRECIO: 4 }, comentario: COMENTARIOS[(i * 2 + k) % COMENTARIOS.length],
        respuesta: k === 0 ? { texto: '¡Gracias por visitarnos! Los esperamos de nuevo.', respondida_en: new Date(ahora - 5 * DIA).toISOString() } : null,
        estado: 'PUBLICADA', version: 1, creada_en: new Date(ahora - (20 - k * 4) * DIA).toISOString(), editada_en: new Date(ahora - (20 - k * 4) * DIA).toISOString(), reportes: [],
      })
    }
  })
  // Una reseña ya reportada: aparece en la cola de moderación del Admin
  resenas.find((r) => r.id === 'r-quebrada-valencia-2').reportes = [
    { motivo: 'OFENSIVO', detalle: 'Insulta al guía.', rol_reportante: 'Turista', es_dueno: false, reportado_en: new Date(ahora - 2 * DIA).toISOString(), usuario_id: 'otro-1' },
    { motivo: 'FALSO', detalle: '', rol_reportante: 'Prestador', es_dueno: true, reportado_en: new Date(ahora - DIA).toISOString(), usuario_id: 'otro-2' },
  ]
  resenas.find((r) => r.id === 'r-quebrada-valencia-2').estado = 'EN_REVISION'
  const docs = [
    ...['p-almendros', 'p-kayak'].flatMap((u, i) => ['RNT', 'RUT'].map((t) => ({
      id: `d-${u}-${t}`, usuario_id: u, tipo_documento: t, estado: 'Pendiente', vigente: true, tipo_contenido: 'application/pdf', tamano_bytes: 180_000 + i * 20_000,
      motivo_rechazo: null, fecha_subida: new Date(ahora - (3 - i) * DIA).toISOString(), revisado_en: null, revisado_por: null,
    }))),
  ]
  return {
    resenas, docs,
    prestadoresExtra: [
      { usuario_id: 'p-almendros', nombre_completo: 'Marta Ríos', email: 'marta@almendros.example', activo: true, razon_social: 'Hostal Los Almendros S.A.S.' },
      { usuario_id: 'p-kayak', nombre_completo: 'Pedro Salcedo', email: 'pedro@kayakrodadero.example', activo: true, razon_social: 'Kayak Rodadero S.A.S.' },
    ],
    razonSocial: {},
    alertas: [
      { id: 'a-1', nivel: 'PREVENTIVA', mensaje: { es: 'Oleaje alto en la bahía: las salidas en lancha pueden cancelarse.', en: 'High swell in the bay: boat trips may be cancelled.' }, zona: 'taganga', activa: true, fecha_expiracion: new Date(ahora + 3 * DIA).toISOString(), creada_en: new Date(ahora - DIA).toISOString(), version: 1 },
      { id: 'a-2', nivel: 'INFORMATIVA', mensaje: { es: 'El sendero cierra los lunes.', en: 'The trail is closed on Mondays.' }, servicio_id: 'quebrada-valencia', activa: true, fecha_expiracion: new Date(ahora + 60 * DIA).toISOString(), creada_en: new Date(ahora - 8 * DIA).toISOString(), version: 1 },
    ],
    perfiles: {}, comercial: { version: 1, telefono: '+57 300 000 0001', direccion: 'Calle 12 # 3-45, Taganga', politica_cancelacion: { es: 'Cancelación gratuita hasta el día anterior.', en: 'Free cancellation until the day before.' } },
    servicios: DEMO_SERVICIOS.map((s) => editable(s, ahora)),
    bitacora: [],
    idem: {},
  }
}

function editable(s, ahora) {
  return {
    id: s.id, prestador_id: 'demo-prestador', nombre: { es: s.es.nombre, en: s.en.nombre }, descripcion: { es: s.es.descripcion, en: s.en.descripcion },
    tipo: s.tipo, ubicacion: s.ubicacion, tarifa_base: s.tarifaBase, unidad_tarifa: 'POR_PERSONA', capacidad_aforo_diario: s.capacidadDiaria, atributos: {}, imagenes_urls: [],
    categoria: s.categoria, zona: s.zona, activo: true, version: 1, creado_en: new Date(ahora - 60 * DIA).toISOString(), actualizado_en: new Date(ahora - 30 * DIA).toISOString(),
  }
}

// Número estable a partir de un texto (los datos de ejemplo no cambian entre recargas)
const hash = (txt) => [...txt].reduce((a, c) => (Math.imul(a, 31) + c.charCodeAt(0)) >>> 0, 7)
const fechaIso = (d) => d.toISOString().slice(0, 10)
const dias = (desde, hasta) => {
  const out = []
  for (let t = Date.parse(`${desde}T00:00:00Z`); t <= Date.parse(`${hasta}T00:00:00Z`); t += DIA) out.push(fechaIso(new Date(t)))
  return out
}
const nivelDe = (i) => (i < 0.6 ? 'BAJO' : i <= 0.85 ? 'MEDIO' : 'ALTO')
const etiquetaNivel = { es: { BAJO: 'Bajo', MEDIO: 'Medio', ALTO: 'Alto' }, en: { BAJO: 'Low', MEDIO: 'Medium', ALTO: 'High' } }
const lang = (i) => (i === 'en' ? 'en' : 'es')

export function createMockGestion({
  storage = globalThis.localStorage, clock = { now: () => new Date() }, directorio, usuario, delayMs = 120,
  newId = nuevaClave,
} = {}) {
  const ahora = () => clock.now().getTime()
  const espera = (v) => (delayMs ? new Promise((r) => setTimeout(() => r(v), delayMs)) : Promise.resolve(v))
  let db = null
  const cargar = () => {
    if (db) return db
    try { db = JSON.parse(storage?.getItem(KEY)) } catch { db = null }
    db ??= semilla(ahora())
    return db
  }
  const guardar = () => { try { storage?.setItem(KEY, JSON.stringify(db)) } catch { /* sin almacenamiento */ } }
  const yo = () => { const u = usuario(); if (!u?.id) throw err(C.NO_AUTENTICADO, 'Inicia sesión.', 401); return u }
  const exigir = (...roles) => { const u = yo(); if (!roles.includes(u.rol)) throw err(C.ROL_INSUFICIENTE, 'Tu rol no puede hacer esto.', 403); return u }
  const auditar = (accion, usuarioId, detalles = {}, resultado = 'Exito') => {
    cargar().bitacora.unshift({ id: newId(), fecha: clock.now().toISOString(), usuario_id: usuarioId, accion, resultado, servicio_origen: 'iam-service', ip_origen: '127.0.0.1', detalles, correlation_id: newId(), event_id: newId() })
    db.bitacora = db.bitacora.slice(0, 300)
  }
  const mutar = async (fn) => { cargar(); const r = await fn(); guardar(); return espera(r) }
  const leer = async (fn) => { cargar(); return espera(await fn()) }

  /* ---------------- Perfil y documentos ---------------- */
  const estadoPrestador = (docs) => {
    const v = docs.filter((d) => d.vigente)
    const tiene = (t) => v.find((d) => d.tipo_documento === t)
    if (!tiene('RNT') || !tiene('RUT')) return v.some((d) => d.estado === 'Rechazado') ? 'rechazado' : 'incompleto'
    if (v.some((d) => d.estado === 'Rechazado')) return 'rechazado'
    return v.every((d) => d.estado === 'Aprobado') ? 'aprobado' : 'pendiente'
  }
  const razon = (id, fallback) => cargar().razonSocial[id] ?? fallback ?? ''
  const vistaDoc = (d, admin) => ({ id: d.id, tipo_documento: d.tipo_documento, estado: d.estado, vigente: d.vigente, tipo_contenido: d.tipo_contenido, tamano_bytes: d.tamano_bytes, motivo_rechazo: d.motivo_rechazo, fecha_subida: d.fecha_subida, revisado_en: d.revisado_en, ...(admin ? { revisado_por: d.revisado_por } : {}) })
  const docsDe = (id, soloVigentes = true) => cargar().docs.filter((d) => d.usuario_id === id && (!soloVigentes || d.vigente))
  const revision = (id, nombre) => ({ usuario_id: id, razon_social: razon(id, nombre), estado: estadoPrestador(docsDe(id)), documentos: docsDe(id, false).map((d) => vistaDoc(d, true)) })

  const account = {
    perfil: () => leer(async () => {
      const u = yo(); const base = await directorio.obtener(u.id)
      if (!base) throw err(C.NO_ENCONTRADO, 'La cuenta ya no existe.', 404)
      return { id: base.id, email: base.email, nombre: base.nombre_completo, rol: base.rol, idioma: base.idioma, razon_social: base.rol === 'Prestador' ? razon(base.id) : null, creado_en: base.creado_en }
    }),
    editarPerfil: (cambios) => mutar(async () => {
      const u = yo()
      const act = {}
      if (cambios.nombre) act.nombre_completo = cambios.nombre
      if (cambios.idioma) act.idioma = cambios.idioma
      const b = await directorio.actualizar(u.id, act)
      return { id: b.id, email: b.email, nombre: b.nombre_completo, rol: b.rol, idioma: b.idioma, razon_social: b.rol === 'Prestador' ? razon(b.id) : null, creado_en: b.creado_en }
    }),
    cambiarContrasena: ({ actual, nueva }) => mutar(async () => {
      const u = yo()
      if (!(await directorio.verificarPassword(u.id, actual))) throw err('PASSWORD_ACTUAL_INCORRECTA', 'La contraseña actual no es correcta.', 422)
      await directorio.cambiarPassword(u.id, nueva)
      auditar('PASSWORD_CHANGE', u.id)
    }),
    suprimirDatos: (password) => mutar(async () => {
      const u = yo()
      if (!(await directorio.verificarPassword(u.id, password))) throw err('CREDENCIALES_INVALIDAS', 'La contraseña no es correcta.', 401) // igual que el IAM real: 401, pero no es una sesión vencida
      if (u.rol === 'Admin' && (await directorio.todos()).filter((x) => x.rol === 'Admin' && x.activo).length <= 1) throw err('ULTIMO_ADMIN', 'Eres el último administrador.', 409)
      await directorio.suprimir(u.id)
      db.docs = db.docs.filter((d) => d.usuario_id !== u.id)
    }),
    misDocumentos: () => leer(() => { const u = exigir('Prestador'); const b = revision(u.id); return { ...b, documentos: docsDe(u.id).map((d) => vistaDoc(d, false)) } }),
    subirDocumento: ({ tipo, archivo, razonSocial }) => mutar(() => {
      const u = exigir('Prestador')
      const vigente = docsDe(u.id).find((d) => d.tipo_documento === tipo)
      if (vigente?.estado === 'Aprobado') throw err('DOCUMENTO_APROBADO', 'Ese documento ya fue aprobado.', 409)
      if (vigente) vigente.vigente = false
      if (tipo === 'RUT') db.razonSocial[u.id] = razonSocial
      const doc = { id: newId(), usuario_id: u.id, tipo_documento: tipo, estado: 'Pendiente', vigente: true, tipo_contenido: archivo.type, tamano_bytes: archivo.size, motivo_rechazo: null, fecha_subida: clock.now().toISOString(), revisado_en: null, revisado_por: null }
      db.docs.push(doc)
      return vistaDoc(doc, false)
    }),
  }

  /* ---------------- Administración ---------------- */
  const prestadoresVista = async () => {
    const reales = (await directorio.todos()).filter((u) => u.rol === 'Prestador').map((u) => ({ usuario_id: u.id, nombre_completo: u.nombre_completo, email: u.email, activo: u.activo, razon_social: razon(u.id, u.nombre_completo) }))
    return [...cargar().prestadoresExtra, ...reales].map((p) => ({ ...p, estado: estadoPrestador(docsDe(p.usuario_id)), documentos: docsDe(p.usuario_id).map((d) => vistaDoc(d, true)) }))
  }
  const admin = {
    usuarios: ({ rol, activo, q, pagina, tamano }) => leer(async () => {
      exigir('Admin')
      const texto = String(q ?? '').toLowerCase()
      const lista = (await directorio.todos()).filter((u) => (!rol || u.rol === rol) && (activo == null || u.activo === (activo === true || activo === 'true')) && (!texto || `${u.nombre_completo} ${u.email}`.toLowerCase().includes(texto)))
      return paginar(lista, pagina, tamano)
    }),
    cambiarRol: (id, { rol, motivo }) => mutar(async () => {
      const yoMismo = exigir('Admin')
      if (id === yoMismo.id) throw err('AUTOGESTION_NO_PERMITIDA', 'No puedes cambiar tu propia cuenta.', 409)
      const u = await directorio.obtener(id)
      if (!u) throw err('USUARIO_NO_ENCONTRADO', 'La cuenta no existe.', 404)
      if (u.rol === 'Admin' && rol !== 'Admin' && (await directorio.todos()).filter((x) => x.rol === 'Admin' && x.activo).length <= 1) throw err('ULTIMO_ADMIN', 'Quedarías sin administradores.', 409)
      const r = await directorio.actualizar(id, { rol })
      auditar('ROLE_CHANGE', yoMismo.id, { usuario_id: id, de: u.rol, a: rol, ...(motivo ? { motivo } : {}) })
      return r
    }),
    cambiarEstado: (id, { activo, motivo }) => mutar(async () => {
      const yoMismo = exigir('Admin')
      if (id === yoMismo.id) throw err('AUTOGESTION_NO_PERMITIDA', 'No puedes cambiar tu propia cuenta.', 409)
      const u = await directorio.obtener(id)
      if (!u) throw err('USUARIO_NO_ENCONTRADO', 'La cuenta no existe.', 404)
      if (!activo && u.rol === 'Admin' && (await directorio.todos()).filter((x) => x.rol === 'Admin' && x.activo).length <= 1) throw err('ULTIMO_ADMIN', 'Quedarías sin administradores.', 409)
      const r = await directorio.actualizar(id, { activo })
      auditar(activo ? 'USER_ACTIVATE' : 'USER_DEACTIVATE', yoMismo.id, { usuario_id: id, ...(motivo ? { motivo } : {}) })
      return r
    }),
    bitacora: ({ usuario_id, accion, resultado, servicio_origen, desde, hasta, pagina, tamano }) => mutar(() => {
      const a = exigir('Admin')
      const filtros = Object.fromEntries(Object.entries({ usuario_id, accion, resultado, servicio_origen, desde, hasta }).filter(([, v]) => v))
      const lista = cargar().bitacora.filter((e) => (!usuario_id || e.usuario_id === usuario_id) && (!accion || e.accion === accion) && (!resultado || e.resultado === resultado) && (!servicio_origen || e.servicio_origen === servicio_origen) && (!desde || Date.parse(e.fecha) >= Date.parse(desde)) && (!hasta || Date.parse(e.fecha) <= Date.parse(hasta)))
      const salida = paginar(lista, pagina, tamano)
      auditar('AUDIT_VIEW', a.id, { filtros }) // consultar la bitácora también queda en la bitácora (C-43)
      return salida
    }),
    prestadores: ({ estado, pagina, tamano }) => leer(async () => { exigir('Admin'); return paginar((await prestadoresVista()).filter((p) => !estado || p.estado === estado), pagina, tamano) }),
    documentosDePrestador: (id) => leer(async () => {
      exigir('Admin')
      const p = (await prestadoresVista()).find((x) => x.usuario_id === id)
      if (!p) throw err('USUARIO_NO_ENCONTRADO', 'La cuenta no existe.', 404)
      return { usuario_id: id, razon_social: p.razon_social, estado: p.estado, documentos: docsDe(id, false).map((d) => vistaDoc(d, true)) }
    }),
    urlDocumento: (documentoId) => mutar(() => {
      const a = exigir('Admin')
      const d = cargar().docs.find((x) => x.id === documentoId)
      if (!d) throw err('DOCUMENTO_NO_ENCONTRADO', 'El documento no existe.', 404)
      auditar('DOCUMENT_VIEW', a.id, { documento_id: documentoId })
      const blob = new Blob([`Documento simulado (${d.tipo_documento}) de ${d.usuario_id}.\nEn la plataforma real aquí se abre el PDF o la imagen subida.`], { type: 'text/plain;charset=utf-8' })
      return { url: URL.createObjectURL(blob), expira_en: new Date(ahora() + 5 * MIN).toISOString() }
    }),
    aprobarPrestador: (id) => mutar(async () => {
      const a = exigir('Admin')
      const p = (await prestadoresVista()).find((x) => x.usuario_id === id)
      if (!p) throw err('USUARIO_NO_ENCONTRADO', 'La cuenta no existe.', 404)
      const v = docsDe(id)
      if (!v.some((d) => d.tipo_documento === 'RNT') || !v.some((d) => d.tipo_documento === 'RUT')) throw err('DOCUMENTOS_INCOMPLETOS', 'Le falta el RNT o el RUT.', 409)
      if (v.some((d) => d.estado !== 'Pendiente')) throw err('DOCUMENTO_YA_REVISADO', 'El documento ya se revisó.', 409)
      v.forEach((d) => Object.assign(d, { estado: 'Aprobado', revisado_en: clock.now().toISOString(), revisado_por: a.id }))
      auditar('PROVIDER_APPROVE', a.id, { usuario_id: id })
      return revision(id, p.razon_social)
    }),
    rechazarPrestador: (id, documentos) => mutar(async () => {
      const a = exigir('Admin')
      const p = (await prestadoresVista()).find((x) => x.usuario_id === id)
      if (!p) throw err('USUARIO_NO_ENCONTRADO', 'La cuenta no existe.', 404)
      for (const { tipo, motivo } of documentos) {
        const d = docsDe(id).find((x) => x.tipo_documento === tipo)
        if (!d) throw err('DOCUMENTO_NO_ENCONTRADO', 'No hay un documento vigente de ese tipo.', 404)
        if (d.estado !== 'Pendiente') throw err('DOCUMENTO_YA_REVISADO', 'El documento ya se revisó.', 409)
        Object.assign(d, { estado: 'Rechazado', motivo_rechazo: motivo, revisado_en: clock.now().toISOString(), revisado_por: a.id })
      }
      auditar('PROVIDER_REJECT', a.id, { usuario_id: id })
      return revision(id, p.razon_social)
    }),
  }

  /* ---------------- Reseñas ---------------- */
  const pub = (r, idioma) => ({
    id: r.id, servicio_id: r.servicio_id, autor: r.autor, mes_visita: r.mes_visita, puntuacion: r.puntuacion, aspectos: r.aspectos, aspectos_etiquetas: Object.fromEntries(Object.keys(r.aspectos ?? {}).map((k) => [k, k])),
    comentario: r.comentario, respuesta: r.respuesta, creada_en: r.creada_en, editada_en: r.editada_en,
  })
  const propia = (r, idioma) => ({ ...pub(r, idioma), estado: r.estado, estado_etiqueta: r.estado, version: r.version })
  const encontrar = (id) => { const r = cargar().resenas.find((x) => x.id === id); if (!r) throw err(C.NO_ENCONTRADO, 'La reseña no existe.', 404); return r }
  const versionOk = (r, version) => { if (version == null || version === '') throw err('FALTA_IF_MATCH', 'Falta la versión.', 428); if (Number(String(version).replace(/\D/g, '')) !== r.version) throw err(C.VERSION_DISTINTA, 'La reseña cambió.', 409, { data: { version_actual: r.version } }) }
  const cuentan = (id) => cargar().resenas.filter((r) => r.servicio_id === id && r.estado !== 'OCULTA')
  const review = {
    resumen: (servicioId) => leer(() => {
      const rs = cuentan(servicioId)
      const distribucion = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 }
      rs.forEach((r) => { distribucion[r.puntuacion]++ })
      const aspectos = {}
      for (const a of ['LIMPIEZA', 'ATENCION', 'CALIDAD_PRECIO', 'SEGURIDAD', 'GUIANZA']) {
        const v = rs.map((r) => r.aspectos?.[a]).filter(Boolean)
        if (v.length) aspectos[a] = { promedio: Math.round((v.reduce((s, n) => s + n, 0) / v.length) * 10) / 10, total: v.length }
      }
      return { servicio_id: servicioId, total: rs.length, promedio: rs.length ? Math.round((rs.reduce((s, r) => s + r.puntuacion, 0) / rs.length) * 10) / 10 : null, distribucion, aspectos }
    }),
    resenasDeServicio: (servicioId, { orden, pagina, tamano, idioma }) => leer(() => {
      const lista = cargar().resenas.filter((r) => r.servicio_id === servicioId && r.estado === 'PUBLICADA')
      lista.sort((a, b) => (orden === 'mejores' ? b.puntuacion - a.puntuacion : orden === 'peores' ? a.puntuacion - b.puntuacion : Date.parse(b.creada_en) - Date.parse(a.creada_en)))
      const p = paginar(lista, pagina, tamano)
      return { ...p, items: p.items.map((r) => pub(r, idioma)) }
    }),
    escribir: (cuerpo, clave) => mutar(() => {
      const u = exigir('Turista')
      if (db.idem[clave]) return db.idem[clave]
      if (db.resenas.some((r) => r.servicio_id === cuerpo.servicio_id && r.turista_id === u.id)) throw err('YA_RESENADO', 'Ya reseñaste este servicio.', 409)
      if (!pendientesDe(u.id).some((p) => p.servicio_id === cuerpo.servicio_id)) throw err('NO_ELEGIBLE', 'Solo puedes reseñar un servicio que ya disfrutaste.', 403)
      const t = clock.now().toISOString()
      const r = { id: newId(), servicio_id: cuerpo.servicio_id, turista_id: u.id, autor: 'Tú', mes_visita: t.slice(0, 7), puntuacion: cuerpo.puntuacion, aspectos: cuerpo.aspectos ?? {}, comentario: cuerpo.comentario ?? '', respuesta: null, estado: 'PUBLICADA', version: 1, creada_en: t, editada_en: t, reportes: [] }
      db.resenas.push(r)
      db.idem[clave] = propia(r)
      return db.idem[clave]
    }),
    editar: (id, cuerpo, version) => mutar(() => {
      const u = exigir('Turista'); const r = encontrar(id)
      if (r.turista_id !== u.id) throw err(C.NO_ENCONTRADO, 'La reseña no existe.', 404)
      if (r.estado !== 'PUBLICADA') throw err('RESENA_EN_MODERACION', 'La reseña está en revisión.', 409)
      versionOk(r, version)
      Object.assign(r, { puntuacion: cuerpo.puntuacion, aspectos: cuerpo.aspectos ?? {}, comentario: cuerpo.comentario ?? '', version: r.version + 1, editada_en: clock.now().toISOString() })
      return propia(r)
    }),
    responder: (id, texto, version) => mutar(() => {
      const u = exigir('Prestador'); const r = encontrar(id)
      if (!cargar().servicios.some((s) => s.id === r.servicio_id)) throw err('NO_ES_DUENO', 'Esa reseña no es de tus servicios.', 403)
      if (r.estado === 'OCULTA') throw err('RESENA_EN_MODERACION', 'La reseña está oculta.', 409)
      versionOk(r, version)
      Object.assign(r, { respuesta: { texto, respondida_en: clock.now().toISOString() }, version: r.version + 1 })
      void u
      return propia(r)
    }),
    reportar: (id, cuerpo) => mutar(() => {
      const u = exigir('Turista', 'Prestador'); const r = encontrar(id)
      if (r.estado !== 'PUBLICADA' || r.turista_id === u.id) throw err(C.NO_ENCONTRADO, 'La reseña no existe.', 404)
      if (r.reportes.some((x) => x.usuario_id === u.id)) throw err('YA_REPORTADA', 'Ya reportaste esta reseña.', 409)
      const dueno = u.rol === 'Prestador' && cargar().servicios.some((s) => s.id === r.servicio_id)
      r.reportes.push({ motivo: cuerpo.motivo, detalle: cuerpo.detalle ?? '', rol_reportante: u.rol, es_dueno: dueno, reportado_en: clock.now().toISOString(), usuario_id: u.id })
      if (dueno || r.reportes.length >= 3) r.estado = 'EN_REVISION'
      return null
    }),
    moderar: (id, cuerpo, version) => mutar(() => {
      const a = exigir('Admin'); const r = encontrar(id)
      versionOk(r, version)
      r.estado = cuerpo.decision === 'OCULTAR' ? 'OCULTA' : 'PUBLICADA'
      r.version += 1
      const reportes = r.reportes
      r.reportes = []
      auditar('MODERACION', a.id, { resena_id: id, decision: cuerpo.decision, ...(cuerpo.motivo ? { motivo: cuerpo.motivo } : {}) })
      return { ...propia(r), turista_id: r.turista_id, reportes: reportes.map((x) => ({ ...x, motivo_etiqueta: x.motivo })) }
    }),
    misResenas: ({ pagina, tamano }) => leer(() => { const u = exigir('Turista'); const l = cargar().resenas.filter((r) => r.turista_id === u.id); return { ...paginar(l, pagina, tamano), items: paginar(l, pagina, tamano).items.map((r) => propia(r)) } }),
    pendientes: () => leer(() => pendientesDe(exigir('Turista').id)),
    resenasPrestador: ({ servicio_id, sin_respuesta, pagina, tamano }) => leer(() => {
      exigir('Prestador')
      const mios = new Set(cargar().servicios.map((s) => s.id))
      const l = cargar().resenas.filter((r) => mios.has(r.servicio_id) && r.estado !== 'OCULTA' && (!servicio_id || r.servicio_id === servicio_id) && (!sin_respuesta || !r.respuesta))
      const p = paginar(l, pagina, tamano)
      return { ...p, items: p.items.map((r) => propia(r)) }
    }),
    colaModeracion: ({ estado, pagina, tamano }) => leer(() => {
      exigir('Admin')
      const l = cargar().resenas.filter((r) => r.reportes.length && (!estado || r.estado === estado)).sort((a, b) => (a.estado === 'EN_REVISION' ? -1 : 1) - (b.estado === 'EN_REVISION' ? -1 : 1) || b.reportes.length - a.reportes.length)
      const p = paginar(l, pagina, tamano)
      return { ...p, items: p.items.map((r) => ({ ...propia(r), turista_id: r.turista_id, reportes: r.reportes.map((x) => ({ ...x, motivo_etiqueta: x.motivo })) })) }
    }),
  }
  // Servicios que el turista "ya disfrutó": en el simulador, los dos primeros que aún no reseñó
  function pendientesDe(id) {
    const ya = new Set(cargar().resenas.filter((r) => r.turista_id === id).map((r) => r.servicio_id))
    return DEMO_SERVICIOS.slice(0, 2).filter((s) => !ya.has(s.id)).map((s) => ({ servicio_id: s.id, ultima_visita: fechaIso(new Date(ahora() - 12 * DIA)) }))
  }

  /* ---------------- Oferta del prestador ---------------- */
  const catalogo = () => cargar().servicios
  const propio = (id) => { const s = catalogo().find((x) => x.id === id); if (!s) throw err(C.NO_ENCONTRADO, 'El servicio no existe.', 404); return s }
  const verOk = (s, version) => { if (version == null || version === '') throw err('FALTA_IF_MATCH', 'Falta la versión.', 428); if (Number(version) !== s.version) throw err(C.VERSION_DISTINTA, 'El servicio cambió.', 409, { data: { version_actual: s.version } }) }
  const zonaDe = (u) => { const z = ZONAS.reduce((m, x) => { const d = (x.centro.lat - u.lat) ** 2 + (x.centro.lon - u.lon) ** 2; return d < m.d ? { d, x } : m }, { d: Infinity }).x; return { codigo: z.codigo, nombre: z.nombre.es } }
  const offer = {
    perfilComercial: () => leer(() => { const u = exigir('Prestador'); return { id: u.id, razon_social: razon(u.id, 'Guías de Taganga'), activo: true, ...cargar().comercial } }),
    editarPerfilComercial: (cuerpo, version) => mutar(() => {
      const u = exigir('Prestador')
      if (Number(version) !== db.comercial.version) throw err(C.VERSION_DISTINTA, 'El perfil cambió.', 409)
      db.comercial = { ...db.comercial, ...cuerpo, version: db.comercial.version + 1 }
      return { id: u.id, razon_social: razon(u.id, 'Guías de Taganga'), activo: true, ...db.comercial }
    }),
    servicios: ({ pagina, tamano }) => leer(() => { exigir('Prestador'); return paginar(catalogo(), pagina, tamano) }),
    crearServicio: (cuerpo, clave) => mutar(() => {
      exigir('Prestador')
      if (db.idem[clave]) return db.idem[clave]
      const bloque = cuerpo.tipo
      const s = { id: newId(), prestador_id: 'demo-prestador', ...cuerpo, categoria: categoriaDe(bloque), zona: zonaDe(cuerpo.ubicacion), activo: true, version: 1, creado_en: clock.now().toISOString(), actualizado_en: clock.now().toISOString() }
      db.servicios.unshift(s)
      db.idem[clave] = s
      return s
    }),
    editarServicio: (id, cuerpo, version, clave) => mutar(() => {
      exigir('Prestador')
      if (db.idem[clave]) return db.idem[clave]
      const s = propio(id); verOk(s, version)
      Object.assign(s, cuerpo, { categoria: categoriaDe(cuerpo.tipo), zona: zonaDe(cuerpo.ubicacion), version: s.version + 1, actualizado_en: clock.now().toISOString() })
      db.idem[clave] = s
      return s
    }),
    desactivarServicio: (id, version) => mutar(() => { exigir('Prestador'); const s = propio(id); verOk(s, version); Object.assign(s, { activo: false, version: s.version + 1 }); return s }),
    reactivarServicio: (id, version) => mutar(() => { exigir('Prestador'); const s = propio(id); verOk(s, version); Object.assign(s, { activo: true, version: s.version + 1 }); return s }),
    // Sin almacenamiento real: la imagen queda como URL de datos (solo para la demostración; las fotos de la oferta se guardan en el navegador)
    subirImagen: (archivo) => leer(() => new Promise((res, rej) => { const fr = new FileReader(); fr.onload = () => res(fr.result); fr.onerror = () => rej(err(C.ERROR, 'No se pudo leer la imagen.')); fr.readAsDataURL(archivo) })),
    metricas: ({ desde, hasta }) => leer(() => {
      exigir('Prestador')
      const n = dias(desde, hasta).length
      return {
        desde, hasta,
        servicios: catalogo().map((s) => {
          const h = hash(s.id)
          const solicitadas = 1 + (h % 4); const confirmadas = 4 + (h % 9) + Math.floor(n / 10); const finalizadas = 2 + (h % 7) + Math.floor(n / 8)
          const rs = cuentan(s.id)
          return {
            servicio_id: s.id, nombre: s.nombre.es,
            reservas: { solicitadas, confirmadas, rechazadas: h % 3, canceladas: h % 2, finalizadas },
            personas_finalizadas: finalizadas * (2 + (h % 3)), ocupacion: Math.round(((30 + (h % 55)) / 100) * 100) / 100,
            calificacion_promedio: rs.length ? Math.round((rs.reduce((a, r) => a + r.puntuacion, 0) / rs.length) * 10) / 10 : undefined, total_resenas: rs.length, intenciones_visita: 3 + (h % 20),
          }
        }),
      }
    }),
    geocodificar: (direccion) => leer(() => {
      exigir('Prestador')
      const t = direccion.toLowerCase()
      const hallados = ZONAS.filter((z) => t.includes(z.nombre.es.toLowerCase()) || t.includes(z.codigo))
      return (hallados.length ? hallados : [ZONAS[0]]).map((z) => ({ lat: z.centro.lat, lon: z.centro.lon, etiqueta: `${z.nombre.es}, Santa Marta, Magdalena, Colombia` }))
    }),
    zonas: (idioma) => leer(() => ZONAS.map((z) => ({ id: z.id, codigo: z.codigo, nombre: z.nombre[lang(idioma)], centro: z.centro }))),
  }
  const categoriaDe = (tipo) => ({ HOTEL: 'ALOJAMIENTO', HOSTAL: 'ALOJAMIENTO', POSADA_ECOHOTEL: 'ALOJAMIENTO', GLAMPING_CAMPING: 'ALOJAMIENTO', APARTAMENTO_TURISTICO: 'ALOJAMIENTO', RESTAURANTE: 'GASTRONOMIA', CAFE_BAR: 'GASTRONOMIA', EXPERIENCIA_GASTRONOMICA: 'GASTRONOMIA', TOUR_GUIADO: 'AVENTURA', SENDERISMO: 'AVENTURA', DEPORTE_ACUATICO: 'AVENTURA', AVISTAMIENTO: 'NATURALEZA', RESERVA_PARQUE: 'NATURALEZA', ACCESO_PLAYA: 'PLAYA', ALQUILER_EQUIPO: 'PLAYA', TRANSPORTE_MARITIMO: 'TRANSPORTE', TRASLADO_TERRESTRE: 'TRANSPORTE' }[tipo] ?? 'CULTURA')

  /* ---------------- Entidad ---------------- */
  const personas = (zona, fecha) => { const z = ZONAS.find((x) => x.codigo === zona); const h = hash(`${zona}${fecha}`); return Math.round(z.capacidad * (0.35 + ((h % 60) / 100))) }
  const estadoAlerta = (a) => (!a.activa ? 'RETIRADA' : Date.parse(a.fecha_expiracion) <= ahora() ? 'VENCIDA' : 'VIGENTE')
  const vistaAlerta = (a, idioma) => ({ ...a, estado: estadoAlerta(a), estado_etiqueta: estadoAlerta(a), nivel_etiqueta: a.nivel, entidad_usuario_id: 'entidad-demo' })
  const capacidadDe = (fecha, zona, idioma) => ZONAS.filter((z) => !zona || z.codigo === zona).map((z) => {
    const activas = personas(z.codigo, fecha)
    const indice = Math.round((activas / z.capacidad) * 100) / 100
    return { zona: { codigo: z.codigo, nombre: z.nombre[lang(idioma)] }, fecha, nivel: nivelDe(indice), nivel_etiqueta: etiquetaNivel[lang(idioma)][nivelDe(indice)], personas_activas: activas, capacidad: z.capacidad, indice, calculado_en: clock.now().toISOString() }
  }).sort((a, b) => b.indice - a.indice)
  const serie = (desde, hasta, zona) => dias(desde, hasta).map((d) => {
    const z = zona ?? 'todas'; const h = hash(`${z}${d}`)
    return { periodo: d, ...(zona ? { zona } : {}), personas_solicitadas: 8 + (h % 20), personas_confirmadas: 30 + (h % 60), personas_finalizadas: 20 + (h % 50), personas_canceladas: h % 9 }
  })
  const poligono = (c, r = 0.03) => ({ type: 'MultiPolygon', coordinates: [[[[c.lon - r, c.lat - r], [c.lon + r, c.lat - r], [c.lon + r, c.lat + r], [c.lon - r, c.lat + r], [c.lon - r, c.lat - r]]]] })
  const entity = {
    alertas: ({ estado, pagina, tamano, idioma }) => leer(() => { exigir('Entidad', 'Admin'); return paginar(cargar().alertas.map((a) => vistaAlerta(a, idioma)).filter((a) => !estado || a.estado === estado), pagina, tamano) }),
    crearAlerta: (cuerpo) => mutar(() => {
      exigir('Entidad', 'Admin')
      if (cuerpo.zona && !ZONAS.some((z) => z.codigo === cuerpo.zona)) throw err(C.NO_ENCONTRADO, 'La zona no existe.', 404)
      if (cuerpo.servicio_id && !DEMO_SERVICIOS.some((s) => s.id === cuerpo.servicio_id)) throw err(C.NO_ENCONTRADO, 'El servicio no existe.', 404)
      const a = { id: newId(), ...cuerpo, activa: true, creada_en: clock.now().toISOString(), version: 1 }
      db.alertas.unshift(a)
      return vistaAlerta(a)
    }),
    editarAlerta: (id, cuerpo, version) => mutar(() => {
      exigir('Entidad', 'Admin')
      const a = db.alertas.find((x) => x.id === id)
      if (!a) throw err(C.NO_ENCONTRADO, 'La alerta no existe.', 404)
      if (!a.activa) throw err('ALERTA_RETIRADA', 'La alerta ya se retiró.', 409)
      if (Number(version) !== a.version) throw err(C.VERSION_DISTINTA, 'La alerta cambió.', 409, { data: { version_actual: a.version } })
      Object.assign(a, cuerpo, { version: a.version + 1 })
      return vistaAlerta(a)
    }),
    retirarAlerta: (id) => mutar(() => { exigir('Entidad', 'Admin'); const a = db.alertas.find((x) => x.id === id); if (!a) throw err(C.NO_ENCONTRADO, 'La alerta no existe.', 404); a.activa = false; return vistaAlerta(a) }),
    zonas: (idioma) => leer(() => ZONAS.map((z) => ({ id: z.id, codigo: z.codigo, nombre: z.nombre[lang(idioma)], centro: z.centro }))),
    demanda: ({ desde, hasta, zona, agrupacion }) => leer(() => { exigir('Entidad', 'Admin'); return { agrupacion: agrupacion ?? 'dia', serie: serie(desde, hasta, zona) } }),
    capacidad: ({ zona, fecha, idioma }) => leer(() => { exigir('Entidad', 'Admin', 'Turista'); return capacidadDe(fecha ?? fechaIso(clock.now()), zona, idioma) }),
    mapaCalor: ({ fecha, idioma }) => leer(() => {
      exigir('Entidad', 'Admin')
      return { type: 'FeatureCollection', features: capacidadDe(fecha ?? fechaIso(clock.now()), null, idioma).map((c) => ({ type: 'Feature', geometry: poligono(ZONAS.find((z) => z.codigo === c.zona.codigo).centro), properties: { codigo: c.zona.codigo, nombre: c.zona.nombre, indice: c.indice, nivel: c.nivel, nivel_etiqueta: c.nivel_etiqueta } })) }
    }),
    intenciones: ({ desde, hasta, zona }) => leer(() => { exigir('Entidad', 'Admin'); return ZONAS.filter((z) => !zona || z.codigo === zona).flatMap((z) => dias(desde, hasta).map((d) => ({ zona: z.codigo, fecha: d, intenciones: hash(`i${z.codigo}${d}`) % 14 }))).filter((x) => x.intenciones > 0) }),
    tablero: ({ desde, hasta, idioma }) => leer(() => {
      exigir('Entidad', 'Admin')
      const s = ZONAS.map((z) => ({ z, v: serie(desde, hasta, z.codigo) }))
      const suma = (k) => s.reduce((t, { v }) => t + v.reduce((a, x) => a + x[k], 0), 0)
      const zonas = s.map(({ z, v }) => ({ zona: { codigo: z.codigo, nombre: z.nombre[lang(idioma)] }, personas: v.reduce((a, x) => a + x.personas_confirmadas + x.personas_solicitadas + x.personas_finalizadas, 0), intenciones_visita: dias(desde, hasta).reduce((a, d) => a + (hash(`i${z.codigo}${d}`) % 14), 0) })).sort((a, b) => b.personas - a.personas).slice(0, 5)
      return {
        desde, hasta, totales: { periodo: desde, personas_solicitadas: suma('personas_solicitadas'), personas_confirmadas: suma('personas_confirmadas'), personas_finalizadas: suma('personas_finalizadas'), personas_canceladas: suma('personas_canceladas') },
        capacidad_hoy: capacidadDe(fechaIso(clock.now()), null, idioma), zonas_mas_demandadas: zonas, alertas_vigentes: cargar().alertas.filter((a) => estadoAlerta(a) === 'VIGENTE').length,
      }
    }),
    reporteCsv: ({ desde, hasta, zona }) => leer(() => {
      exigir('Entidad', 'Admin')
      const filas = [['Fecha', 'Zona', 'Servicio', 'Categoría', 'Tipo', 'Personas solicitadas', 'Personas confirmadas', 'Personas finalizadas', 'Personas canceladas', 'Intenciones de visita']]
      for (const s of DEMO_SERVICIOS) {
        const z = s.zona.codigo
        if (zona && zona !== z) continue
        for (const d of dias(desde, hasta)) {
          const h = hash(`${s.id}${d}`)
          if (h % 3) continue
          filas.push([d, s.zona.nombre, s.es.nombre, s.categoria, s.tipo, 2 + (h % 6), 4 + (h % 12), h % 9, h % 3, h % 5])
        }
      }
      return { texto: `﻿${filas.map((f) => f.map((c) => `"${String(c).replaceAll('"', '""')}"`).join(';')).join('\r\n')}\r\n`, nombre: `demanda_${desde}_${hasta}${zona ? `_${zona}` : ''}.csv` }
    }),
  }

  return { account, admin, review, offer, entity }
}
