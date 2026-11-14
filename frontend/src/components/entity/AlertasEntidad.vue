<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { catalogUseCases, entityUseCases } from '../../composition'
import { useGestion } from '../../ui/useGestion'
import { useOnline } from '../../ui/useOnline'
import { fmtMomento } from '../../ui/format'
import EstadoCarga from '../shared/EstadoCarga.vue'
import Paginacion from '../shared/Paginacion.vue'

/*
 * UC26 · Alertas oficiales. Se publican para una zona o para un servicio, con nivel (informativa, preventiva o crítica) y vigencia.
 * Retirar no borra. Editar exige la versión: varias personas de la Entidad pueden administrar las mismas alertas (409 si alguien la cambió).
 */
const NIVELES = ['INFORMATIVA', 'PREVENTIVA', 'CRITICA']
const { t, locale } = useI18n()
const { mensaje, camposDe, sesionVencida } = useGestion()
const enLinea = useOnline()

const estado = ref('VIGENTE')
const datos = ref({ items: [], pagina: 1, tamano: 10, total: 0 })
const zonas = ref([])
const servicios = ref([])
const cargando = ref(true)
const error = ref('')
const aviso = ref('')
const form = reactive({ abierto: false, id: '', version: 0, nivel: 'INFORMATIVA', es: '', en: '', destino: 'zona', zona: '', servicioId: '', expira: '', enviando: false, error: '', campos: {} })

async function cargar(pagina = 1) {
  cargando.value = true; error.value = ''
  try { datos.value = await entityUseCases.alertas({ estado: estado.value || undefined, pagina, tamano: 10, idioma: locale.value }) }
  catch (e) { if (!sesionVencida(e)) error.value = mensaje(e, 'entidad') } finally { cargando.value = false }
}
onMounted(async () => {
  cargar()
  zonas.value = await entityUseCases.zonas(locale.value).catch(() => [])
  servicios.value = (await catalogUseCases.explorar({ pagina: 1, tamano: 100 }, { idioma: locale.value }).catch(() => ({ items: [] }))).items
})
watch([estado, locale], () => cargar())

