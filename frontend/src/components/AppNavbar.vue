<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useSession } from '../ui/useSession'
import BrandLogo from './BrandLogo.vue'
import InstallButton from './InstallButton.vue'

const { t, locale } = useI18n()
const router = useRouter()
const { sesion, salir } = useSession()
const menu = ref(false)
const userMenu = ref(false)
const saliendo = ref(false)
const zonaUsuario = ref(null)

const primerNombre = computed(() => (sesion.usuario?.nombre_completo ?? '').trim().split(/\s+/)[0])
const inicial = computed(() => primerNombre.value.charAt(0).toUpperCase())
// Cierra el menú del usuario al salir de él con el teclado o al tocar fuera
const alPerderFoco = (e) => { if (!zonaUsuario.value?.contains(e.relatedTarget)) userMenu.value = false }

async function cerrarSesion() {
  saliendo.value = true
  try { await salir() } finally { saliendo.value = false; userMenu.value = false; menu.value = false }
  router.push({ name: 'home' })
}

function setLang(l) {
  locale.value = l
  document.documentElement.lang = l
  try { localStorage.setItem('lang', l) } catch { /* sin almacenamiento */ }
}
const links = [['catalog', '#catalogo'], ['map', '#mapa'], ['routes', '#rutas'], ['ethics', '#compromiso']].map(([k, hash]) => [k, { name: 'home', hash }])
</script>

