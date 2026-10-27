<script setup>
import { useI18n } from 'vue-i18n'
import { routes } from '../data/mock'

const { t } = useI18n()
const icons = {
  hike: 'M13 4a1.5 1.5 0 100 3 1.5 1.5 0 000-3zM9 21l2-6-2-2 1-5 3 2 3 1M11 15l-3 6',
  kayak: 'M3 17c2 0 2 1 4 1s2-1 4-1 2 1 4 1 2-1 4-1M5 13l14-4M14 7l3 6',
  dive: 'M4 18c3-1 5-4 7-7s4-4 8-5M16 4l4 2-2 4M3 21c2 0 2-1 4-1',
}
</script>

<template>
  <section id="rutas" class="bg-white px-[clamp(20px,6vw,96px)] py-[clamp(56px,8vw,100px)]">
    <div class="mx-auto max-w-[1200px]">
      <div class="mx-auto max-w-2xl text-center">
        <p class="kicker inline-flex items-center gap-2 rounded-full border border-sand/40 bg-cream px-4 py-1.5"><span class="size-1.5 rounded-full bg-teal" />{{ t('routes.kicker') }}</p>
        <h2 class="mt-4 text-[clamp(32px,4vw,52px)] font-bold leading-[1.1] tracking-[-.025em] text-navy-darkest text-balance">{{ t('routes.title') }}</h2>
        <p class="mt-4 text-[17px] leading-relaxed text-muted">{{ t('routes.lead') }}</p>
      </div>

      <div class="mt-12 grid grid-cols-[repeat(auto-fit,minmax(min(100%,300px),1fr))] gap-6">
        <article v-for="r in routes" :key="r.id" class="flex flex-col rounded-panel border border-sand/30 bg-cream p-7 shadow-card transition hover:-translate-y-0.5 hover:shadow-elevated">
          <span class="grid size-14 place-items-center rounded-2xl bg-white text-navy shadow-card">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="icons[r.icon]" /></svg>
          </span>
          <p class="mt-7 font-mono text-xs uppercase tracking-[.12em] text-teal">{{ t('routes.label') }} 0{{ r.id }}</p>
          <h3 class="mt-2 text-[22px] font-bold leading-snug tracking-tight text-navy-darkest">{{ t(`routeItems.${r.id}.name`) }}</h3>
          <p class="mt-3 flex-1 text-[15px] leading-relaxed text-muted">{{ t(`routeItems.${r.id}.desc`) }}</p>
          <div class="mt-6 flex items-center justify-between gap-3 border-t border-sand/30 pt-4 font-mono text-xs">
            <span class="text-muted">{{ t(`routeItems.${r.id}.meta`) }}</span>
            <a href="#" class="font-semibold text-navy hover:text-teal">{{ t('routes.itinerary') }} →</a>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>
