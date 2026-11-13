<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { catalogUseCases } from '../composition'
import { CODIGOS } from '../domain/catalog/errors'
import { nivelOcupacion } from '../domain/catalog/rules'
import { seccionesDeAtributos } from '../domain/catalog/atributos'
import { degradado, urlMapa } from '../ui/format'
import BookingWidget from '../components/BookingWidget.vue'

const props = defineProps({ id: { type: String, required: true } })
const { t, n, locale } = useI18n()

// UC9 · GET /api/catalog/servicios/{id}
const servicio = ref(null)
const estado = ref('cargando') // 'cargando' | 'listo' | 'noEncontrado' | 'error'
async function cargar() {
  const id = props.id
  estado.value = 'cargando'
  try {
    const s = await catalogUseCases.ficha(id, { idioma: locale.value })
    if (id !== props.id) return // se cambió de ficha mientras llegaba la respuesta
    servicio.value = s; estado.value = 'listo'
  } catch (e) {
    if (id !== props.id) return
    servicio.value = null; estado.value = e.code === CODIGOS.NO_ENCONTRADO ? 'noEncontrado' : 'error'
  }
}
watch([() => props.id, locale], cargar, { immediate: true })

const cop = (v) => n(v, { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })
const bar = { ok: 'bg-ok', mid: 'bg-warn', high: 'bg-danger' }
const nivelAlerta = { INFORMATIVA: 'bg-sand/15 text-ink-control', PREVENTIVA: 'bg-warn-bg text-warn', CRITICA: 'bg-danger-bg text-danger' }
const pagoClase = (a) => (a.importante ? 'border-warn/40 bg-warn-bg text-warn' : 'border-sand/40 bg-sand/10 text-ink-control')
const secciones = computed(() => seccionesDeAtributos(servicio.value?.atributos, servicio.value?.etiquetasPorCodigo))
const portada = computed(() => servicio.value?.imagenes?.[0] ?? null)
const duracion = (min) => (min >= 60 ? `${Math.floor(min / 60)} h${min % 60 ? ` ${min % 60} min` : ''}` : `${min} min`)
const enlaceMapa = computed(() => (servicio.value ? urlMapa(servicio.value.ubicacion) : '#'))
// "Cómo llegar": cuenta la intención de visita (indicador aparte) y abre el punto en OpenStreetMap
const comoLlegar = () => catalogUseCases.comoLlegar(props.id)
</script>

