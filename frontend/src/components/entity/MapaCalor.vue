<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

/* Mapa de calor de saturación por zona (RF-07): cada polígono se pinta según su nivel (BAJO, MEDIO, ALTO). Los nombres vienen del servidor: se arman como texto, nunca como HTML. */
const props = defineProps({ geojson: { type: Object, default: null } })
const el = ref(null)
let map
let capa
const COLOR = { BAJO: '#009767', MEDIO: '#F99C00', ALTO: '#E40014' }

function pintar() {
  if (!map) return
  capa?.remove()
  if (!props.geojson?.features?.length) return
  capa = L.geoJSON(props.geojson, {
    style: (f) => ({ color: COLOR[f.properties.nivel] ?? '#5D9A92', weight: 2, fillOpacity: 0.35 }),
    onEachFeature: (f, layer) => {
      const caja = document.createElement('span')
      caja.textContent = `${f.properties.nombre}: ${f.properties.nivel_etiqueta ?? f.properties.nivel ?? '—'}${f.properties.indice != null ? ` (${Math.round(f.properties.indice * 100)} %)` : ''}`
      layer.bindTooltip(caja, { sticky: true })
    },
  }).addTo(map)
  map.fitBounds(capa.getBounds(), { padding: [20, 20], maxZoom: 12 })
}
onMounted(() => {
  map = L.map(el.value, { scrollWheelZoom: false }).setView([11.24, -74.2], 10)
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' }).addTo(map)
  pintar()
})
watch(() => props.geojson, pintar)
onBeforeUnmount(() => map?.remove())
</script>

<template>
  <div ref="el" class="h-[320px] w-full overflow-hidden rounded-card border border-sand/30" role="region" aria-label="Mapa" />
</template>
