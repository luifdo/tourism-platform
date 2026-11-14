<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { assistantOpen as isOpen } from '../lib/assistant'
import { useSession } from '../ui/useSession'
import { puedeReintentar, useAssistant } from '../ui/useAssistant'
import { MAX_MENSAJE, largo, puedeUsarAsistente } from '../domain/assistant/rules'

const { t, te, locale } = useI18n()
const route = useRoute()
const { sesion, expirar } = useSession()
const { estado, enviar, reintentar, reiniciar } = useAssistant()

const borrador = ref('')
const lista = ref(null)
const campo = ref(null)
const enLinea = ref(typeof navigator === 'undefined' ? true : navigator.onLine)
const alCambiarRed = () => { enLinea.value = navigator.onLine }
onMounted(() => { window.addEventListener('online', alCambiarRed); window.addEventListener('offline', alCambiarRed) })
onBeforeUnmount(() => { window.removeEventListener('online', alCambiarRed); window.removeEventListener('offline', alCambiarRed) })

// Qué se le muestra a cada visitante: sin sesión, con otro rol, o el chat
const modo = computed(() => (!sesion.autenticado ? 'invitado' : puedeUsarAsistente(sesion.usuario?.rol) ? 'chat' : 'rol'))
const caracteres = computed(() => largo(borrador.value))
const sugerencias = ['s1', 's2', 's3']

const textoError = computed(() => {
  const e = estado.error
  if (!e) return ''
  const clave = te(`assistant.errors.${e.codigo}`) ? e.codigo : 'generic'
  return t(`assistant.errors.${clave}`, { minutos: Math.max(1, Math.ceil((e.retryAfter ?? 300) / 60)) })
})

const opciones = () => ({ idioma: locale.value, alExpirar: expirar })
async function mandar(texto = borrador.value) {
  if (!enLinea.value) return
  const previo = borrador.value
  if (texto === borrador.value) borrador.value = ''
  const ok = await enviar(texto, opciones())
  if (!ok && !estado.mensajes.length) borrador.value = previo
  campo.value?.focus()
}

// Otra persona (o ninguna) en la sesión: la conversación era de la anterior
watch(() => sesion.usuario?.id ?? null, () => { reiniciar(); borrador.value = '' })

// Siempre se ve lo último; al abrir, el cursor queda en el campo
const alFondo = () => nextTick(() => { if (lista.value) lista.value.scrollTop = lista.value.scrollHeight })
watch(() => [estado.mensajes.length, estado.enviando, estado.error], alFondo)
watch(isOpen, (abierto) => { if (abierto) nextTick(() => { campo.value?.focus(); alFondo() }) })
</script>

