<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { TOTAL, conjuntoPara, cuadroMasCercano, indiceDeAvance, ordenDeCarga, recorteCover, rutaDeCuadro } from '../lib/heroFrames'

const { t, tm, rt } = useI18n()
const router = useRouter()

// El buscador de la portada lleva al explorador del catálogo con lo escrito (?q=), que es donde se busca de verdad
const destino = ref('')
const buscar = () => router.push({ name: 'home', query: destino.value.trim() ? { q: destino.value.trim().slice(0, 200) } : {}, hash: '#catalogo' })

const base = import.meta.env.BASE_URL
const story = ref(null)
const lienzo = ref(null)
const p = ref(0) // progreso 0..1 del scroll dentro del hero

const reduced = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
const stats = computed(() => tm('hero.stats').map((s) => ({ k: rt(s.k), n: rt(s.n), l: rt(s.l) })))
const icons = [
  'M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6zM9 12l2 2 4-4',
  'M12 7v5l3 2M12 21a9 9 0 100-18 9 9 0 000 18z',
  'M4 6h16M4 12h16M4 18h10',
  'M3 5h12M9 3v2M5 11c2 4 6 7 10 8M13 11c-1 3-4 6-9 8M14 21l4-9 4 9M15.5 18h5',
]

/*
 * La portada se mueve con el scroll dibujando, en un canvas, el fotograma que toca (ver lib/heroFrames.js). No es un <video>: un video
 * necesita permiso para reproducirse y en iOS con el modo de bajo consumo no se mueve; las imágenes se cargan siempre, en Safari,
 * Chrome y demás. Los cuadros se piden por capas (inicio y final, de a 16, de a 8...): el scroll ya funciona con pocos y se afina
 * solo; mientras no hay ninguno, se ve el póster. Con movimiento reducido solo se carga y se muestra el primer cuadro.
 */
const cuadros = new Array(TOTAL).fill(null) // Image ya cargadas
const listo = new Array(TOTAL).fill(false)
let conjunto = conjuntoPara(window.innerWidth, window.innerHeight)
let generacion = 0 // un cambio de conjunto (girar el teléfono) descarta las cargas del anterior
let ctx = null
let cur = 0 // posición suavizada, en cuadros
let target = 0
let raf = 0
let dibujado = -1
let vivo = true

function ajustarLienzo() {
  const c = lienzo.value
  if (!c) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const w = Math.round(c.clientWidth * dpr)
  const h = Math.round(c.clientHeight * dpr)
  if (c.width !== w || c.height !== h) { c.width = w; c.height = h; dibujado = -1 }
  ctx = c.getContext('2d')
}

function dibujar() {
  const c = lienzo.value
  if (!c || !ctx) return
  const i = cuadroMasCercano(Math.round(cur), listo)
  if (i == null || i === dibujado) return
  const img = cuadros[i]
  const r = recorteCover(img.naturalWidth, img.naturalHeight, c.width, c.height)
  ctx.drawImage(img, r.sx, r.sy, r.sw, r.sh, 0, 0, c.width, c.height)
  dibujado = i
}

function cargar(i, gen) {
  return new Promise((resolver) => {
    const img = new Image()
    img.decoding = 'async'
    img.onload = () => {
      if (gen === generacion && vivo) { cuadros[i] = img; listo[i] = true; dibujar() }
      resolver()
    }
    img.onerror = () => resolver() // un cuadro que falta se salta: se dibuja el más cercano
    img.src = rutaDeCuadro(base, conjunto, i)
  })
}

async function cargarTodos() {
  const gen = ++generacion
  cuadros.fill(null); listo.fill(false); dibujado = -1
  const ahorro = !!navigator.connection?.saveData
  const orden = reduced ? [0] : ordenDeCarga(TOTAL, ahorro ? 3 : 1)
  let siguiente = 0
  // Cuatro a la vez: no se compite con el resto de la página, y el orden de las capas se respeta
  const hilo = async () => { while (vivo && gen === generacion && siguiente < orden.length) await cargar(orden[siguiente++], gen) }
  await Promise.all([hilo(), hilo(), hilo(), hilo()])
}

function onScroll() {
  const el = story.value
  if (!el) return
  const max = el.offsetHeight - el.firstElementChild.offsetHeight
  target = Math.min(1, Math.max(0, -el.getBoundingClientRect().top / (max || 1)))
  p.value = target
  if (!raf && !reduced) raf = requestAnimationFrame(tick)
}

// El cuadro actual alcanza al del scroll con suavizado; el bucle se detiene al converger
function tick() {
  const meta = indiceDeAvance(target)
  cur += (meta - cur) * 0.22
  if (Math.abs(meta - cur) < 0.3) cur = meta
  dibujar()
  raf = cur !== meta ? requestAnimationFrame(tick) : 0
}

function onResize() {
  const nuevo = conjuntoPara(window.innerWidth, window.innerHeight)
  ajustarLienzo()
  if (nuevo !== conjunto) { conjunto = nuevo; cargarTodos() } else dibujar()
  onScroll()
}

