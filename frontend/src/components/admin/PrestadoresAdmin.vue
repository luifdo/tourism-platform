<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { adminUseCases } from '../../composition'
import { useGestion } from '../../ui/useGestion'
import { useOnline } from '../../ui/useOnline'
import { fmtMomento } from '../../ui/format'
import EstadoCarga from '../shared/EstadoCarga.vue'
import Paginacion from '../shared/Paginacion.vue'

/*
 * UC28 · Aprobar o rechazar prestadores. La cola son las cuentas con el RNT y el RUT subidos y sin revisar (`pendiente`).
 * Aprobar da por buenos los dos documentos vigentes; rechazar exige un motivo por documento, que el prestador verá.
 * "Ver" abre el documento con un enlace que vale 5 minutos y queda en la bitácora.
 */
const { t, locale } = useI18n()
const { mensaje, camposDe, sesionVencida } = useGestion()
const enLinea = useOnline()

const estado = ref('pendiente')
const datos = ref({ items: [], pagina: 1, tamano: 10, total: 0 })
const cargando = ref(true)
const error = ref('')
const accion = reactive({ id: '', modo: '', motivos: { RNT: '', RUT: '' }, tipos: { RNT: true, RUT: true }, enviando: false, error: '', campos: {} })
const aviso = ref('')
const verError = ref('')

async function cargar(pagina = 1) {
  cargando.value = true; error.value = ''
  try { datos.value = await adminUseCases.prestadores({ estado: estado.value || undefined, pagina, tamano: 10 }) }
  catch (e) { if (!sesionVencida(e)) error.value = mensaje(e, 'admin') } finally { cargando.value = false }
}
onMounted(() => cargar())
watch(estado, () => cargar())

const docs = (p) => p.documentos.filter((d) => d.vigente)
const colorEstado = { pendiente: 'bg-warn-bg text-warn', aprobado: 'bg-ok-bg text-ok', rechazado: 'bg-danger-bg text-danger', incompleto: 'bg-sand/15 text-ink-control' }
const kb = (b) => `${Math.max(1, Math.round(b / 1024))} KB`
const abrirAccion = (p, modo) => Object.assign(accion, { id: p.usuario_id, modo, motivos: { RNT: '', RUT: '' }, tipos: { RNT: true, RUT: true }, error: '', campos: {} })

async function ver(d) {
  verError.value = ''
  try { const { url } = await adminUseCases.urlDocumento(d.id); window.open(url, '_blank', 'noopener,noreferrer') }
  catch (e) { if (!sesionVencida(e)) verError.value = mensaje(e, 'admin') }
}
async function confirmar(p) {
  accion.enviando = true; accion.error = ''; accion.campos = {}
  try {
    if (accion.modo === 'aprobar') await adminUseCases.aprobarPrestador(p.usuario_id)
    else await adminUseCases.rechazarPrestador(p.usuario_id, ['RNT', 'RUT'].filter((k) => accion.tipos[k] && docs(p).some((d) => d.tipo_documento === k)).map((k) => ({ tipo: k, motivo: accion.motivos[k] })))
    aviso.value = t(accion.modo === 'aprobar' ? 'admin.approved' : 'admin.rejected', { nombre: p.razon_social || p.nombre_completo })
    accion.id = ''
    await cargar(datos.value.pagina)
  } catch (e) {
    if (sesionVencida(e)) return
    accion.error = mensaje(e, 'admin'); accion.campos = camposDe(e)
    if (e.status === 409) await cargar(datos.value.pagina)
  } finally { accion.enviando = false }
}
</script>

