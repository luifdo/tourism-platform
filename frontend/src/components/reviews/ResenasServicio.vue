<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { reviewUseCases } from '../../composition'
import { MOTIVOS_REPORTE } from '../../domain/gestion/resenas'
import { useGestion } from '../../ui/useGestion'
import { useOnline } from '../../ui/useOnline'
import { useSession } from '../../ui/useSession'
import { fmtMomento } from '../../ui/format'
import EstadoCarga from '../shared/EstadoCarga.vue'
import Paginacion from '../shared/Paginacion.vue'
import Estrellas from './Estrellas.vue'
import ResenaForm from './ResenaForm.vue'

/*
 * Reseñas de un servicio (UC9, UC15, UC39): resumen con distribución y aspectos, lista pública (solo PUBLICADAS), escribir
 * la mía (solo si ya viajé y aún no reseñé) y reportar una inapropiada. La lectura es pública; escribir y reportar piden sesión.
 */
const props = defineProps({ servicioId: { type: String, required: true } })
const { t, locale, n } = useI18n()
const { mensaje, sesionVencida } = useGestion()
const { sesion } = useSession()
const enLinea = useOnline()

const resumen = ref(null)
const datos = ref({ items: [], pagina: 1, tamano: 5, total: 0 })
const orden = ref('recientes')
const cargando = ref(true)
const error = ref('')
const puedeEscribir = ref(false)
const escribiendo = ref(false)
const gracias = ref('')
const reporte = reactive({ id: '', motivo: 'OFENSIVO', detalle: '', enviando: false, error: '', hecho: '' })

const rol = computed(() => sesion.usuario?.rol)
const puedeReportar = computed(() => sesion.autenticado && (rol.value === 'Turista' || rol.value === 'Prestador'))

async function cargar(pagina = 1) {
  cargando.value = true; error.value = ''
  try {
    const [r, l] = await Promise.all([reviewUseCases.resumen(props.servicioId), reviewUseCases.resenasDeServicio(props.servicioId, { orden: orden.value, pagina, tamano: 5, idioma: locale.value })])
    resumen.value = r; datos.value = l
  } catch (e) { error.value = mensaje(e, 'resenas') } finally { cargando.value = false }
}
async function elegibilidad() {
  puedeEscribir.value = false
  if (!sesion.autenticado || rol.value !== 'Turista') return
  try { puedeEscribir.value = (await reviewUseCases.pendientes()).some((p) => p.servicio_id === props.servicioId) } catch (e) { sesionVencida(e) && undefined }
}
onMounted(() => { cargar(); elegibilidad() })
watch([orden, locale], () => cargar())
watch(() => props.servicioId, () => { cargar(); elegibilidad() })
watch(() => sesion.autenticado, elegibilidad)

const distribucion = computed(() => [5, 4, 3, 2, 1].map((e) => ({ e, n: resumen.value?.distribucion?.[e] ?? 0, pct: resumen.value?.total ? Math.round(((resumen.value.distribucion?.[e] ?? 0) / resumen.value.total) * 100) : 0 })))
const aspectos = computed(() => Object.entries(resumen.value?.aspectos ?? {}))

async function escrita() {
  escribiendo.value = false; puedeEscribir.value = false; gracias.value = t('resenas.thanks')
  await cargar()
}
function abrirReporte(r) { Object.assign(reporte, { id: r.id, motivo: 'OFENSIVO', detalle: '', error: '', hecho: '' }) }
async function reportar() {
  reporte.enviando = true; reporte.error = ''
  try { await reviewUseCases.reportar(reporte.id, { motivo: reporte.motivo, detalle: reporte.detalle }); reporte.hecho = reporte.id; reporte.id = '' }
  catch (e) { if (!sesionVencida(e)) reporte.error = mensaje(e, 'resenas') } finally { reporte.enviando = false }
}
</script>

