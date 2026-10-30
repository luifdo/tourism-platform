<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { places, level } from '../data/mock'

const { t } = useI18n()
const el = ref(null)
let map

const color = { ok: '#009767', mid: '#F99C00', high: '#E40014' }
const chip = {
  ok: 'bg-ok-bg text-ok', mid: 'bg-warn-bg text-warn', high: 'bg-danger-bg text-danger',
}
const label = { ok: 'map.open', mid: 'map.caution', high: 'map.saturated' }

onMounted(() => {
  map = L.map(el.value, { scrollWheelZoom: false }).setView([11.28, -74.0], 10)
  // Solo OpenStreetMap (sin APIs privativas de mapas); la PWA solo cachea teselas ya vistas
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map)
  for (const p of places) {
    const c = color[level(p.aforo)]
    L.marker([p.lat, p.lng], {
      icon: L.divIcon({
        className: '',
        html: `<span style="display:block;width:18px;height:18px;border-radius:9999px;background:${c};border:3px solid #fff;box-shadow:0 0 0 6px ${c}40"></span>`,
        iconSize: [18, 18],
      }),
      title: t(`items.${p.id}.name`),
    }).addTo(map).bindPopup(`<b>${t(`items.${p.id}.name`)}</b><br>${p.aforo}%`)
  }
})
onBeforeUnmount(() => map?.remove())
</script>

<template>
  <section id="mapa" class="bg-cream px-[clamp(20px,6vw,96px)] py-[clamp(56px,8vw,100px)]">
    <div class="mx-auto grid max-w-[1200px] grid-cols-[repeat(auto-fit,minmax(min(100%,420px),1fr))] items-center gap-10">
      <div>
        <p class="kicker flex items-center gap-2"><span class="size-1.5 rounded-full bg-teal" />{{ t('map.kicker') }}</p>
        <h2 class="mt-3 text-[clamp(32px,4vw,52px)] font-bold leading-[1.08] tracking-[-.025em] text-navy-deep text-balance">{{ t('map.title') }}</h2>
        <p class="mt-4 text-[17px] leading-relaxed text-muted">{{ t('map.lead') }}</p>

        <ul class="mt-7 flex flex-col gap-3">
          <li v-for="p in places" :key="p.id" class="glass flex items-center justify-between gap-4 rounded-card px-5 py-4 shadow-card">
            <div class="flex items-center gap-3">
              <span class="size-2.5 rounded-full" :style="{ background: color[level(p.aforo)] }" />
              <div>
                <p class="font-semibold text-navy-darkest">{{ t(`items.${p.id}.name`) }}</p>
                <p class="font-mono text-xs text-muted">{{ p.aforo }}%<template v-if="t(`items.${p.id}.note`, '') !== `items.${p.id}.note`"> · {{ t(`items.${p.id}.note`) }}</template></p>
              </div>
            </div>
            <span class="rounded-full px-3 py-1 font-mono text-xs font-semibold" :class="chip[level(p.aforo)]">{{ t(label[level(p.aforo)]) }}</span>
          </li>
        </ul>
        <a href="#" class="mt-6 inline-flex items-center gap-2 font-mono text-sm font-semibold uppercase tracking-wider text-navy hover:text-teal">{{ t('map.gis') }} →</a>
      </div>

      <div class="relative isolate overflow-hidden rounded-panel border border-navy/20 shadow-elevated">
        <div ref="el" class="h-[460px] w-full" role="application" aria-label="Mapa de capacidad de carga" />
        <div class="glass pointer-events-none absolute bottom-3 left-3 right-3 z-[500] flex flex-wrap items-center justify-between gap-2 rounded-xl px-4 py-2.5 font-mono text-[11px] text-ink-control">
          <span class="flex items-center gap-3">
            <span class="flex items-center gap-1.5"><i class="size-2 rounded-full bg-ok" />{{ t('map.legend.ok') }}</span>
            <span class="flex items-center gap-1.5"><i class="size-2 rounded-full bg-warn" />{{ t('map.legend.mid') }}</span>
            <span class="flex items-center gap-1.5"><i class="size-2 rounded-full bg-danger" />{{ t('map.legend.high') }}</span>
          </span>
          <span class="text-navy">{{ t('map.updated') }}</span>
        </div>
      </div>
    </div>
  </section>
</template>