onMounted(() => {
  ajustarLienzo()
  cargarTodos()
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('resize', onResize)
  onScroll()
  cur = indiceDeAvance(target)
})
onBeforeUnmount(() => {
  vivo = false
  cancelAnimationFrame(raf)
  window.removeEventListener('scroll', onScroll)
  window.removeEventListener('resize', onResize)
})
</script>

<template>
  <!-- Con movimiento reducido: sin altura extra, video detenido (WCAG) -->
  <section ref="story" :style="{ height: reduced ? 'auto' : '320vh' }" aria-label="Inicio">
    <div class="hero-pin overflow-hidden bg-cream">
      <!-- El póster se ve de inmediato; el canvas lo cubre en cuanto llega el primer cuadro -->
      <div class="absolute inset-0 bg-cover bg-center" :style="{ backgroundImage: `url(${base}video/hero-poster.jpg)` }" aria-hidden="true" />
      <canvas ref="lienzo" class="absolute inset-0 size-full" aria-hidden="true" />
      <!-- Sin velo sobre el video: solo un degradado azul suave a la izquierda para leer el texto -->
      <div class="absolute inset-0 bg-[linear-gradient(90deg,rgba(2,31,57,.55)_0%,rgba(2,31,57,.25)_40%,rgba(2,31,57,0)_70%),linear-gradient(0deg,rgba(2,31,57,.35)_0%,rgba(2,31,57,0)_35%)]" />
      <!-- Difuminado de los bordes con degradados simples (sin máscara: Safari deja de repintar un video enmascarado) -->
      <div class="pointer-events-none absolute inset-x-0 top-0 h-14 bg-gradient-to-b from-cream to-cream/0" />
      <div class="pointer-events-none absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-white to-white/0" />

      <div class="relative mx-auto flex h-full max-w-[1400px] flex-col justify-center gap-[clamp(10px,2.4vh,28px)] px-[clamp(20px,5vw,64px)] pb-[76px] pt-9 sm:pb-24 sm:pt-6">
        <p class="kicker inline-flex w-fit items-center gap-2 rounded-full border border-sand/40 bg-white/85 px-3 py-1 text-[10px] tracking-[.12em] text-ink-control sm:px-4 sm:py-1.5 sm:text-[11px] sm:tracking-[.22em]">
          <span class="size-1.5 rounded-full bg-teal" />{{ t('hero.eyebrow') }}
        </p>
        <h1 class="max-w-[14ch] text-[clamp(32px,min(6.4vw,10.5vh),92px)] font-extrabold leading-[.98] tracking-[-.035em] text-white text-balance">{{ t('hero.title') }}</h1>
        <p class="max-w-[58ch] line-clamp-3 text-[clamp(14px,1.5vw,21px)] leading-relaxed text-white/90 sm:line-clamp-none">{{ t('hero.lead') }}</p>

        <form class="flex w-full max-w-[860px] flex-wrap items-center gap-2 rounded-[28px] border border-sand/30 bg-white p-2 shadow-elevated sm:flex-nowrap sm:rounded-full" @submit.prevent="buscar">
          <label class="flex min-w-0 flex-1 items-center gap-3 rounded-full px-3 py-1.5 sm:px-4 sm:py-2">
            <svg class="shrink-0 text-teal" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M15.5 8.5l-2 5-5 2 2-5z" /></svg>
            <span class="min-w-0 flex-1">
              <span class="block font-mono text-[10px] uppercase tracking-[.12em] text-muted">{{ t('hero.searchDest') }}</span>
              <input v-model="destino" type="search" maxlength="200" :placeholder="t('hero.searchDestPh')" class="w-full bg-transparent text-[15px] font-medium text-ink outline-none placeholder:text-muted/70" />
            </span>
          </label>
          <button type="submit" class="flex w-full items-center justify-center gap-2 rounded-full bg-navy px-8 py-3 font-semibold text-white shadow-cta transition hover:bg-blue sm:w-auto sm:py-3.5">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" /></svg>
            {{ t('hero.go') }}
          </button>
        </form>

        <ul class="mt-[clamp(4px,2vh,24px)] grid grid-cols-2 gap-3 lg:grid-cols-4 [@media(max-height:920px)]:hidden">
          <li v-for="(s, i) in stats" :key="s.k" class="glass rounded-card p-3 shadow-card sm:p-4">
            <div class="flex items-center justify-between">
              <span class="font-mono text-[10px] uppercase tracking-[.14em] text-muted">{{ s.k }}</span>
              <svg class="text-teal" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="icons[i]" /></svg>
            </div>
            <p class="mt-1 text-[clamp(22px,3vw,40px)] font-bold leading-none tracking-tight text-navy-darkest sm:mt-1.5">{{ s.n }}</p>
            <p class="mt-2 hidden text-[13px] leading-snug text-muted sm:block">{{ s.l }}</p>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>
