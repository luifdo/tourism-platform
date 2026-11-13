<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { reviewUseCases } from '../../composition'
import { MOTIVOS_REPORTE, MAX_RESPUESTA } from '../../domain/gestion/resenas'
import { useGestion } from '../../ui/useGestion'
import { useOnline } from '../../ui/useOnline'
import { fmtMomento } from '../../ui/format'
import EstadoCarga from '../shared/EstadoCarga.vue'
import Paginacion from '../shared/Paginacion.vue'
import Estrellas from '../reviews/Estrellas.vue'

/* UC21 · Reseñas de mis servicios: responder públicamente (una respuesta por reseña; se puede reemplazar) y reportar las inapropiadas (UC39). */
const props = defineProps({ servicios: { type: Array, default: () => [] } })
const { t, locale } = useI18n()
const { mensaje, camposDe, sesionVencida } = useGestion()
const enLinea = useOnline()

const filtros = reactive({ servicio_id: '', sin_respuesta: false })
const datos = ref({ items: [], pagina: 1, tamano: 10, total: 0 })
const cargando = ref(true)
const error = ref('')
const abierta = reactive({ id: '', modo: '', texto: '', motivo: 'OFENSIVO', detalle: '', enviando: false, error: '', ok: '' })

async function cargar(pagina = 1) {
  cargando.value = true; error.value = ''
  try { datos.value = await reviewUseCases.resenasPrestador({ pagina, tamano: 10, idioma: locale.value, servicio_id: filtros.servicio_id || undefined, sin_respuesta: filtros.sin_respuesta || undefined }) }
  catch (e) { if (!sesionVencida(e)) error.value = mensaje(e, 'resenas') } finally { cargando.value = false }
}
onMounted(() => cargar())
watch([() => filtros.servicio_id, () => filtros.sin_respuesta, locale], () => cargar())

const nombreServicio = (id) => props.servicios.find((s) => s.id === id)?.nombre ?? ''
function abrir(r, modo) { Object.assign(abierta, { id: r.id, modo, texto: modo === 'responder' ? (r.respuesta?.texto ?? '') : '', motivo: 'OFENSIVO', detalle: '', error: '', ok: '' }) }
const cerrar = () => { abierta.id = '' }

async function enviar(r) {
  abierta.enviando = true; abierta.error = ''
  try {
    if (abierta.modo === 'responder') await reviewUseCases.responder(r.id, abierta.texto, r.version)
    else await reviewUseCases.reportar(r.id, { motivo: abierta.motivo, detalle: abierta.detalle })
    abierta.ok = r.id; abierta.id = ''
    await cargar(datos.value.pagina)
  } catch (e) {
    if (sesionVencida(e)) return
    abierta.error = mensaje(e, 'resenas') || camposDe(e).texto
    if (e.code === 'VERSION_DISTINTA') await cargar(datos.value.pagina)
  } finally { abierta.enviando = false }
}
</script>

