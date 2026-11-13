<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { catalogUseCases, isMockBackend } from '../composition'
import { nivelOcupacion } from '../domain/catalog/rules'

const { t, locale } = useI18n()
const router = useRouter()
const el = ref(null)
const puntos = ref([]) // lo que hay en la vista actual del mapa (UC16)
const falloMapa = ref(false)
let map
let capa
let solicitud = 0 // una vista nueva descarta la respuesta de la anterior
let esperar

const color = { ok: '#009767', mid: '#F99C00', high: '#E40014' }
const chip = { ok: 'bg-ok-bg text-ok', mid: 'bg-warn-bg text-warn', high: 'bg-danger-bg text-danger' }
const label = { ok: 'map.open', mid: 'map.caution', high: 'map.saturated' }
const SIN_DATO = '#5D9A92' // el catálogo real no publica el aforo en vivo: el punto va sin semáforo

const colorDe = (p) => (p.ocupacion != null ? color[nivelOcupacion(p.ocupacion)] : SIN_DATO)
const servicios = computed(() => puntos.value.filter((p) => p.tipo === 'servicio').sort((a, b) => a.nombre.localeCompare(b.nombre)))
const hayAforo = computed(() => servicios.value.some((p) => p.ocupacion != null))

const irAFicha = (id) => router.push({ name: 'service', params: { id } })

// Los nombres vienen del servidor (los escribe un prestador): se arman con textContent, nunca con HTML
function marcador(p) {
  const c = colorDe(p)
  const punto = document.createElement('span')
  if (p.tipo === 'grupo') {
    punto.textContent = String(p.conteo)
    punto.style.cssText = `display:grid;place-items:center;width:34px;height:34px;border-radius:9999px;background:${SIN_DATO};color:#fff;font:600 13px system-ui;border:3px solid #fff;box-shadow:0 0 0 6px ${SIN_DATO}40`
    return L.marker([p.lat, p.lon], { icon: L.divIcon({ className: '', html: punto, iconSize: [34, 34] }), title: String(p.conteo) })
      .on('click', () => map.setView([p.lat, p.lon], Math.min(map.getZoom() + 2, 18)))
  }
  punto.style.cssText = `display:block;width:18px;height:18px;border-radius:9999px;background:${c};border:3px solid #fff;box-shadow:0 0 0 6px ${c}40`
  const popup = document.createElement('div')
  const nombre = document.createElement('b')
  nombre.textContent = p.nombre
  popup.append(nombre)
  if (p.ocupacion != null) popup.append(document.createElement('br'), `${p.ocupacion}%`)
  const enlace = document.createElement('a')
  enlace.textContent = t('explorer.details')
  enlace.href = router.resolve({ name: 'service', params: { id: p.id } }).href
  enlace.style.cssText = 'display:block;margin-top:6px;font-weight:600'
  enlace.addEventListener('click', (e) => { e.preventDefault(); irAFicha(p.id) })
  popup.append(enlace)
  return L.marker([p.lat, p.lon], { icon: L.divIcon({ className: '', html: punto, iconSize: [18, 18] }), title: p.nombre }).bindPopup(popup)
}

async function actualizar() {
  const mia = ++solicitud
  const b = map.getBounds()
  try {
    const r = await catalogUseCases.puntosDelMapa({ bbox: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()], zoom: map.getZoom() }, { idioma: locale.value })
    if (mia !== solicitud) return
    puntos.value = r
    falloMapa.value = false
    capa.clearLayers()
    for (const p of r) marcador(p).addTo(capa)
  } catch {
    if (mia === solicitud) falloMapa.value = true
  }
}
const alMover = () => { clearTimeout(esperar); esperar = setTimeout(actualizar, 300) }

onMounted(() => {
  map = L.map(el.value, { scrollWheelZoom: false }).setView([11.28, -74.0], 10)
  // Solo OpenStreetMap (sin APIs privativas de mapas); la PWA solo cachea teselas ya vistas
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map)
  capa = L.layerGroup().addTo(map)
  map.on('moveend', alMover)
  actualizar()
})
watch(locale, actualizar)
onBeforeUnmount(() => { clearTimeout(esperar); map?.remove() })
</script>

<template>
  <section id="mapa" class="bg-cream px-[clamp(20px,6vw,96px)] py-[clamp(56px,8vw,100px)]">
    <div class="mx-auto grid max-w-[1200px] grid-cols-[repeat(auto-fit,minmax(min(100%,420px),1fr))] items-center gap-10">
      <div>
        <p class="kicker flex items-center gap-2"><span class="size-1.5 rounded-full bg-teal" />{{ t('map.kicker') }}</p>
        <h2 class="mt-3 text-[clamp(32px,4vw,52px)] font-bold leading-[1.08] tracking-[-.025em] text-navy-deep text-balance">{{ t('map.title') }}</h2>
        <p class="mt-4 text-[17px] leading-relaxed text-muted">{{ t('map.lead') }}</p>

        <p v-if="falloMapa" class="mt-5 rounded-xl bg-warn-bg px-4 py-2.5 text-sm text-warn" role="status">{{ t('map.error') }}</p>
        <p v-else-if="!servicios.length" class="mt-5 text-muted">{{ t('map.empty') }}</p>
        <ul v-else class="mt-7 flex flex-col gap-3">
          <li v-for="p in servicios.slice(0, 6)" :key="p.id" class="glass flex items-center justify-between gap-4 rounded-card px-5 py-4 shadow-card">
            <div class="flex min-w-0 items-center gap-3">
              <span class="size-2.5 shrink-0 rounded-full" :style="{ background: colorDe(p) }" />
              <div class="min-w-0">
                <RouterLink :to="{ name: 'service', params: { id: p.id } }" class="block truncate font-semibold text-navy-darkest hover:text-navy">{{ p.nombre }}</RouterLink>
                <p v-if="p.ocupacion != null" class="font-mono text-xs text-muted">{{ p.ocupacion }}%</p>
              </div>
            </div>
            <span v-if="p.ocupacion != null" class="rounded-full px-3 py-1 font-mono text-xs font-semibold" :class="chip[nivelOcupacion(p.ocupacion)]">{{ t(label[nivelOcupacion(p.ocupacion)]) }}</span>
          </li>
        </ul>
        <a href="#" class="mt-6 inline-flex items-center gap-2 font-mono text-sm font-semibold uppercase tracking-wider text-navy hover:text-teal">{{ t('map.gis') }} →</a>
      </div>

      <div class="relative isolate overflow-hidden rounded-panel border border-navy/20 shadow-elevated">
        <div ref="el" class="h-[460px] w-full" role="application" :aria-label="t('map.aria')" />
        <div class="glass pointer-events-none absolute bottom-3 left-3 right-3 z-[500] flex flex-wrap items-center justify-between gap-2 rounded-xl px-4 py-2.5 font-mono text-[11px] text-ink-control">
          <span v-if="hayAforo" class="flex items-center gap-3">
            <span class="flex items-center gap-1.5"><i class="size-2 rounded-full bg-ok" />{{ t('map.legend.ok') }}</span>
            <span class="flex items-center gap-1.5"><i class="size-2 rounded-full bg-warn" />{{ t('map.legend.mid') }}</span>
            <span class="flex items-center gap-1.5"><i class="size-2 rounded-full bg-danger" />{{ t('map.legend.high') }}</span>
          </span>
          <span v-else />
          <span class="text-navy">{{ isMockBackend ? t('map.updated') : t('map.source') }}</span>
        </div>
      </div>
    </div>
  </section>
</template>
