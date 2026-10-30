<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { level } from '../data/mock'
import { useCatalog } from '../lib/useCatalog'

const { t, tm, rt, n } = useI18n()
const { items, source, load } = useCatalog()
onMounted(load)
const filter = ref('all')
const cats = ['all', 'Playa', 'Naturaleza', 'Cultura']

const list = computed(() => items.value.filter((e) => filter.value === 'all' || e.cat === filter.value))
const stats = computed(() => tm('explorer.stats').map((s) => ({ n: rt(s.n), l: rt(s.l) })))
const cop = (v) => n(v, { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })
const bar = { ok: 'bg-ok', mid: 'bg-warn', high: 'bg-danger' }
const txt = { ok: 'text-ok', mid: 'text-warn', high: 'text-danger' }
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
        <div class="flex flex-wrap gap-2" role="group" aria-label="Categorías">
          <button
            v-for="c in cats" :key="c" type="button" :aria-pressed="filter === c"
            class="rounded-full border px-5 py-2.5 text-sm font-medium transition"
            :class="filter === c ? 'border-navy bg-navy text-white shadow-cta' : 'border-sand/40 bg-cream text-ink-control hover:border-teal'"
            @click="filter = c"
          >{{ t(`explorer.filters.${c}`) }}</button>
        </div>
      </div>

      <!-- Buscador multicriterio (RF-02) -->
      <form class="glass mt-9 grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-3 rounded-panel p-3.5 shadow-elevated" @submit.prevent>
        <label class="rounded-xl border border-border-input bg-white px-4 py-2 transition focus-within:border-teal focus-within:shadow-[0_0_0_3px_rgba(93,154,146,.15)]">
          <span class="block font-mono text-[10px] font-medium uppercase tracking-[.12em] text-teal-hover">{{ t('explorer.search.what') }}</span>
          <input type="text" :placeholder="t('explorer.search.whatPh')" class="mt-0.5 w-full bg-transparent text-[15px] text-ink-control outline-none placeholder:text-[#64777E]" />
        </label>
        <div v-for="k in ['zone', 'fee', 'date']" :key="k" class="rounded-xl border border-border-input bg-white px-4 py-2">
          <span class="block font-mono text-[10px] font-medium uppercase tracking-[.12em] text-teal-hover">{{ t(`explorer.search.${k}`) }}</span>
          <span class="mt-0.5 block text-[15px] text-ink-control">{{ t(`explorer.search.${k}V`) }}</span>
        </div>
        <button type="submit" class="min-h-14 rounded-full bg-navy px-5 font-medium text-white shadow-cta transition hover:-translate-y-0.5 hover:bg-blue">{{ t('explorer.search.go') }}</button>
      </form>

      <div class="mt-10 grid grid-cols-[repeat(auto-fit,minmax(min(100%,300px),1fr))] gap-6">
        <article
          v-for="e in list" :key="e.id"
          class="group flex flex-col overflow-hidden rounded-card border border-sand/30 bg-cream shadow-card transition hover:-translate-y-0.5 hover:shadow-elevated"
        >
          <div class="relative h-56" :style="{ background: `linear-gradient(135deg, ${e.from}, ${e.to})` }">
            <div class="absolute left-3 top-3 flex gap-1.5 font-mono text-xs">
              <span class="rounded-full bg-white/90 px-2.5 py-1 text-ink-control">{{ t(`explorer.filters.${e.cat}`) }}</span>
              <span class="rounded-full bg-navy-darkest/85 px-2.5 py-1 text-white">{{ e.km }} km</span>
            </div>
            <span class="absolute bottom-3 left-3 font-mono text-[10px] tracking-widest text-white/80">FOTO</span>
          </div>
          <div class="flex flex-1 flex-col p-5">
            <p class="flex items-center gap-1.5 font-mono text-xs text-muted">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" /><path d="M9 12l2 2 4-4" /></svg>
              {{ t('explorer.rnt') }} · {{ e.zone }}
            </p>
            <h3 class="mt-2 text-xl font-bold leading-snug tracking-tight text-navy-darkest">{{ t(`items.${e.id}.name`) }}</h3>
            <p class="mt-2 line-clamp-2 text-[15px] leading-relaxed text-muted">{{ t(`items.${e.id}.desc`) }}</p>
            <div class="mt-4 rounded-xl border border-sand/30 bg-white px-3.5 py-3">
              <div class="flex justify-between font-mono text-xs text-muted">
                <span>{{ t('explorer.aforo') }}</span>
                <span class="font-semibold" :class="txt[level(e.aforo)]">{{ e.aforo }}% ({{ t(`explorer.status.${level(e.aforo)}`) }})</span>
              </div>
              <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-cream" role="progressbar" :aria-valuenow="e.aforo" aria-valuemin="0" aria-valuemax="100">
                <div class="h-full rounded-full" :class="bar[level(e.aforo)]" :style="{ width: e.aforo + '%' }" />
              </div>
            </div>
            <div class="mt-auto flex items-center justify-between border-t border-sand/30 pt-4 mt-5">
              <div>
                <p class="font-mono text-[10px] uppercase tracking-[.12em] text-muted">{{ t('explorer.fee') }}</p>
                <p class="text-lg font-semibold tabular-nums text-ink">{{ cop(e.fee) }}</p>
              </div>
              <RouterLink :to="{ name: 'service', params: { id: e.id } }" class="rounded-full bg-navy px-5 py-2.5 text-sm font-medium text-white shadow-cta transition hover:bg-blue">{{ t('explorer.details') }}</RouterLink>
            </div>
          </div>
        </article>
        <p v-if="!list.length" class="text-muted">{{ t('explorer.empty') }}</p>
      </div>
      <p v-if="source === 'demo'" class="mt-4 font-mono text-[11px] text-muted/80">{{ t('explorer.mock') }}</p>

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