<template>
  <section aria-labelledby="h-resp">
    <h2 id="h-resp" class="text-lg font-bold text-navy-darkest">{{ t('resenas.providerTitle') }}</h2>
    <p class="mt-1 max-w-2xl text-sm text-muted">{{ t('resenas.providerLead') }}</p>

    <div class="mt-4 flex flex-wrap items-end gap-4">
      <label class="min-w-[220px]"><span class="campo-etiqueta">{{ t('resenas.service') }}</span>
        <select v-model="filtros.servicio_id" class="campo-input"><option value="">{{ t('resenas.allServices') }}</option><option v-for="s in servicios" :key="s.id" :value="s.id">{{ s.nombre }}</option></select>
      </label>
      <label class="flex items-center gap-2 pb-2.5 text-sm text-ink-control"><input v-model="filtros.sin_respuesta" type="checkbox" class="size-4 accent-navy" />{{ t('resenas.onlyUnanswered') }}</label>
    </div>

    <div class="mt-5">
      <EstadoCarga :cargando="cargando" :error="error" :vacio="!datos.items.length" :texto-vacio="t('resenas.providerEmpty')" alto="h-40" @reintentar="cargar(datos.pagina)">
        <ul class="space-y-4">
          <li v-for="r in datos.items" :key="r.id" class="tarjeta">
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
              <Estrellas :valor="r.puntuacion" />
              <span class="text-sm font-semibold text-navy-darkest">{{ nombreServicio(r.servicio_id) }}</span>
              <span class="font-mono text-xs text-muted">{{ r.autor }} · {{ fmtMomento(r.creada_en, locale, false) }}</span>
              <span v-if="r.estado === 'EN_REVISION'" class="pildora bg-warn-bg text-warn">{{ t('resenas.inReview') }}</span>
            </div>
            <p v-if="r.comentario" class="mt-2 whitespace-pre-line text-sm leading-relaxed text-ink-control">{{ r.comentario }}</p>
            <p v-else class="mt-2 text-sm italic text-muted">{{ t('resenas.noComment') }}</p>

            <div v-if="r.respuesta" class="mt-3 rounded-xl bg-cream p-3 text-sm">
              <p class="font-mono text-[10px] uppercase tracking-[.12em] text-teal">{{ t('resenas.yourReply') }} · {{ fmtMomento(r.respuesta.respondida_en, locale, false) }}</p>
              <p class="mt-1 whitespace-pre-line text-ink-control">{{ r.respuesta.texto }}</p>
            </div>
            <p v-if="abierta.ok === r.id" class="mt-2 text-sm text-ok" role="status">{{ t('resenas.done') }}</p>

            <div v-if="abierta.id !== r.id" class="mt-3 flex flex-wrap gap-4 text-sm">
              <button type="button" class="font-medium text-navy underline hover:text-teal" :disabled="!enLinea" @click="abrir(r, 'responder')">{{ r.respuesta ? t('resenas.editReply') : t('resenas.reply') }}</button>
              <button type="button" class="font-medium text-danger underline" :disabled="!enLinea" @click="abrir(r, 'reportar')">{{ t('resenas.report') }}</button>
            </div>

            <form v-else class="mt-3 space-y-3" @submit.prevent="enviar(r)">
              <template v-if="abierta.modo === 'responder'">
                <label class="block"><span class="campo-etiqueta">{{ t('resenas.replyLabel') }}</span>
                  <textarea v-model="abierta.texto" rows="3" :maxlength="MAX_RESPUESTA" class="campo-input" required />
                  <span class="mt-1 block text-right font-mono text-[11px] text-muted">{{ abierta.texto.length }}/{{ MAX_RESPUESTA }}</span>
                </label>
                <p class="text-xs text-muted">{{ t('resenas.replyPublic') }}</p>
              </template>
              <template v-else>
                <label class="block"><span class="campo-etiqueta">{{ t('resenas.reportReason') }}</span>
                  <select v-model="abierta.motivo" class="campo-input"><option v-for="m in MOTIVOS_REPORTE" :key="m" :value="m">{{ t(`resenas.reasons.${m}`) }}</option></select>
                </label>
                <label class="block"><span class="campo-etiqueta">{{ t('resenas.reportDetail') }}</span><textarea v-model="abierta.detalle" rows="2" maxlength="500" class="campo-input" /></label>
              </template>
              <p v-if="abierta.error" class="campo-error" role="alert">{{ abierta.error }}</p>
              <div class="flex gap-3">
                <button type="submit" :class="abierta.modo === 'responder' ? 'btn-primario' : 'btn-peligro'" :disabled="abierta.enviando">{{ abierta.enviando ? t('gestion.sending') : abierta.modo === 'responder' ? t('resenas.sendReply') : t('resenas.sendReport') }}</button>
                <button type="button" class="btn-secundario" @click="cerrar">{{ t('gestion.cancel') }}</button>
              </div>
            </form>
          </li>
        </ul>
        <Paginacion :pagina="datos.pagina" :tamano="datos.tamano" :total="datos.total" @cambiar="cargar" />
      </EstadoCarga>
    </div>
  </section>
</template>
