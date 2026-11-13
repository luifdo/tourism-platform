<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { isMockBackend } from '../composition'
import { CATEGORIAS, nivelOcupacion } from '../domain/catalog/rules'
import { useCatalog } from '../lib/useCatalog'
import { degradado } from '../ui/format'

const { t, te, tm, rt, n, locale, d } = useI18n()
const { estado, cargar, masResultados } = useCatalog()
const route = useRoute()

// La portada y las rutas llegan con ?q=texto: el texto entra al buscador y se busca
const deLaUrl = () => (typeof route.query.q === 'string' ? route.query.q.trim().slice(0, 200) : '')
const categoria = ref('all') // 'all' o un código de categoría del contrato
const texto = ref(deLaUrl()) // lo que se está escribiendo
const buscado = ref(deLaUrl()) // lo que se buscó al enviar el formulario
const cats = ['all', ...CATEGORIAS]

const filtros = () => ({ texto: buscado.value, categorias: categoria.value === 'all' ? [] : [categoria.value] })
const recargar = () => cargar(filtros(), locale.value)
onMounted(recargar)
watch([categoria, buscado, locale], recargar)
// Ya en la portada, una búsqueda nueva desde arriba cambia ?q= sin volver a montar la sección
watch(() => route.query.q, () => { texto.value = deLaUrl(); buscado.value = texto.value })
const buscar = () => { buscado.value = texto.value.trim() }

const stats = computed(() => tm('explorer.stats').map((s) => ({ n: rt(s.n), l: rt(s.l) })))
const cop = (v) => n(v, { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })
const bar = { ok: 'bg-ok', mid: 'bg-warn', high: 'bg-danger' }
const txt = { ok: 'text-ok', mid: 'text-warn', high: 'text-danger' }
const etiquetaFiltro = (c) => (c === 'all' ? t('explorer.filters.all') : te(`explorer.filters.${c}`) ? t(`explorer.filters.${c}`) : c)
const errorTexto = computed(() => t(`explorer.errors.${te(`explorer.errors.${estado.error}`) ? estado.error : 'generic'}`))
const hayMas = computed(() => estado.items.length < estado.total)
const fecha = computed(() => (estado.actualizadoEn ? d(estado.actualizadoEn, { dateStyle: 'medium', timeStyle: 'short' }) : ''))
</script>

