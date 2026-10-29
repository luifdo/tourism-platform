import { createApp } from 'vue'
import { createI18n } from 'vue-i18n'
import App from './App.vue'
import router from './router'
import es from './locales/es'
import en from './locales/en'
import { initOffline, submitOrQueue } from './lib/offlineQueue'
import './styles/main.css'

const saved = (() => { try { return localStorage.getItem('lang') } catch { return null } })()

export const i18n = createI18n({
  legacy: false,
  locale: saved === 'en' ? 'en' : 'es', // español por defecto (RF-10)
  fallbackLocale: 'es',
  messages: { es, en },
})

createApp(App).use(router).use(i18n).mount('#app')

initOffline()
if (import.meta.env.DEV) window.__queue = { submitOrQueue } // solo para probar la cola en desarrollo