<template>
  <div class="fixed right-[clamp(16px,2.5vw,32px)] z-[60] flex flex-col items-end gap-3.5" style="bottom: calc(env(safe-area-inset-bottom) + clamp(16px, 2.5vw, 28px))">
    <section
      v-if="isOpen"
      class="flex max-h-[min(560px,calc(100vh-140px))] w-[min(380px,calc(100vw-32px))] flex-col overflow-hidden rounded-panel bg-white/95 shadow-[0_30px_70px_-20px_rgba(0,103,152,.6)] backdrop-blur-xl"
      role="dialog" :aria-label="t('assistant.title')" @keydown.esc="isOpen = false"
    >
      <header class="flex items-center justify-between gap-3 bg-navy-darkest px-5 py-4 text-white">
        <div class="min-w-0">
          <p class="font-semibold">{{ t('assistant.title') }}</p>
          <p class="mt-0.5 font-mono text-[10px] tracking-[.08em] text-[#a9ddd4]">{{ t('assistant.note') }}</p>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <button v-if="estado.mensajes.length" type="button" class="grid size-8 place-items-center rounded-full bg-white/10 hover:bg-white/25" :aria-label="t('assistant.newChat')" :title="t('assistant.newChat')" @click="reiniciar">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
          </button>
          <button type="button" class="grid size-8 place-items-center rounded-full bg-white/10 text-lg hover:bg-white/25" :aria-label="t('assistant.close')" @click="isOpen = false">×</button>
        </div>
      </header>

      <!-- Sin sesión o con un rol que no es Turista: el servicio responde 401 / 403 -->
      <div v-if="modo !== 'chat'" class="flex flex-col gap-3 bg-[#EAF4F9] px-5 py-6 text-sm text-ink-control">
        <template v-if="modo === 'invitado'">
          <p class="font-semibold text-navy-darkest">{{ t('assistant.guestTitle') }}</p>
          <p>{{ t('assistant.guestBody') }}</p>
          <div class="flex flex-wrap gap-2.5 pt-1">
            <RouterLink :to="{ name: 'login', query: { redirect: route.fullPath } }" class="rounded-full bg-navy px-5 py-2.5 font-medium text-white hover:bg-blue" @click="isOpen = false">{{ t('assistant.login') }}</RouterLink>
            <RouterLink :to="{ name: 'register' }" class="rounded-full border border-navy px-5 py-2.5 font-medium text-navy hover:bg-white" @click="isOpen = false">{{ t('assistant.register') }}</RouterLink>
          </div>
        </template>
        <p v-else>{{ t('assistant.onlyTourist') }}</p>
      </div>

      <template v-else>
        <div ref="lista" class="flex flex-col gap-3.5 overflow-auto bg-[#EAF4F9] px-5 py-4" role="log" aria-live="polite" :aria-label="t('assistant.title')">
          <p class="max-w-[88%] self-start rounded-[16px_16px_16px_4px] bg-white px-3.5 py-2.5 text-sm text-ink-control shadow-card">{{ t('assistant.hello') }}</p>

          <div v-if="!estado.mensajes.length" class="flex flex-col items-end gap-2">
            <button v-for="s in sugerencias" :key="s" type="button" class="max-w-[92%] rounded-[16px_16px_4px_16px] border border-navy/30 bg-white px-3.5 py-2 text-left text-[13px] text-navy hover:border-navy hover:bg-cream disabled:opacity-50" :disabled="!enLinea || estado.enviando" @click="mandar(t(`assistant.${s}`))">{{ t(`assistant.${s}`) }}</button>
          </div>

          <template v-for="m in estado.mensajes" :key="m.id">
            <p v-if="m.rol === 'usuario'" class="max-w-[88%] self-end whitespace-pre-wrap break-words rounded-[16px_16px_4px_16px] bg-navy px-3.5 py-2.5 text-sm text-white">{{ m.texto }}</p>
            <p v-else-if="m.rol === 'nota'" class="self-center rounded-full bg-white/70 px-3 py-1 text-center font-mono text-[10px] uppercase tracking-wider text-muted">{{ t(`assistant.${m.clave}`) }}</p>
            <div v-else class="flex flex-col gap-2.5 self-start">
              <p class="max-w-[92%] whitespace-pre-wrap break-words rounded-[16px_16px_16px_4px] bg-white px-3.5 py-2.5 text-sm text-ink-control shadow-card">{{ m.texto }}</p>
              <div v-for="r in m.recomendaciones" :key="r.servicioId" class="rounded-card border border-[#d7e8f0] bg-white p-3.5 shadow-card">
                <p class="font-mono text-[10px] uppercase tracking-[.12em] text-teal">{{ t('assistant.rec') }}</p>
                <p class="mt-1 font-semibold">{{ r.nombre }}</p>
                <p class="mt-2 text-[13px] leading-snug text-ink-control"><b>{{ t('assistant.why') }}</b> {{ r.justificacion }}</p>
                <RouterLink :to="{ name: 'service', params: { id: r.servicioId } }" class="mt-2.5 inline-block text-[13px] font-medium text-navy hover:text-teal" @click="isOpen = false">{{ t('assistant.view') }}</RouterLink>
              </div>
            </div>
          </template>

          <!-- El modelo tarda de 3 a 15 s (hasta 45 s): se avisa que sigue trabajando -->
          <div v-if="estado.enviando" class="flex items-center gap-2.5 self-start rounded-[16px_16px_16px_4px] bg-white px-3.5 py-2.5 text-[13px] text-muted shadow-card" role="status">
            <span class="flex gap-1" aria-hidden="true"><i v-for="n in 3" :key="n" class="size-1.5 animate-bounce rounded-full bg-teal" :style="{ animationDelay: `${(n - 1) * 150}ms` }" /></span>
            {{ t('assistant.typing') }}
          </div>

          <div v-if="estado.error" class="rounded-xl border border-danger/30 bg-danger-bg px-3.5 py-2.5 text-[13px] text-danger" role="alert">
            <p>{{ textoError }}</p>
            <button v-if="puedeReintentar(estado.error) && enLinea" type="button" class="mt-1.5 font-semibold underline" :disabled="estado.enviando" @click="reintentar(opciones())">{{ t('assistant.retry') }}</button>
          </div>
        </div>

        <p v-if="!enLinea" class="bg-warn-bg px-4 py-2 text-center text-[12px] text-warn" role="status">{{ t('assistant.offline') }}</p>
        <form class="flex flex-col gap-1.5 bg-white p-3" @submit.prevent="mandar()">
          <div class="flex gap-2.5">
            <input
              ref="campo" v-model="borrador" type="text" :maxlength="MAX_MENSAJE" autocomplete="off" enterkeyhint="send"
              :placeholder="t('assistant.ph')" :aria-label="t('assistant.ph')" :disabled="estado.enviando || !enLinea"
              class="min-w-0 flex-1 rounded-xl bg-[#EAF4F9] px-3.5 py-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-teal disabled:opacity-60"
            />
            <button type="submit" class="rounded-full bg-navy px-5 text-sm font-medium text-white transition hover:bg-blue disabled:opacity-50" :disabled="estado.enviando || !enLinea || !borrador.trim()">{{ t('assistant.send') }}</button>
          </div>
          <p v-if="caracteres > MAX_MENSAJE - 200" class="text-right font-mono text-[10px] text-muted" :class="{ 'text-danger': caracteres >= MAX_MENSAJE }">{{ caracteres }}/{{ MAX_MENSAJE }}</p>
        </form>
      </template>
    </section>
    <button
      type="button"
      class="flex items-center gap-2 rounded-2xl bg-navy p-3.5 text-sm font-semibold sm:px-5 sm:py-3 text-white shadow-cta transition hover:-translate-y-0.5 hover:bg-blue active:scale-95"
      :aria-expanded="isOpen" @click="isOpen = !isOpen"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2l1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8zM19 14l.9 2.6L22.5 17.5l-2.6.9L19 21l-.9-2.6-2.6-.9 2.6-.9z" /></svg>
      <span class="sr-only sm:not-sr-only">{{ t('assistant.open') }}</span>
    </button>
  </div>
</template>
