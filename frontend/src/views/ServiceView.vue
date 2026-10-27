<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { capacity, findService, providers, level } from '../data/mock'
import BookingWidget from '../components/BookingWidget.vue'

const props = defineProps({ id: { type: String, required: true } })
const { t, n } = useI18n()

// En producción: GET /api/catalog/servicios/{id}
const service = computed(() => findService(props.id))
const provider = computed(() => providers[props.id])
const cop = (v) => n(v, { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })
const bar = { ok: 'bg-ok', mid: 'bg-warn', high: 'bg-danger' }
</script>

<template>
  <div class="bg-cream px-[clamp(20px,5vw,64px)] py-8 sm:py-12">
    <div class="mx-auto max-w-[1200px]">
      <RouterLink :to="{ name: 'home', hash: '#catalogo' }" class="inline-flex items-center gap-1.5 font-mono text-sm text-navy hover:text-teal">← {{ t('service.back') }}</RouterLink>

      <p v-if="!service" class="mt-10 text-lg text-muted">{{ t('service.notFound') }}</p>

      <div v-else class="mt-6 grid items-start gap-8 lg:grid-cols-[1.4fr_1fr]">
        <article>
          <div class="relative h-[clamp(200px,34vw,360px)] overflow-hidden rounded-panel shadow-elevated" :style="{ background: `linear-gradient(135deg, ${service.from}, ${service.to})` }">
            <div class="absolute left-4 top-4 flex gap-2 font-mono text-xs">
              <span class="rounded-full bg-white/90 px-3 py-1 text-ink-control">{{ t(`explorer.filters.${service.cat}`) }}</span>
              <span class="rounded-full bg-navy-darkest/85 px-3 py-1 text-white">{{ service.km }} km</span>
            </div>
            <span class="absolute bottom-4 left-4 font-mono text-[10px] tracking-widest text-white/80">FOTO</span>
          </div>

          <p class="kicker mt-8 flex items-center gap-2"><span class="size-1.5 rounded-full bg-teal" />{{ service.zone }}</p>
          <h1 class="mt-2 text-[clamp(30px,4vw,48px)] font-bold leading-[1.1] tracking-[-.02em] text-navy-darkest text-balance">{{ t(`items.${service.id}.name`) }}</h1>
          <p class="mt-3 flex items-center gap-1.5 font-mono text-xs text-muted">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" /><path d="M9 12l2 2 4-4" /></svg>
            {{ t('explorer.rnt') }} #{{ provider.rnt }}
          </p>

          <h2 class="mt-8 text-lg font-bold text-navy-darkest">{{ t('service.about') }}</h2>
          <p class="mt-2 leading-relaxed text-ink-control">{{ t(`items.${service.id}.long`) }}</p>

          <dl class="mt-8 grid gap-4 sm:grid-cols-3">
            <div class="rounded-card border border-sand/30 bg-white p-4 shadow-card">
              <dt class="font-mono text-[10px] uppercase tracking-[.12em] text-muted">{{ t('service.fee') }}</dt>
              <dd class="mt-1 text-xl font-semibold tabular-nums text-ink">{{ cop(service.fee) }}</dd>
              <dd class="text-xs text-muted">{{ t('service.perPerson') }}</dd>
            </div>
            <div class="rounded-card border border-sand/30 bg-white p-4 shadow-card">
              <dt class="font-mono text-[10px] uppercase tracking-[.12em] text-muted">{{ t('service.capacity') }}</dt>
              <dd class="mt-1 text-xl font-semibold tabular-nums text-ink">{{ capacity[service.id] }} {{ t('service.people') }}</dd>
            </div>
            <div class="rounded-card border border-sand/30 bg-white p-4 shadow-card">
              <dt class="font-mono text-[10px] uppercase tracking-[.12em] text-muted">{{ t('explorer.aforo') }}</dt>
              <dd class="mt-1 text-xl font-semibold tabular-nums text-ink">{{ service.aforo }}%</dd>
              <dd class="mt-2 h-1.5 overflow-hidden rounded-full bg-cream"><div class="h-full rounded-full" :class="bar[level(service.aforo)]" :style="{ width: service.aforo + '%' }" /></dd>
            </div>
          </dl>

          <div class="mt-8 grid gap-4 sm:grid-cols-2">
            <div class="rounded-card border border-sand/30 bg-white p-5 shadow-card">
              <h3 class="font-mono text-[11px] uppercase tracking-[.14em] text-teal">{{ t('service.provider') }}</h3>
              <p class="mt-2 font-semibold text-navy-darkest">{{ provider.name }}</p>
              <p class="text-sm text-muted">{{ t('service.phone') }}: {{ provider.phone }}</p>
            </div>
            <div class="rounded-card border border-sand/40 bg-sand/10 p-5">
              <h3 class="font-mono text-[11px] uppercase tracking-[.14em] text-teal">{{ t('service.policy') }}</h3>
              <p class="mt-2 text-sm leading-snug text-ink-control">{{ t(`items.${service.id}.policy`) }}</p>
              <p class="mt-2 text-xs leading-snug text-muted">{{ t('service.rule') }}</p>
            </div>
          </div>
        </article>

        <aside class="lg:sticky lg:top-[calc(var(--nav-h)+16px)]">
          <BookingWidget :service="service" />
        </aside>
      </div>
    </div>
  </div>
</template>