<template>
  <!-- Cinta superior (se desplaza con la página) -->
  <div class="flex items-center justify-between gap-4 bg-cream px-[clamp(16px,3vw,32px)] font-mono text-[11px] text-ink-control" style="height: var(--ticker-h)">
    <p class="flex min-w-0 items-center gap-2.5 truncate">
      <i class="size-1.5 shrink-0 rounded-full bg-teal" />
      <b class="shrink-0 font-semibold uppercase tracking-wider text-navy-darkest">{{ t('ticker.badge') }}</b>
      <span class="hidden truncate text-muted sm:inline">· {{ t('ticker.text') }}</span>
    </p>
    <div class="flex shrink-0 items-center gap-4">
      <span class="hidden items-center gap-1.5 text-teal md:flex">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M5 12a7 7 0 0114 0M8.5 12a3.5 3.5 0 017 0" /><circle cx="12" cy="12" r="1" /></svg>
        {{ t('ticker.live') }}
      </span>
      <div role="group" aria-label="Idioma / Language">
        <button type="button" :aria-pressed="locale === 'es'" :class="locale === 'es' ? 'font-bold text-navy' : 'text-muted'" @click="setLang('es')">ES</button>
        <span class="mx-1 text-muted">|</span>
        <button type="button" :aria-pressed="locale === 'en'" :class="locale === 'en' ? 'font-bold text-navy' : 'text-muted'" @click="setLang('en')">EN</button>
      </div>
    </div>
  </div>

  <!-- Barra principal fija -->
  <header class="sticky top-0 z-50 bg-cream/90 px-[clamp(16px,3vw,32px)] backdrop-blur-xl" style="height: var(--nav-h)">
    <nav class="mx-auto flex h-full max-w-[1400px] items-center justify-between gap-4" aria-label="Principal">
      <RouterLink :to="{ name: 'home' }" class="shrink-0" aria-label="Samaland adventure"><BrandLogo /></RouterLink>

      <div class="hidden items-center rounded-full border border-sand/30 bg-white px-3 py-1.5 shadow-card xl:flex">
        <RouterLink v-for="[k, to] in links" :key="k" :to="to" class="max-w-[150px] rounded-full px-4 py-1.5 text-center text-[13px] font-medium leading-tight text-ink-control transition-colors hover:bg-cream hover:text-navy">{{ t(`nav.${k}`) }}</RouterLink>
      </div>

      <div class="flex items-center gap-2 sm:gap-3">
        <InstallButton />

        <!-- Con sesión: acceso a reservas y menú de la cuenta -->
        <template v-if="sesion.autenticado">
          <RouterLink :to="{ name: 'my-bookings' }" class="flex items-center gap-1.5 text-[13px] font-medium text-navy transition-colors hover:text-teal">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3h12v18l-3-2-3 2-3-2-3 2z" /><path d="M9 8h6M9 12h6" /></svg>
            <span class="hidden sm:inline">{{ t('nav.reservations') }}</span>
          </RouterLink>
          <div ref="zonaUsuario" class="relative" @focusout="alPerderFoco" @keydown.esc="userMenu = false">
            <button type="button" class="flex items-center gap-2 rounded-full border border-sand/40 bg-white py-1 pl-1 pr-3 text-[13px] font-medium text-ink-control shadow-card transition hover:border-teal" :aria-expanded="userMenu" aria-haspopup="menu" :aria-label="t('auth.menu.account')" @click="userMenu = !userMenu">
              <span class="grid size-7 place-items-center rounded-full bg-navy text-xs font-bold text-white" aria-hidden="true">{{ inicial }}</span>
              <span class="hidden max-w-[110px] truncate md:inline">{{ primerNombre }}</span>
            </button>
            <div v-if="userMenu" role="menu" class="absolute right-0 top-[calc(100%+8px)] w-64 rounded-card border border-sand/30 bg-white p-2 shadow-elevated">
              <div class="px-3 py-2">
                <p class="truncate text-sm font-semibold text-navy-darkest">{{ sesion.usuario?.nombre_completo }}</p>
                <p class="truncate font-mono text-[11px] text-muted">{{ sesion.usuario?.email }}</p>
                <p class="mt-1 w-fit rounded bg-teal/15 px-1.5 font-mono text-[10px] uppercase tracking-widest text-teal">{{ sesion.usuario?.rol }}</p>
              </div>
              <RouterLink :to="{ name: 'my-bookings' }" role="menuitem" class="block rounded-lg px-3 py-2 text-sm text-ink-control hover:bg-cream" @click="userMenu = false">{{ t('auth.menu.bookings') }}</RouterLink>
              <button type="button" role="menuitem" class="block w-full rounded-lg px-3 py-2 text-left text-sm text-danger hover:bg-danger-bg disabled:opacity-50" :disabled="saliendo" @click="cerrarSesion">{{ saliendo ? t('auth.menu.loggingOut') : t('auth.menu.logout') }}</button>
            </div>
          </div>
        </template>

        <!-- Sin sesión: ingresar o crear cuenta -->
        <template v-else>
          <RouterLink :to="{ name: 'login' }" class="text-[13px] font-medium text-navy transition-colors hover:text-teal">{{ t('auth.menu.login') }}</RouterLink>
          <RouterLink :to="{ name: 'register' }" class="hidden rounded-full bg-navy px-4 py-2 text-[13px] font-semibold text-white shadow-cta transition hover:-translate-y-0.5 hover:bg-blue sm:inline-block">{{ t('auth.menu.register') }}</RouterLink>
        </template>

        <button type="button" class="xl:hidden" :aria-label="t('nav.menu')" :aria-expanded="menu" @click="menu = !menu">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
        </button>
      </div>
    </nav>

    <div v-if="menu" class="absolute inset-x-0 top-full flex flex-col gap-1 border-b border-sand/30 bg-cream p-4 shadow-elevated xl:hidden">
      <RouterLink v-for="[k, to] in links" :key="k" :to="to" class="rounded-lg px-3 py-3 font-medium text-ink-control hover:bg-white" @click="menu = false">{{ t(`nav.${k}`) }}</RouterLink>
      <template v-if="sesion.autenticado">
        <RouterLink :to="{ name: 'my-bookings' }" class="rounded-lg px-3 py-3 font-medium text-navy hover:bg-white" @click="menu = false">{{ t('nav.reservations') }}</RouterLink>
        <button type="button" class="rounded-lg px-3 py-3 text-left font-medium text-danger hover:bg-white" :disabled="saliendo" @click="cerrarSesion">{{ t('auth.menu.logout') }}</button>
      </template>
      <template v-else>
        <RouterLink :to="{ name: 'login' }" class="rounded-lg px-3 py-3 font-medium text-navy hover:bg-white" @click="menu = false">{{ t('auth.menu.login') }}</RouterLink>
        <RouterLink :to="{ name: 'register' }" class="rounded-full bg-navy px-5 py-3 text-center font-semibold text-white" @click="menu = false">{{ t('auth.menu.register') }}</RouterLink>
      </template>
    </div>
  </header>
</template>