<template>
  <section id="catalogo" class="bg-white px-[clamp(20px,5vw,64px)] py-[clamp(56px,9vw,120px)]">
    <div class="mx-auto max-w-[1200px]">
      <p class="kicker flex items-center gap-2"><span class="size-1.5 rounded-full bg-teal" />{{ t('explorer.kicker') }}</p>
      <div class="mt-3 flex flex-wrap items-end justify-between gap-6">
        <div class="max-w-2xl">
          <h2 class="text-[clamp(34px,4.6vw,60px)] font-bold leading-[1.1] tracking-[-.025em] text-navy-deep text-balance">{{ t('explorer.title') }}</h2>
          <p class="mt-4 text-lg leading-relaxed text-muted">{{ t('explorer.lead') }}</p>
        </div>
        <div class="flex flex-wrap gap-2" role="group" :aria-label="t('explorer.categories')">
          <button
            v-for="c in cats" :key="c" type="button" :aria-pressed="categoria === c"
            class="rounded-full border px-5 py-2.5 text-sm font-medium transition"
            :class="categoria === c ? 'border-navy bg-navy text-white shadow-cta' : 'border-sand/40 bg-cream text-ink-control hover:border-teal'"
            @click="categoria = c"
          >{{ etiquetaFiltro(c) }}</button>
        </div>
      </div>

      <!-- Buscador por texto (RF-02): nombre y descripción, en el idioma de la interfaz -->
      <form class="glass mt-9 flex flex-wrap gap-3 rounded-panel p-3.5 shadow-elevated" role="search" @submit.prevent="buscar">
        <label class="min-w-[220px] flex-1 rounded-xl border border-border-input bg-white px-4 py-2 transition focus-within:border-teal focus-within:shadow-[0_0_0_3px_rgba(93,154,146,.15)]">
          <span class="block font-mono text-[10px] font-medium uppercase tracking-[.12em] text-teal-hover">{{ t('explorer.search.what') }}</span>
          <input v-model="texto" type="search" maxlength="200" :placeholder="t('explorer.search.whatPh')" class="mt-0.5 w-full bg-transparent text-[15px] text-ink-control outline-none placeholder:text-[#64777E]" />
        </label>
        <button type="submit" class="min-h-14 rounded-full bg-navy px-8 font-medium text-white shadow-cta transition hover:-translate-y-0.5 hover:bg-blue">{{ t('explorer.search.go') }}</button>
      </form>

      <p v-if="estado.desdeCache" class="mt-4 rounded-xl bg-warn-bg px-4 py-2.5 text-sm text-warn" role="status">{{ t('explorer.cached', { when: fecha }) }}</p>

      <div v-if="estado.cargando" class="mt-10 grid grid-cols-[repeat(auto-fit,minmax(min(100%,300px),1fr))] gap-6" role="status" :aria-label="t('explorer.loading')">
        <div v-for="k in 3" :key="k" class="h-[420px] animate-pulse rounded-card bg-cream" />
      </div>

      <div v-else-if="estado.error && !estado.items.length" class="mt-10 rounded-panel border border-danger/30 bg-danger-bg p-6 text-danger" role="alert">
        <p>{{ errorTexto }}</p>
        <button type="button" class="mt-3 font-semibold underline" @click="recargar">{{ t('explorer.retry') }}</button>
      </div>

      <div v-else class="mt-10 grid grid-cols-[repeat(auto-fit,minmax(min(100%,300px),1fr))] gap-6">
        <article
          v-for="e in estado.items" :key="e.id"
          class="group flex flex-col overflow-hidden rounded-card border border-sand/30 bg-cream shadow-card transition hover:-translate-y-0.5 hover:shadow-elevated"
        >
          <div class="relative h-44 overflow-hidden" :style="{ background: degradado(e.categoria) }">
            <!-- Sin foto queda el degradado de la categoría; las etiquetas van encima de la imagen. -->
            <img v-if="e.imagen" :src="e.imagen" alt="" class="absolute inset-0 size-full object-cover transition duration-500 group-hover:scale-105" loading="lazy" decoding="async" />
            <div class="absolute left-3 top-3 flex gap-1.5 font-mono text-xs">
              <span class="rounded-full bg-white/90 px-2.5 py-1 text-ink-control">{{ e.categoriaEtiqueta }}</span>
              <span v-if="e.calificacion" class="rounded-full bg-navy-darkest/85 px-2.5 py-1 text-white" :title="t('explorer.reviews', { n: e.totalResenas })">★ {{ e.calificacion.toFixed(1) }}</span>
            </div>
          </div>
          <div class="flex flex-1 flex-col p-5">
            <p class="flex items-center gap-1.5 font-mono text-xs text-muted">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" /><path d="M9 12l2 2 4-4" /></svg>
              {{ t('explorer.rnt') }}<template v-if="e.zona"> · {{ e.zona.nombre }}</template>
            </p>
            <h3 class="mt-2 text-xl font-bold leading-snug tracking-tight text-navy-darkest">{{ e.nombre }}</h3>
            <p class="mt-2 text-[15px] leading-relaxed text-muted">{{ e.tipoEtiqueta }}</p>

            <!-- El aforo en vivo solo lo conoce el simulador: el catálogo real no lo publica -->
            <div v-if="e.ocupacion != null" class="mt-4 rounded-xl border border-sand/30 bg-white px-3.5 py-3">
              <div class="flex justify-between font-mono text-xs text-muted">
                <span>{{ t('explorer.aforo') }}</span>
                <span class="font-semibold" :class="txt[nivelOcupacion(e.ocupacion)]">{{ e.ocupacion }}% ({{ t(`explorer.status.${nivelOcupacion(e.ocupacion)}`) }})</span>
              </div>
              <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-cream" role="progressbar" :aria-valuenow="e.ocupacion" aria-valuemin="0" aria-valuemax="100">
                <div class="h-full rounded-full" :class="bar[nivelOcupacion(e.ocupacion)]" :style="{ width: e.ocupacion + '%' }" />
              </div>
            </div>

            <div class="mt-auto flex items-center justify-between border-t border-sand/30 pt-4 mt-5">
              <div>
                <p class="font-mono text-[10px] uppercase tracking-[.12em] text-muted">{{ t('explorer.fee') }}</p>
                <p class="text-lg font-semibold tabular-nums text-ink">{{ cop(e.tarifaBase) }}</p>
                <p v-if="e.unidadEtiqueta" class="text-xs text-muted">{{ e.unidadEtiqueta }}</p>
              </div>
              <RouterLink :to="{ name: 'service', params: { id: e.id } }" class="rounded-full bg-navy px-5 py-2.5 text-sm font-medium text-white shadow-cta transition hover:bg-blue">{{ t('explorer.details') }}</RouterLink>
            </div>
          </div>
        </article>
        <p v-if="!estado.items.length" class="text-muted">{{ buscado ? t('explorer.emptySearch') : t('explorer.empty') }}</p>
      </div>

      <div v-if="hayMas && !estado.cargando" class="mt-8 text-center">
        <button type="button" class="rounded-full border border-navy px-8 py-3 font-medium text-navy transition hover:bg-cream disabled:opacity-50" :disabled="estado.cargandoMas" @click="masResultados(filtros(), locale)">{{ estado.cargandoMas ? t('explorer.loading') : t('explorer.more') }}</button>
        <p v-if="estado.error" class="mt-3 text-sm text-danger" role="alert">{{ errorTexto }}</p>
      </div>

      <p v-if="isMockBackend" class="mt-4 font-mono text-[11px] text-muted/80">{{ t('explorer.mock') }}</p>

      <div class="mt-14 grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-8">
        <div v-for="s in stats" :key="s.n + s.l">
          <p class="text-[clamp(40px,5vw,64px)] font-semibold leading-none tracking-[-.04em] text-navy-deep tabular-nums">{{ s.n }}</p>
          <div class="mt-2 h-px w-10 bg-sand" />
          <p class="mt-2.5 text-sm leading-snug text-ink/75">{{ s.l }}</p>
        </div>
      </div>
    </div>
  </section>
</template>
