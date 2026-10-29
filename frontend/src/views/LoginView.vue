<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { cuentaDemo } from '../composition'
import { AuthError } from '../domain/auth/errors'
import { rutaSegura } from '../domain/auth/rules'
import { queue } from '../lib/offlineQueue'
import { repartirError, textoDeError } from '../ui/authErrors'
import { useSession } from '../ui/useSession'
import AuthShell from '../components/auth/AuthShell.vue'
import AuthField from '../components/auth/AuthField.vue'
import PasswordField from '../components/auth/PasswordField.vue'

const { t, te } = useI18n()
const route = useRoute()
const router = useRouter()
const { iniciar } = useSession()

const email = ref('')
const password = ref('')
const enviando = ref(false)
const errores = ref({})
const general = ref('')

async function enviar() {
  errores.value = {}; general.value = ''
  enviando.value = true
  try {
    await iniciar({ email: email.value, password: password.value })
    router.replace(rutaSegura(route.query.redirect))
  } catch (e) {
    if (!(e instanceof AuthError)) { general.value = textoDeError('generic', t, te); return }
    const r = repartirError(e)
    errores.value = Object.fromEntries(Object.entries(r.campos).map(([k, v]) => [k, textoDeError(v.codigo ?? e.code, t, te)]))
    // Credenciales incorrectas se muestran arriba del formulario, sin señalar un campo concreto (no revela cuál falló)
    if (!Object.keys(errores.value).length) general.value = textoDeError(e.code, t, te)
  } finally { enviando.value = false }
}

function usarDemo() { email.value = cuentaDemo.email; password.value = cuentaDemo.password }
</script>

<template>
  <AuthShell :title="t('auth.login.title')" :lead="t('auth.login.lead')">
    <p v-if="route.query.expirada" class="mb-4 rounded-xl bg-warn-bg px-4 py-3 text-sm text-warn" role="status">{{ t('auth.login.expired') }}</p>
    <p v-if="route.query.restablecida" class="mb-4 rounded-xl bg-ok-bg px-4 py-3 text-sm text-ok" role="status">{{ t('auth.login.resetDone') }}</p>
    <p v-if="route.query.creada" class="mb-4 rounded-xl bg-ok-bg px-4 py-3 text-sm text-ok" role="status">{{ t('auth.register.createdNoLogin') }}</p>

    <form class="flex flex-col gap-4" novalidate @submit.prevent="enviar">
      <AuthField id="email" v-model="email" :label="t('auth.login.email')" type="email" autocomplete="username" inputmode="email" :error="errores.email" />
      <PasswordField id="password" v-model="password" :label="t('auth.login.password')" autocomplete="current-password" :error="errores.password" />

      <p v-if="general" class="rounded-xl bg-danger-bg px-4 py-3 text-sm text-danger" role="alert">{{ general }}</p>
      <p v-if="!queue.online" class="rounded-xl bg-warn-bg px-4 py-3 text-sm text-warn">{{ t('auth.login.needOnline') }}</p>

      <button type="submit" class="rounded-full bg-navy px-6 py-3.5 font-semibold text-white shadow-cta transition hover:bg-blue disabled:opacity-50" :disabled="enviando || !queue.online">
        {{ enviando ? t('auth.login.submitting') : t('auth.login.submit') }}
      </button>
      <RouterLink :to="{ name: 'recover' }" class="text-center text-sm font-medium text-navy hover:text-teal">{{ t('auth.login.forgot') }}</RouterLink>
    </form>

    <div v-if="cuentaDemo" class="mt-6 rounded-card border border-sand/40 bg-sand/10 p-4 text-sm">
      <p class="font-mono text-[11px] uppercase tracking-[.12em] text-teal">{{ t('auth.login.demoTitle') }}</p>
      <p class="mt-1 text-ink-control">{{ t('auth.login.demoBody') }}</p>
      <button type="button" class="mt-2 font-semibold text-navy hover:text-teal" @click="usarDemo">{{ t('auth.login.demoUse') }}</button>
    </div>

    <template #footer>
      {{ t('auth.login.noAccount') }}
      <RouterLink :to="{ name: 'register', query: route.query.redirect ? { redirect: route.query.redirect } : {} }" class="font-semibold text-navy hover:text-teal">{{ t('auth.login.createAccount') }}</RouterLink>
    </template>
  </AuthShell>
</template>
