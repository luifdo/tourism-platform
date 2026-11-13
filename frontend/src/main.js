import { createApp } from 'vue'
import { createI18n } from 'vue-i18n'
import App from './App.vue'
import router from './router'
import es from './locales/es'
import en from './locales/en'
import gestionEs from './locales/gestion.es'
import gestionEn from './locales/gestion.en'
import { initOffline, submitOrQueue } from './lib/offlineQueue'
import { borrarCachesObsoletas } from './lib/limpiezaLocal'
import { registrarError } from './lib/errorGlobal'
import '@fontsource/geist/latin-300.css'
import '@fontsource/geist/latin-400.css'
import '@fontsource/geist/latin-500.css'
import '@fontsource/geist/latin-600.css'
import '@fontsource/geist/latin-700.css'
import '@fontsource/geist/latin-800.css'
import '@fontsource/geist-mono/latin-400.css'
import '@fontsource/geist-mono/latin-500.css'
import '@fontsource/geist-mono/latin-600.css'
import './styles/main.css'

const saved = (() => { try { return localStorage.getItem('lang') } catch { return null } })()

export const i18n = createI18n({
  legacy: false,
  locale: saved === 'en' ? 'en' : 'es', // español por defecto (RF-10)
  fallbackLocale: 'es',
  messages: { es: { ...es, ...gestionEs }, en: { ...en, ...gestionEn } },
})

const app = createApp(App).use(router).use(i18n)
// Una excepción que nadie atrapó no debe dejar la pantalla a medias sin decir nada
app.config.errorHandler = (e) => registrarError(e)
window.addEventListener('unhandledrejection', (ev) => registrarError(ev.reason))
window.addEventListener('error', (ev) => registrarError(ev.error ?? ev.message))
app.mount('#app')
borrarCachesObsoletas()

initOffline()
if (import.meta.env.DEV) window.__queue = { submitOrQueue } // solo para probar la cola en desarrollo
