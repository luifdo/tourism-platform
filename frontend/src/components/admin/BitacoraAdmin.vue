<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { adminUseCases } from '../../composition'
import { useGestion } from '../../ui/useGestion'
import { fmtMomento } from '../../ui/format'
import EstadoCarga from '../shared/EstadoCarga.vue'
import Paginacion from '../shared/Paginacion.vue'

/*
 * UC33 · Bitácora de auditoría: de lo más reciente a lo más antiguo. Consultarla también queda registrado (AUDIT_VIEW).
 * Las fechas se piden en la hora del navegador y se mandan con zona horaria (el servicio rechaza fechas sin zona).
 */
const props = defineProps({ usuarioId: { type: String, default: '' } }) // llega desde «Ver en la bitácora» de la lista de usuarios
const { t, locale } = useI18n()
const { mensaje, camposDe, sesionVencida } = useGestion()

const f = reactive({ accion: '', resultado: '', servicio_origen: '', usuario_id: '', desde: '', hasta: '' })
const datos = ref({ items: [], pagina: 1, tamano: 20, total: 0 })
const cargando = ref(true)
const error = ref('')
const abierto = ref('')

const iso = (local) => (local ? new Date(local).toISOString() : undefined)
async function cargar(pagina = 1) {
  cargando.value = true; error.value = ''
  try {
    datos.value = await adminUseCases.bitacora({
      pagina, tamano: 20, accion: f.accion.trim() || undefined, resultado: f.resultado || undefined, servicio_origen: f.servicio_origen.trim() || undefined,
      usuario_id: f.usuario_id.trim() || undefined, desde: iso(f.desde), hasta: iso(f.hasta),
    })
  } catch (e) {
    if (sesionVencida(e)) return
    error.value = camposDe(e).desde ?? mensaje(e, 'admin')
  } finally { cargando.value = false }
}
onMounted(() => { if (props.usuarioId) f.usuario_id = props.usuarioId; cargar() })
watch(() => props.usuarioId, (id) => { if (id) { f.usuario_id = id; cargar() } })
const colorResultado = { Exito: 'bg-ok-bg text-ok', Denegado: 'bg-warn-bg text-warn', Error: 'bg-danger-bg text-danger' }
const limpiar = () => { Object.assign(f, { accion: '', resultado: '', servicio_origen: '', usuario_id: '', desde: '', hasta: '' }); cargar() }
</script>

<template>
  <section aria-labelledby="h-bit">
    <h2 id="h-bit" class="text-lg font-bold text-navy-darkest">{{ t('admin.auditTitle') }}</h2>
    <p class="mt-1 max-w-2xl text-sm text-muted">{{ t('admin.auditLead') }}</p>

    <form class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3" role="search" @submit.prevent="cargar()">
      <label><span class="campo-etiqueta">{{ t('admin.action') }}</span><input v-model="f.accion" class="campo-input" maxlength="50" placeholder="LOGIN, ROLE_CHANGE…" /></label>
      <label><span class="campo-etiqueta">{{ t('admin.result') }}</span><select v-model="f.resultado" class="campo-input"><option value="">{{ t('gestion.all') }}</option><option v-for="r in ['Exito', 'Denegado', 'Error']" :key="r" :value="r">{{ t(`admin.results.${r}`) }}</option></select></label>
      <label><span class="campo-etiqueta">{{ t('admin.origin') }}</span><input v-model="f.servicio_origen" class="campo-input" maxlength="50" placeholder="iam-service" /></label>
      <label><span class="campo-etiqueta">{{ t('admin.userId') }}</span><input v-model="f.usuario_id" class="campo-input" placeholder="UUID" /></label>
      <label><span class="campo-etiqueta">{{ t('gestion.from') }}</span><input v-model="f.desde" type="datetime-local" class="campo-input" /></label>
      <label><span class="campo-etiqueta">{{ t('gestion.to') }}</span><input v-model="f.hasta" type="datetime-local" class="campo-input" /></label>
      <div class="flex gap-3 sm:col-span-2 lg:col-span-3"><button type="submit" class="btn-primario">{{ t('admin.searchGo') }}</button><button type="button" class="btn-secundario" @click="limpiar">{{ t('gestion.clear') }}</button></div>
    </form>

    <div class="mt-5">
      <EstadoCarga :cargando="cargando" :error="error" :vacio="!datos.items.length" :texto-vacio="t('admin.auditEmpty')" alto="h-48" @reintentar="cargar(datos.pagina)">
        <div class="overflow-x-auto rounded-card border border-sand/30 bg-white shadow-card">
          <table class="w-full min-w-[760px] text-left text-sm">
            <caption class="sr-only">{{ t('admin.auditTitle') }}</caption>
            <thead class="bg-cream font-mono text-[10px] uppercase tracking-[.12em] text-muted"><tr>
              <th scope="col" class="px-4 py-3">{{ t('admin.when') }}</th><th scope="col" class="px-3 py-3">{{ t('admin.action') }}</th><th scope="col" class="px-3 py-3">{{ t('admin.result') }}</th><th scope="col" class="px-3 py-3">{{ t('admin.origin') }}</th><th scope="col" class="px-3 py-3">{{ t('admin.userId') }}</th><th scope="col" class="px-3 py-3"><span class="sr-only">{{ t('admin.details') }}</span></th>
            </tr></thead>
            <tbody class="divide-y divide-sand/20">
              <template v-for="e in datos.items" :key="e.id">
                <tr>
                  <td class="whitespace-nowrap px-4 py-2.5 tabular-nums">{{ fmtMomento(e.fecha, locale) }}</td>
                  <td class="px-3 py-2.5 font-mono text-xs">{{ e.accion }}</td>
                  <td class="px-3 py-2.5"><span class="pildora" :class="colorResultado[e.resultado]">{{ t(`admin.results.${e.resultado}`) }}</span></td>
                  <td class="px-3 py-2.5 text-xs">{{ e.servicio_origen }}</td>
                  <td class="max-w-[140px] truncate px-3 py-2.5 font-mono text-[11px] text-muted" :title="e.usuario_id">{{ e.usuario_id }}</td>
                  <td class="px-3 py-2.5 text-right"><button type="button" class="text-xs font-medium text-navy underline" :aria-expanded="abierto === e.id" @click="abierto = abierto === e.id ? '' : e.id">{{ t('admin.details') }}</button></td>
                </tr>
                <tr v-if="abierto === e.id" class="bg-cream/60"><td colspan="6" class="px-4 py-3">
                  <!-- Los detalles son texto: se muestran como JSON legible, nunca como HTML -->
                  <pre class="overflow-x-auto whitespace-pre-wrap break-words font-mono text-xs text-ink-control">{{ JSON.stringify(e.detalles ?? {}, null, 2) }}</pre>
                  <p class="mt-2 font-mono text-[11px] text-muted">IP {{ e.ip_origen }} · correlation {{ e.correlation_id }}</p>
                </td></tr>
              </template>
            </tbody>
          </table>
        </div>
        <Paginacion :pagina="datos.pagina" :tamano="datos.tamano" :total="datos.total" @cambiar="cargar" />
      </EstadoCarga>
    </div>
  </section>
</template>
