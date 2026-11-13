<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { catalogUseCases, reviewUseCases } from '../../composition'
import { useGestion } from '../../ui/useGestion'
import { useOnline } from '../../ui/useOnline'
import { fmtMomento } from '../../ui/format'
import EstadoCarga from '../shared/EstadoCarga.vue'
import Paginacion from '../shared/Paginacion.vue'
import Estrellas from '../reviews/Estrellas.vue'

/*
 * UC29 · Moderar reseñas reportadas. La cola trae primero las que están en revisión (ocultas a la espera de decisión) y luego
 * las publicadas con reportes. Publicar la deja visible y cierra sus reportes; ocultar exige un motivo y la saca del promedio.
 */
const { t, locale } = useI18n()
const { mensaje, sesionVencida } = useGestion()
const enLinea = useOnline()

const estado = ref('')
const datos = ref({ items: [], pagina: 1, tamano: 10, total: 0 })
const nombres = ref({})
const cargando = ref(true)
const error = ref('')
const aviso = ref('')
const accion = reactive({ id: '', decision: '', motivo: '', enviando: false, error: '' })

async function cargar(pagina = 1) {
  cargando.value = true; error.value = ''
  try {
    datos.value = await reviewUseCases.colaModeracion({ estado: estado.value || undefined, pagina, tamano: 10, idioma: locale.value })
    nombres.value = (await catalogUseCases.nombres(datos.value.items.map((r) => r.servicio_id), { idioma: locale.value })).porId
  } catch (e) { if (!sesionVencida(e)) error.value = mensaje(e, 'resenas') } finally { cargando.value = false }
}
onMounted(() => cargar())
watch([estado, locale], () => cargar())

const nombre = (id) => nombres.value[id]?.nombre ?? t('my.service')
const abrir = (r, decision) => Object.assign(accion, { id: r.id, decision, motivo: '', error: '' })
async function confirmar(r) {
  accion.enviando = true; accion.error = ''
  try {
    await reviewUseCases.moderar(r.id, { decision: accion.decision, motivo: accion.motivo }, r.version)
    aviso.value = t(accion.decision === 'OCULTAR' ? 'admin.hidden' : 'admin.published')
    accion.id = ''
    await cargar(datos.value.pagina)
  } catch (e) {
    if (sesionVencida(e)) return
    accion.error = mensaje(e, 'resenas')
    if (e.code === 'VERSION_DISTINTA') await cargar(datos.value.pagina)
  } finally { accion.enviando = false }
}
</script>

<template>
  <section aria-labelledby="h-mod">
    <h2 id="h-mod" class="text-lg font-bold text-navy-darkest">{{ t('admin.moderationTitle') }}</h2>
    <p class="mt-1 max-w-2xl text-sm text-muted">{{ t('admin.moderationLead') }}</p>
    <label class="mt-4 block max-w-xs"><span class="campo-etiqueta">{{ t('admin.status') }}</span>
      <select v-model="estado" class="campo-input"><option value="">{{ t('gestion.all') }}</option><option value="EN_REVISION">{{ t('resenas.states.EN_REVISION') }}</option><option value="PUBLICADA">{{ t('resenas.states.PUBLICADA') }}</option></select>
    </label>
    <p v-if="aviso" class="mt-4 rounded-xl bg-ok-bg px-4 py-2.5 text-sm text-ok" role="status">{{ aviso }}</p>

    <div class="mt-5">
      <EstadoCarga :cargando="cargando" :error="error" :vacio="!datos.items.length" :texto-vacio="t('admin.moderationEmpty')" alto="h-40" @reintentar="cargar(datos.pagina)">
        <ul class="space-y-4">
          <li v-for="r in datos.items" :key="r.id" class="tarjeta">
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
              <Estrellas :valor="r.puntuacion" />
              <span class="text-sm font-semibold text-navy-darkest">{{ nombre(r.servicio_id) }}</span>
              <span class="pildora" :class="r.estado === 'EN_REVISION' ? 'bg-warn-bg text-warn' : 'bg-ok-bg text-ok'">{{ t(`resenas.states.${r.estado}`) }}</span>
              <span class="font-mono text-xs text-muted">{{ fmtMomento(r.creada_en, locale, false) }}</span>
            </div>
            <p v-if="r.comentario" class="mt-2 whitespace-pre-line text-sm leading-relaxed text-ink-control">{{ r.comentario }}</p>
            <p v-else class="mt-2 text-sm italic text-muted">{{ t('resenas.noComment') }}</p>
            <div class="mt-3 rounded-xl bg-cream p-3 text-sm">
              <p class="font-mono text-[10px] uppercase tracking-[.12em] text-danger">{{ t('admin.reports', { n: r.reportes.length }) }}</p>
              <ul class="mt-1.5 space-y-1">
                <li v-for="(x, i) in r.reportes" :key="i" class="text-ink-control"><b>{{ t(`resenas.reasons.${x.motivo}`) }}</b> · {{ t(`perfil.roles.${x.rol_reportante}`) }}<span v-if="x.es_dueno"> ({{ t('admin.owner') }})</span> · <span class="text-xs text-muted">{{ fmtMomento(x.reportado_en, locale) }}</span><span v-if="x.detalle" class="block text-xs text-muted">“{{ x.detalle }}”</span></li>
              </ul>
            </div>
            <div v-if="accion.id !== r.id" class="mt-3 flex flex-wrap gap-3">
              <button type="button" class="btn-primario" :disabled="!enLinea" @click="abrir(r, 'PUBLICAR')">{{ t('admin.keepPublished') }}</button>
              <button type="button" class="btn-peligro" :disabled="!enLinea" @click="abrir(r, 'OCULTAR')">{{ t('admin.hide') }}</button>
            </div>
            <form v-else class="mt-3 space-y-3 rounded-xl border border-sand/40 p-3" @submit.prevent="confirmar(r)">
              <label class="block"><span class="campo-etiqueta">{{ accion.decision === 'OCULTAR' ? t('admin.hideReason') : t('admin.reasonOptional') }}</span><textarea v-model="accion.motivo" rows="2" maxlength="500" class="campo-input" :required="accion.decision === 'OCULTAR'" /></label>
              <p v-if="accion.error" class="campo-error" role="alert">{{ accion.error }}</p>
              <div class="flex gap-3"><button type="submit" :class="accion.decision === 'OCULTAR' ? 'btn-peligro' : 'btn-primario'" :disabled="accion.enviando">{{ accion.enviando ? t('gestion.sending') : t('gestion.confirm') }}</button><button type="button" class="btn-secundario" @click="accion.id = ''">{{ t('gestion.cancel') }}</button></div>
            </form>
          </li>
        </ul>
        <Paginacion :pagina="datos.pagina" :tamano="datos.tamano" :total="datos.total" @cambiar="cargar" />
      </EstadoCarga>
    </div>
  </section>
</template>
