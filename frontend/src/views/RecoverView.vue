<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { isMockBackend } from '../composition'
import { AuthError } from '../domain/auth/errors'
import { queue } from '../lib/offlineQueue'
import { textoDeError } from '../ui/authErrors'
import { useSession } from '../ui/useSession'
import AuthShell from '../components/auth/AuthShell.vue'
import AuthField from '../components/auth/AuthField.vue'

/* UC3, paso 1: pedir el enlace de recuperación. Siempre se responde lo mismo, exista o no la cuenta. */
const { t, te } = useI18n()
const { solicitarRecuperacion } = useSession()

const email = ref('')
const enviando = ref(false)
const error = ref('')
const enviado = ref(false)
const tokenDemo = ref(null)

async function enviar() {
  error.value = ''
  enviando.value = true
  try {
    const r = await solicitarRecuperacion(email.value)
    enviado.value = true
    tokenDemo.value = isMockBackend ? r.demo?.token ?? null : null
  } catch (e) {
    error.value = textoDeError(e instanceof AuthError ? e.code : 'generic', t, te)
  } finally { enviando.value = false }
}
</script>

<template>
  <AuthShell :title="t('auth.recover.title')" :lead="enviado ? undefined : t('auth.recover.lead')">
    <div v-if="enviado" role="status">
      <p class="rounded-xl bg-ok-bg px-4 py-3 text-sm leading-relaxed text-ok">{{ t('auth.recover.sent') }}</p>
      <div v-if="tokenDemo" class="mt-4 rounded-card border border-sand/40 bg-sand/10 p-4 text-sm">
        <p class="font-mono text-[11px] uppercase tracking-[.12em] text-teal">{{ t('auth.recover.demoTitle') }}</p>
        <p class="mt-1 text-ink-control">{{ t('auth.recover.demoBody') }}</p>
        <RouterLink :to="{ name: 'reset', query: { token: tokenDemo } }" class="mt-2 inline-block font-semibold text-navy hover:text-teal">{{ t('auth.recover.demoLink') }} →</RouterLink>
      </div>
    </div>

    <form v-else class="flex flex-col gap-4" novalidate @submit.prevent="enviar">
      <AuthField id="email" v-model="email" :label="t('auth.login.email')" type="email" autocomplete="username" inputmode="email" :error="error" />
      <p v-if="!queue.online" class="rounded-xl bg-warn-bg px-4 py-3 text-sm text-warn">{{ t('auth.login.needOnline') }}</p>
      <button type="submit" class="rounded-full bg-navy px-6 py-3.5 font-semibold text-white shadow-cta transition hover:bg-blue disabled:opacity-50" :disabled="enviando || !queue.online">
        {{ enviando ? t('auth.recover.submitting') : t('auth.recover.submit') }}
      </button>
    </form>

    <template #footer>
      <RouterLink :to="{ name: 'login' }" class="font-semibold text-navy hover:text-teal">← {{ t('auth.recover.back') }}</RouterLink>
    </template>
  </AuthShell>
</template>
