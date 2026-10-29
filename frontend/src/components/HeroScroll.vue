<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const { t, tm, rt } = useI18n()

const base = import.meta.env.BASE_URL
const story = ref(null)
const video = ref(null)
const p = ref(0) // progreso 0..1 del scroll dentro del hero

const reduced = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
const stats = computed(() => tm('hero.stats').map((s) => ({ k: rt(s.k), n: rt(s.n), l: rt(s.l) })))
const icons = [
  'M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6zM9 12l2 2 4-4',
  'M12 7v5l3 2M12 21a9 9 0 100-18 9 9 0 000 18z',
  'M4 6h16M4 12h16M4 18h10',
  'M3 5h12M9 3v2M5 11c2 4 6 7 10 8M13 11c-1 3-4 6-9 8M14 21l4-9 4 9M15.5 18h5',
]

let cur = 0
let target = 0
let raf = 0

function onScroll() {
  const el = story.value
  if (!el) return
  const max = el.offsetHeight - el.firstElementChild.offsetHeight
  target = Math.min(1, Math.max(0, -el.getBoundingClientRect().top / max))
  p.value = target
  if (!raf && !reduced) raf = requestAnimationFrame(tick)
}

// El video se "escrubea" con suavizado; el bucle se detiene al converger
function tick() {
  cur += (target - cur) * 0.1
  const v = video.value
  if (v && v.duration && !v.seeking) {
    const time = Math.min(v.duration - 0.05, cur * v.duration)
    if (Math.abs(v.currentTime - time) > 0.02) v.currentTime = time
  }
  raf = Math.abs(target - cur) > 0.0005 ? requestAnimationFrame(tick) : 0
}

// iOS no carga un video que nunca se reprodujo (ignora preload): se "despierta" una vez, en silencio, y se pausa
let woke = false
function wake() {
  const v = video.value
  if (woke || !v || reduced) return
  woke = true
  v.muted = true
  const pr = v.play()
  if (pr && pr.then) pr.then(() => { v.pause(); v.currentTime = cur * (v.duration || 0) }).catch(() => { woke = false })
  else v.pause()
}

onMounted(() => {
  wake()
  window.addEventListener('touchstart', wake, { passive: true, once: true })
  window.addEventListener('pointerdown', wake, { passive: true, once: true })
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('resize', onScroll)
  onScroll()
})
onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  window.removeEventListener('scroll', onScroll)
  window.removeEventListener('resize', onScroll)
})
</script>

<template>
  <!-- Con movimiento reducido: sin altura extra, video detenido (WCAG) -->
  <section ref="story" :style="{ height: reduced ? 'auto' : '320vh' }" aria-label="Inicio">
    <div class="hero-pin overflow-hidden bg-cream">
      <video
        ref="video" :src="`${base}video/hero.mp4`" :poster="`${base}video/hero-poster.jpg`" muted playsinline preload="auto" aria-hidden="true" tabindex="-1"
        class="absolute inset-0 size-full object-cover"
      />
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

        <form class="flex w-full max-w-[860px] flex-wrap items-center gap-2 rounded-[28px] border border-sand/30 bg-white p-2 shadow-elevated sm:flex-nowrap sm:rounded-full" @submit.prevent>
          <label class="flex min-w-0 flex-1 items-center gap-3 rounded-full px-3 py-1.5 sm:px-4 sm:py-2">
            <svg class="shrink-0 text-teal" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M15.5 8.5l-2 5-5 2 2-5z" /></svg>
            <span class="min-w-0 flex-1">
              <span class="block font-mono text-[10px] uppercase tracking-[.12em] text-muted">{{ t('hero.searchDest') }}</span>
              <input type="text" :placeholder="t('hero.searchDestPh')" class="w-full bg-transparent text-[15px] font-medium text-ink outline-none placeholder:text-muted/70" />
            </span>
          </label>
          <div class="hidden h-10 w-px bg-sand/40 sm:block" />
          <div class="hidden items-center gap-3 px-4 py-2 md:flex">
            <svg class="shrink-0 text-teal" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M4 10h16M9 3v4M15 3v4" /></svg>
            <span>
              <span class="block font-mono text-[10px] uppercase tracking-[.12em] text-muted">{{ t('hero.searchWhen') }}</span>
              <span class="block text-[15px] font-medium text-ink">{{ t('hero.searchWhenV') }}</span>
            </span>
          </div>
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