const aLocal = (iso) => { const d = new Date(iso); const p = (x) => String(x).padStart(2, '0'); return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}` }
function nueva() { Object.assign(form, { abierto: true, id: '', version: 0, nivel: 'INFORMATIVA', es: '', en: '', destino: 'zona', zona: '', servicioId: '', expira: aLocal(new Date(Date.now() + 7 * 86_400_000)), error: '', campos: {} }); aviso.value = '' }
function editar(a) { Object.assign(form, { abierto: true, id: a.id, version: a.version, nivel: a.nivel, es: a.mensaje.es, en: a.mensaje.en ?? '', expira: aLocal(a.fecha_expiracion), error: '', campos: {} }); aviso.value = '' }

async function guardar() {
  form.enviando = true; form.error = ''; form.campos = {}
  try {
    const comun = { nivel: form.nivel, mensaje: { es: form.es, en: form.en }, fechaExpiracion: form.expira }
    if (form.id) await entityUseCases.editarAlerta(form.id, comun, form.version)
    else await entityUseCases.crearAlerta({ ...comun, ...(form.destino === 'zona' ? { zona: form.zona } : { servicioId: form.servicioId }) })
    aviso.value = t(form.id ? 'entidad.alertUpdated' : 'entidad.alertCreated')
    form.abierto = false
    await cargar(datos.value.pagina)
  } catch (e) {
    if (sesionVencida(e)) return
    form.campos = camposDe(e); form.error = e.code === 'VALIDACION' && e.campos?.length && !e.status ? t('oferta.fixErrors') : mensaje(e, 'entidad')
    if (e.code === 'VERSION_DISTINTA' || e.code === 'ALERTA_RETIRADA') await cargar(datos.value.pagina)
  } finally { form.enviando = false }
}
async function retirar(a) {
  try { await entityUseCases.retirarAlerta(a.id); aviso.value = t('entidad.alertRetired'); await cargar(datos.value.pagina) }
  catch (e) { if (!sesionVencida(e)) error.value = mensaje(e, 'entidad') }
}
const destinoDe = (a) => (a.servicio_id ? servicios.value.find((s) => s.id === a.servicio_id)?.nombre ?? t('entidad.aService') : zonas.value.find((z) => z.codigo === a.zona)?.nombre ?? a.zona)
const NIVEL = { INFORMATIVA: 'bg-sand/15 text-ink-control', PREVENTIVA: 'bg-warn-bg text-warn', CRITICA: 'bg-danger-bg text-danger' }
const ESTADO = { VIGENTE: 'bg-ok-bg text-ok', VENCIDA: 'bg-sand/20 text-ink-control', RETIRADA: 'bg-sand/20 text-ink-control' }
</script>

<template>
  <section aria-labelledby="h-ale">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div><h2 id="h-ale" class="text-lg font-bold text-navy-darkest">{{ t('entidad.alertsTitle') }}</h2><p class="mt-1 max-w-2xl text-sm text-muted">{{ t('entidad.alertsLead') }}</p></div>
      <button v-if="!form.abierto" type="button" class="btn-primario" :disabled="!enLinea" @click="nueva">+ {{ t('entidad.newAlert') }}</button>
    </div>
    <p v-if="aviso" class="mt-4 rounded-xl bg-ok-bg px-4 py-2.5 text-sm text-ok" role="status">{{ aviso }}</p>

    <form v-if="form.abierto" class="tarjeta mt-4 space-y-4" @submit.prevent="guardar">
      <h3 class="font-bold text-navy-darkest">{{ form.id ? t('entidad.editAlert') : t('entidad.newAlert') }}</h3>
      <div class="grid gap-4 sm:grid-cols-2">
        <label><span class="campo-etiqueta">{{ t('entidad.level') }}</span><select v-model="form.nivel" class="campo-input"><option v-for="n in NIVELES" :key="n" :value="n">{{ t(`entidad.levels.${n}`) }}</option></select></label>
        <label><span class="campo-etiqueta">{{ t('entidad.expires') }}</span><input v-model="form.expira" type="datetime-local" class="campo-input" required :aria-invalid="!!form.campos.fecha_expiracion" /><span v-if="form.campos.fecha_expiracion" class="campo-error">{{ form.campos.fecha_expiracion }}</span></label>
        <label><span class="campo-etiqueta">{{ t('entidad.messageEs') }} *</span><textarea v-model="form.es" rows="3" class="campo-input" required :aria-invalid="!!form.campos.mensaje" /><span v-if="form.campos.mensaje" class="campo-error">{{ form.campos.mensaje }}</span></label>
        <label><span class="campo-etiqueta">{{ t('entidad.messageEn') }}</span><textarea v-model="form.en" rows="3" class="campo-input" /></label>
      </div>
      <fieldset v-if="!form.id" class="space-y-3">
        <legend class="campo-etiqueta">{{ t('entidad.appliesTo') }}</legend>
        <div class="flex gap-5 text-sm"><label class="flex items-center gap-2"><input v-model="form.destino" type="radio" value="zona" class="accent-navy" />{{ t('entidad.zone') }}</label><label class="flex items-center gap-2"><input v-model="form.destino" type="radio" value="servicio" class="accent-navy" />{{ t('entidad.aService') }}</label></div>
        <select v-if="form.destino === 'zona'" v-model="form.zona" class="campo-input" :aria-label="t('entidad.zone')"><option value="">—</option><option v-for="z in zonas" :key="z.codigo" :value="z.codigo">{{ z.nombre }}</option></select>
        <select v-else v-model="form.servicioId" class="campo-input" :aria-label="t('entidad.aService')"><option value="">—</option><option v-for="s in servicios" :key="s.id" :value="s.id">{{ s.nombre }}</option></select>
        <p v-if="form.campos.destino" class="campo-error">{{ form.campos.destino }}</p>
      </fieldset>
      <p v-else class="text-xs text-muted">{{ t('entidad.targetFixed') }}</p>
      <p v-if="form.error" class="campo-error" role="alert">{{ form.error }}</p>
      <div class="flex gap-3"><button type="submit" class="btn-primario" :disabled="form.enviando || !enLinea">{{ form.enviando ? t('gestion.saving') : t('gestion.save') }}</button><button type="button" class="btn-secundario" @click="form.abierto = false">{{ t('gestion.cancel') }}</button></div>
    </form>

    <label class="mt-5 block max-w-xs"><span class="campo-etiqueta">{{ t('admin.status') }}</span>
      <select v-model="estado" class="campo-input"><option value="">{{ t('gestion.all') }}</option><option v-for="e in ['VIGENTE', 'VENCIDA', 'RETIRADA']" :key="e" :value="e">{{ t(`entidad.alertStates.${e}`) }}</option></select>
    </label>

    <div class="mt-4">
      <EstadoCarga :cargando="cargando" :error="error" :vacio="!datos.items.length" :texto-vacio="t('entidad.alertsEmpty')" alto="h-32" @reintentar="cargar(datos.pagina)">
        <ul class="space-y-3">
          <li v-for="a in datos.items" :key="a.id" class="tarjeta !p-4">
            <div class="flex flex-wrap items-center gap-2"><span class="pildora" :class="NIVEL[a.nivel]">{{ t(`entidad.levels.${a.nivel}`) }}</span><span class="pildora" :class="ESTADO[a.estado]">{{ t(`entidad.alertStates.${a.estado}`) }}</span><span class="font-mono text-xs text-muted">{{ destinoDe(a) }} · {{ t('entidad.until', { fecha: fmtMomento(a.fecha_expiracion, locale) }) }}</span></div>
            <p class="mt-2 text-sm text-ink-control">{{ a.mensaje.es }}</p>
            <p v-if="a.mensaje.en" class="mt-0.5 text-xs italic text-muted">{{ a.mensaje.en }}</p>
            <div v-if="a.activa" class="mt-2 flex gap-4 text-sm"><button type="button" class="font-medium text-navy underline hover:text-teal" :disabled="!enLinea" @click="editar(a)">{{ t('gestion.edit') }}</button><button type="button" class="font-medium text-danger underline" :disabled="!enLinea" @click="retirar(a)">{{ t('entidad.retire') }}</button></div>
          </li>
        </ul>
        <Paginacion :pagina="datos.pagina" :tamano="datos.tamano" :total="datos.total" @cambiar="cargar" />
      </EstadoCarga>
    </div>
  </section>
</template>