<template>
  <div class="bg-cream px-[clamp(20px,5vw,64px)] py-8 sm:py-12">
    <div class="mx-auto max-w-[1200px]">
      <RouterLink :to="{ name: 'home', hash: '#catalogo' }" class="inline-flex items-center gap-1.5 font-mono text-sm text-navy hover:text-teal">← {{ t('service.back') }}</RouterLink>

      <div v-if="estado === 'cargando'" class="mt-8 grid gap-8 lg:grid-cols-[1.4fr_1fr]" role="status" :aria-label="t('service.loading')">
        <div class="h-[360px] animate-pulse rounded-panel bg-white" />
        <div class="h-[360px] animate-pulse rounded-panel bg-white" />
      </div>

      <p v-else-if="estado === 'noEncontrado'" class="mt-10 text-lg text-muted">{{ t('service.notFound') }}</p>

      <div v-else-if="estado === 'error'" class="mt-10 rounded-panel border border-danger/30 bg-danger-bg p-6 text-danger" role="alert">
        <p>{{ t('service.error') }}</p>
        <button type="button" class="mt-3 font-semibold underline" @click="cargar">{{ t('service.retry') }}</button>
      </div>

      <div v-else class="mt-6 grid items-start gap-8 lg:grid-cols-[1.4fr_1fr]">
        <article>
          <div class="relative h-[clamp(200px,34vw,360px)] overflow-hidden rounded-panel shadow-elevated" :style="{ background: degradado(servicio.categoria) }">
            <img v-if="portada" :src="portada" :alt="servicio.nombre" class="size-full object-cover" loading="lazy" />
            <div class="absolute left-4 top-4 flex gap-2 font-mono text-xs">
              <span class="rounded-full bg-white/90 px-3 py-1 text-ink-control">{{ servicio.categoriaEtiqueta }}</span>
              <span v-if="servicio.calificacion" class="rounded-full bg-navy-darkest/85 px-3 py-1 text-white" :title="t('explorer.reviews', { n: servicio.totalResenas })">★ {{ servicio.calificacion.toFixed(1) }}</span>
            </div>
          </div>

          <p class="kicker mt-8 flex items-center gap-2"><span class="size-1.5 rounded-full bg-teal" />{{ servicio.zona?.nombre ?? servicio.tipoEtiqueta }}</p>
          <h1 class="mt-2 text-[clamp(30px,4vw,48px)] font-bold leading-[1.1] tracking-[-.02em] text-navy-darkest text-balance">{{ servicio.nombre }}</h1>
          <p class="mt-3 flex items-center gap-1.5 font-mono text-xs text-muted">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" /><path d="M9 12l2 2 4-4" /></svg>
            {{ t('explorer.rnt') }} · {{ servicio.tipoEtiqueta }}
          </p>

          <!-- Alertas vigentes del servicio y de su zona (UC26) -->
          <ul v-if="servicio.alertas.length" class="mt-6 flex flex-col gap-2" :aria-label="t('service.alerts')">
            <li v-for="a in servicio.alertas" :key="a.id" class="rounded-xl px-4 py-3 text-sm" :class="nivelAlerta[a.nivel] ?? nivelAlerta.INFORMATIVA" role="note">
              <span class="font-mono text-[10px] uppercase tracking-[.12em]">{{ a.nivelEtiqueta }}</span>
              <!-- Texto plano: lo escribe el prestador o el admin, nunca se interpreta como HTML -->
              <p class="mt-0.5">{{ a.mensaje }}</p>
            </li>
          </ul>

          <h2 class="mt-8 text-lg font-bold text-navy-darkest">{{ t('service.about') }}</h2>
          <p class="mt-2 whitespace-pre-line leading-relaxed text-ink-control">{{ servicio.descripcion }}</p>

          <ul v-if="servicio.etiquetas.length" class="mt-4 flex flex-wrap gap-2">
            <li v-for="e in servicio.etiquetas" :key="e" class="rounded-full border border-sand/40 bg-white px-3 py-1 text-xs text-ink-control">{{ e }}</li>
          </ul>

          <dl class="mt-8 grid gap-4 sm:grid-cols-3">
            <div class="rounded-card border border-sand/30 bg-white p-4 shadow-card">
              <dt class="font-mono text-[10px] uppercase tracking-[.12em] text-muted">{{ t('service.fee') }}</dt>
              <dd class="mt-1 text-xl font-semibold tabular-nums text-ink">{{ cop(servicio.tarifaBase) }}</dd>
              <dd class="text-xs text-muted">{{ servicio.unidadEtiqueta || t('service.perPerson') }}</dd>
            </div>
            <div v-if="servicio.capacidadDiaria" class="rounded-card border border-sand/30 bg-white p-4 shadow-card">
              <dt class="font-mono text-[10px] uppercase tracking-[.12em] text-muted">{{ t('service.capacity') }}</dt>
              <dd class="mt-1 text-xl font-semibold tabular-nums text-ink">{{ servicio.capacidadDiaria }} {{ t('service.people') }}</dd>
            </div>
            <!-- Solo el simulador conoce el aforo en vivo: el catálogo real no lo publica -->
            <div v-if="servicio.ocupacion != null" class="rounded-card border border-sand/30 bg-white p-4 shadow-card">
              <dt class="font-mono text-[10px] uppercase tracking-[.12em] text-muted">{{ t('explorer.aforo') }}</dt>
              <dd class="mt-1 text-xl font-semibold tabular-nums text-ink">{{ servicio.ocupacion }}%</dd>
              <dd class="mt-2 h-1.5 overflow-hidden rounded-full bg-cream"><div class="h-full rounded-full" :class="bar[nivelOcupacion(servicio.ocupacion)]" :style="{ width: servicio.ocupacion + '%' }" /></dd>
            </div>
          </dl>

          <!-- Qué dinero llevar: el pago es directo al prestador (SRS §1.2.1) -->
          <div v-if="servicio.avisoPagos" class="mt-6 rounded-card border p-4 text-sm leading-snug" :class="pagoClase(servicio.avisoPagos)" role="note">
            <p class="font-mono text-[10px] uppercase tracking-[.12em]">{{ t('service.payments') }}</p>
            <p class="mt-1">{{ servicio.avisoPagos.mensaje }}</p>
          </div>

          <!-- Atributos del servicio (qué incluye, horario, punto de encuentro, qué llevar...): el catálogo los manda por bloques -->
          <section v-if="secciones.length" class="mt-8" :aria-label="t('service.details')">
            <h2 class="text-lg font-bold text-navy-darkest">{{ t('service.details') }}</h2>
            <div class="mt-3 grid gap-4 sm:grid-cols-2">
              <div v-for="sec in secciones" :key="sec.id" class="rounded-card border border-sand/30 bg-white p-5 shadow-card" :class="{ 'sm:col-span-2': sec.filas.length > 6 }">
                <h3 class="font-mono text-[11px] uppercase tracking-[.14em] text-teal">{{ t(`attrs.sections.${sec.id}`) }}</h3>
                <dl class="mt-3 space-y-2.5 text-sm">
                  <div v-for="f in sec.filas" :key="f.campo">
                    <dt class="font-mono text-[10px] uppercase tracking-[.1em] text-muted">{{ t(`attrs.fields.${f.campo}`) }}</dt>
                    <dd class="mt-0.5 text-ink-control">
                      <!-- Todo es texto plano: lo escribe el prestador y nunca se interpreta como HTML -->
                      <template v-if="f.clase === 'si-no'">{{ f.valor ? t('attrs.yes') : t('attrs.no') }}</template>
                      <template v-else-if="f.clase === 'minutos'">{{ duracion(f.valor) }}</template>
                      <template v-else-if="f.clase === 'dinero'">{{ cop(f.valor) }}</template>
                      <template v-else-if="f.clase === 'habitaciones'">
                        <span v-for="(h, i) in f.valor" :key="i" class="block">{{ h.cantidad }} × {{ h.tipo }} · {{ t('attrs.upTo', { n: h.capacidad }) }}</span>
                      </template>
                      <template v-else-if="f.clase === 'tarifas'">
                        <span v-for="(tf, i) in f.valor" :key="i" class="block">{{ tf.visitante }}: {{ cop(tf.valor) }}</span>
                      </template>
                      <template v-else-if="Array.isArray(f.valor)">{{ f.valor.join(', ') }}</template>
                      <template v-else>{{ f.valor }}</template>
                    </dd>
                  </div>
                </dl>
              </div>
            </div>
          </section>

          <div class="mt-8 grid gap-4 sm:grid-cols-2">
            <div class="rounded-card border border-sand/30 bg-white p-5 shadow-card">
              <h3 class="font-mono text-[11px] uppercase tracking-[.14em] text-teal">{{ t('service.provider') }}</h3>
              <p class="mt-2 font-semibold text-navy-darkest">{{ servicio.prestador.razonSocial }}</p>
              <p v-if="servicio.prestador.telefono" class="text-sm text-muted">{{ t('service.phone') }}: {{ servicio.prestador.telefono }}</p>
            </div>
            <div class="rounded-card border border-sand/40 bg-sand/10 p-5">
              <h3 class="font-mono text-[11px] uppercase tracking-[.14em] text-teal">{{ t('service.policy') }}</h3>
              <p v-if="servicio.prestador.politicaCancelacion" class="mt-2 text-sm leading-snug text-ink-control">{{ servicio.prestador.politicaCancelacion }}</p>
              <p class="mt-2 text-xs leading-snug text-muted">{{ servicio.reglaCancelacion || t('service.rule') }}</p>
            </div>
          </div>

          <a :href="enlaceMapa" target="_blank" rel="noopener noreferrer" class="mt-6 inline-flex items-center gap-2 rounded-full border border-navy px-6 py-3 text-sm font-medium text-navy transition hover:bg-white" @click="comoLlegar">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s7-6.2 7-11a7 7 0 10-14 0c0 4.8 7 11 7 11z" /><circle cx="12" cy="10" r="2.5" /></svg>
            {{ t('service.directions') }}
          </a>
        </article>

        <aside class="lg:sticky lg:top-[calc(var(--nav-h)+16px)]">
          <BookingWidget :service="servicio" />
        </aside>
      </div>
    </div>
  </div>
</template>
