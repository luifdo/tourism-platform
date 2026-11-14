// Traduce los errores de autenticación a lo que pinta un formulario (sin lógica de negocio)

/** Nombre del campo en la API de iam-service -> nombre del campo en los formularios */
const CAMPO_DE_API = {
  email: 'email', password: 'password', nombre_completo: 'nombre', rol: 'rol',
  habeas_data_aceptado: 'habeasData', es_mayor_de_edad: 'mayorDeEdad',
}
/** Código de error de dominio -> campo del formulario al que pertenece */
const CAMPO_DE_CODIGO = {
  EMAIL_INVALIDO: 'email', EMAIL_EN_USO: 'email', PASSWORD_INVALIDA: 'password', NOMBRE_INVALIDO: 'nombre',
  HABEAS_DATA_REQUERIDO: 'habeasData', MAYORIA_DE_EDAD_REQUERIDA: 'mayorDeEdad', ROL_NO_PERMITIDO: 'rol',
}

/**
 * Separa un AuthError en errores por campo y un mensaje general.
 * @returns {{ campos: Record<string, {codigo?: string, mensaje: string}>, general: string|null }}
 */
export function repartirError(error) {
  const campos = {}
  for (const c of error.campos ?? []) {
    const campo = CAMPO_DE_API[c.campo] ?? c.campo
    if (!campos[campo]) campos[campo] = { codigo: c.codigo, mensaje: c.mensaje }
  }
  const delCodigo = CAMPO_DE_CODIGO[error.code]
  if (delCodigo && !campos[delCodigo]) campos[delCodigo] = { codigo: error.code, mensaje: error.message }
  return { campos, general: Object.keys(campos).length ? null : error.code }
}

/** Texto traducido de un código de error (con uno genérico si no hay traducción) */
export const textoDeError = (code, t, te) => t(`auth.errors.${te(`auth.errors.${code}`) ? code : 'generic'}`)