<template>
  <section class="mt-10" aria-labelledby="h-resenas">
    <h2 id="h-resenas" class="text-lg font-bold text-navy-darkest">{{ t('resenas.title') }}</h2>

    <div class="mt-3">
      <EstadoCarga :cargando="cargando" :error="error" alto="h-32" @reintentar="cargar()">
        <div v-if="resumen" class="grid gap-5 sm:grid-cols-[180px_1fr]">
          <div class="tarjeta !p-4 text-center">
            <template v-if="resumen.total">
              <p class="text-4xl font-bold tabular-nums text-navy-darkest">{{ n(resumen.promedio, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) }}</p>
              <p class="mt-1 flex justify-center"><Estrellas :valor="resumen.promedio" :tamano="18" /></p>
              <p class="mt-1 text-xs text-muted">{{ t('resenas.count', { n: resumen.total }, resumen.total) }}</p>
            </template>
            <p v-else class="text-sm text-muted">{{ t('resenas.none') }}</p>
          </div>
          <div v-if="resumen.total" class="space-y-1.5">
            <div v-for="d in distribucion" :key="d.e" class="flex items-center gap-3 text-xs">
              <span class="w-14 shrink-0 text-right tabular-nums text-muted">{{ d.e }} ★</span>
              <span class="h-2 flex-1 overflow-hidden rounded-full bg-cream"><span class="block h-full rounded-full bg-warn" :style="{ width: d.pct + '%' }" /></span>
              <span class="w-8 shrink-0 tabular-nums text-muted">{{ d.n }}</span>
            </div>
            <ul v-if="aspectos.length" class="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-control">
              <li v-for="[a, v] in aspectos" :key="a">{{ t(`resenas.aspect.${a}`) }}: <b class="tabular-nums">{{ v.promedio.toFixed(1) }}</b></li>
            </ul>
          </div>
        </div>

        <p v-if="gracias" class="mt-4 rounded-xl bg-ok-bg px-4 py-2.5 text-sm text-ok" role="status">{{ gracias }}</p>
        <div v-if="puedeEscribir && !escribiendo" class="mt-4"><button type="button" class="btn-primario" @click="escribiendo = true; gracias = ''">{{ t('resenas.write') }}</button></div>
        <ResenaForm v-if="escribiendo" class="mt-4" :servicio-id="servicioId" @guardada="escrita" @cancelar="escribiendo = false" />
        <p v-else-if="!sesion.autenticado" class="mt-4 text-sm text-muted">{{ t('resenas.loginToWrite') }} <RouterLink :to="{ name: 'login', query: { redirect: $route.fullPath } }" class="font-medium text-navy underline">{{ t('auth.menu.login') }}</RouterLink></p>

        <template v-if="resumen.total">
          <div class="mt-6 flex items-center justify-between gap-3">
            <p class="font-mono text-xs text-muted">{{ t('resenas.shown', { n: datos.total }) }}</p>
            <label class="flex items-center gap-2 text-sm"><span class="campo-etiqueta">{{ t('resenas.order') }}</span>
              <select v-model="orden" class="campo-input !mt-0 !w-auto !py-1.5"><option v-for="o in ['recientes', 'mejores', 'peores']" :key="o" :value="o">{{ t(`resenas.orders.${o}`) }}</option></select>
            </label>
          </div>
          <ul class="mt-3 space-y-4">
            <li v-for="r in datos.items" :key="r.id" class="tarjeta">
              <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
                <Estrellas :valor="r.puntuacion" />
                <span class="text-sm font-semibold text-navy-darkest">{{ r.autor }}</span>
                <span class="font-mono text-xs text-muted">{{ t('resenas.visitedIn', { mes: r.mes_visita }) }}</span>
              </div>
              <!-- El comentario lo escribe un turista: siempre texto plano -->
              <p v-if="r.comentario" class="mt-2 whitespace-pre-line text-sm leading-relaxed text-ink-control">{{ r.comentario }}</p>
              <ul v-if="Object.keys(r.aspectos ?? {}).length" class="mt-2 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted">
                <li v-for="(v, a) in r.aspectos" :key="a">{{ r.aspectos_etiquetas?.[a] ?? t(`resenas.aspect.${a}`) }}: {{ v }}/5</li>
              </ul>
              <div v-if="r.respuesta" class="mt-3 rounded-xl bg-cream p-3 text-sm">
                <p class="font-mono text-[10px] uppercase tracking-[.12em] text-teal">{{ t('resenas.providerReply') }} · {{ fmtMomento(r.respuesta.respondida_en, locale, false) }}</p>
                <p class="mt-1 whitespace-pre-line text-ink-control">{{ r.respuesta.texto }}</p>
              </div>
              <div v-if="puedeReportar" class="mt-2 text-right text-xs">
                <span v-if="reporte.hecho === r.id" class="text-ok" role="status">{{ t('resenas.reported') }}</span>
                <button v-else-if="reporte.id !== r.id" type="button" class="text-muted underline hover:text-danger" :disabled="!enLinea" @click="abrirReporte(r)">{{ t('resenas.report') }}</button>
              </div>
              <form v-if="reporte.id === r.id" class="mt-3 space-y-3 rounded-xl border border-danger/20 bg-danger-bg/40 p-3" @submit.prevent="reportar">
                <label class="block"><span class="campo-etiqueta">{{ t('resenas.reportReason') }}</span>
                  <select v-model="reporte.motivo" class="campo-input"><option v-for="m in MOTIVOS_REPORTE" :key="m" :value="m">{{ t(`resenas.reasons.${m}`) }}</option></select>
                </label>
                <label class="block"><span class="campo-etiqueta">{{ t('resenas.reportDetail') }}</span><textarea v-model="reporte.detalle" rows="2" maxlength="500" class="campo-input" /></label>
                <p v-if="reporte.error" class="campo-error" role="alert">{{ reporte.error }}</p>
                <div class="flex gap-3"><button type="submit" class="btn-peligro" :disabled="reporte.enviando">{{ reporte.enviando ? t('gestion.sending') : t('resenas.sendReport') }}</button><button type="button" class="btn-secundario" @click="reporte.id = ''">{{ t('gestion.cancel') }}</button></div>
              </form>
            </li>
          </ul>
          <Paginacion :pagina="datos.pagina" :tamano="datos.tamano" :total="datos.total" @cambiar="cargar" />
        </template>
      </EstadoCarga>
    </div>
  </section>
</template>