<template>
  <section aria-labelledby="h-prest">
    <h2 id="h-prest" class="text-lg font-bold text-navy-darkest">{{ t('admin.providersTitle') }}</h2>
    <p class="mt-1 max-w-2xl text-sm text-muted">{{ t('admin.providersLead') }}</p>
    <label class="mt-4 block max-w-xs"><span class="campo-etiqueta">{{ t('admin.status') }}</span>
      <select v-model="estado" class="campo-input"><option value="">{{ t('gestion.all') }}</option><option v-for="e in ['pendiente', 'incompleto', 'rechazado', 'aprobado']" :key="e" :value="e">{{ t(`verif.states.${e}`) }}</option></select>
    </label>
    <p v-if="aviso" class="mt-4 rounded-xl bg-ok-bg px-4 py-2.5 text-sm text-ok" role="status">{{ aviso }}</p>
    <p v-if="verError" class="campo-error" role="alert">{{ verError }}</p>

    <div class="mt-5">
      <EstadoCarga :cargando="cargando" :error="error" :vacio="!datos.items.length" :texto-vacio="t('admin.providersEmpty')" alto="h-40" @reintentar="cargar(datos.pagina)">
        <ul class="space-y-4">
          <li v-for="p in datos.items" :key="p.usuario_id" class="tarjeta">
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span class="font-semibold text-navy-darkest">{{ p.razon_social || p.nombre_completo }}</span>
              <span class="pildora" :class="colorEstado[p.estado]">{{ t(`verif.states.${p.estado}`) }}</span>
              <span v-if="!p.activo" class="pildora bg-danger-bg text-danger">{{ t('admin.suspended') }}</span>
            </div>
            <p class="mt-0.5 font-mono text-xs text-muted">{{ p.nombre_completo }} · {{ p.email }}</p>

            <ul class="mt-3 grid gap-2 sm:grid-cols-2">
              <li v-for="d in docs(p)" :key="d.id" class="rounded-xl bg-cream p-3 text-sm">
                <p class="flex flex-wrap items-center gap-2"><b>{{ t(`verif.docs.${d.tipo_documento}`) }}</b><span class="pildora" :class="{ Pendiente: 'bg-warn-bg text-warn', Aprobado: 'bg-ok-bg text-ok', Rechazado: 'bg-danger-bg text-danger' }[d.estado]">{{ t(`verif.docStates.${d.estado}`) }}</span></p>
                <p class="mt-1 text-xs text-muted">{{ fmtMomento(d.fecha_subida, locale) }} · {{ kb(d.tamano_bytes) }}</p>
                <p v-if="d.motivo_rechazo" class="mt-1 text-xs text-danger">{{ d.motivo_rechazo }}</p>
                <button type="button" class="mt-1.5 text-sm font-medium text-navy underline hover:text-teal" @click="ver(d)">{{ t('admin.openDoc') }} ↗</button>
              </li>
              <li v-if="!docs(p).length" class="text-sm text-muted">{{ t('admin.noDocs') }}</li>
            </ul>

            <div v-if="p.estado === 'pendiente' && accion.id !== p.usuario_id" class="mt-4 flex flex-wrap gap-3">
              <button type="button" class="btn-primario" :disabled="!enLinea" @click="abrirAccion(p, 'aprobar')">{{ t('admin.approve') }}</button>
              <button type="button" class="btn-peligro" :disabled="!enLinea" @click="abrirAccion(p, 'rechazar')">{{ t('admin.reject') }}</button>
            </div>

            <form v-if="accion.id === p.usuario_id" class="mt-4 space-y-3 rounded-xl border border-sand/40 p-4" @submit.prevent="confirmar(p)">
              <p v-if="accion.modo === 'aprobar'" class="text-sm text-ink-control">{{ t('admin.approveConfirm') }}</p>
              <template v-else>
                <p class="text-sm text-ink-control">{{ t('admin.rejectHelp') }}</p>
                <div v-for="k in ['RNT', 'RUT']" :key="k" class="space-y-1">
                  <label class="flex items-center gap-2 text-sm font-medium text-ink-control"><input v-model="accion.tipos[k]" type="checkbox" class="size-4 accent-danger" :disabled="!docs(p).some((d) => d.tipo_documento === k)" />{{ t(`verif.docs.${k}`) }}</label>
                  <textarea v-if="accion.tipos[k] && docs(p).some((d) => d.tipo_documento === k)" v-model="accion.motivos[k]" rows="2" maxlength="500" class="campo-input" :placeholder="t('admin.rejectReason')" :aria-label="`${t('admin.rejectReason')} ${k}`" :aria-invalid="!!accion.campos[`motivo_${k}`]" />
                  <p v-if="accion.campos[`motivo_${k}`]" class="campo-error">{{ accion.campos[`motivo_${k}`] }}</p>
                </div>
              </template>
              <p v-if="accion.error" class="campo-error" role="alert">{{ accion.error }}</p>
              <div class="flex gap-3">
                <button type="submit" :class="accion.modo === 'aprobar' ? 'btn-primario' : 'btn-peligro'" :disabled="accion.enviando">{{ accion.enviando ? t('gestion.sending') : t('gestion.confirm') }}</button>
                <button type="button" class="btn-secundario" @click="accion.id = ''">{{ t('gestion.cancel') }}</button>
              </div>
            </form>
          </li>
        </ul>
        <Paginacion :pagina="datos.pagina" :tamano="datos.tamano" :total="datos.total" @cambiar="cargar" />
      </EstadoCarga>
    </div>
  </section>
</template>
