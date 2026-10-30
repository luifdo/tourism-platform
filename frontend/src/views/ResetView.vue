<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { AuthError } from '../domain/auth/errors'
import { queue } from '../lib/offlineQueue'
import { repartirError, textoDeError } from '../ui/authErrors'
import { useSession } from '../ui/useSession'
import AuthShell from '../components/auth/AuthShell.vue'
import PasswordField from '../components/auth/PasswordField.vue'

/* UC3, paso 2: nueva contraseña con el token del enlace (?token=...) */
const { t, te } = useI18n()
const route = useRoute()
const router = useRouter()
const { restablecerPassword } = useSession()

const password = ref('')
const confirmacion = ref('')
const enviando = ref(false)
const errores = ref({})
const general = ref('')
const enlaceInvalido = ref(!route.query.token)

async function enviar() {
  errores.value = {}; general.value = ''
  enviando.value = true
  try {
    await restablecerPassword({ token: String(route.query.token ?? ''), password: password.value, confirmacion: confirmacion.value })
    router.replace({ name: 'login', query: { restablecida: '1' } })
  } catch (e) {
    if (!(e instanceof AuthError)) { general.value = textoDeError('generic', t, te); return }
    if (e.code === 'TOKEN_INVALIDO') { enlaceInvalido.value = true; return }
    const r = repartirError(e)
    errores.value = Object.fromEntries(Object.entries(r.campos).map(([k, v]) => [k, k === 'confirmacion' ? t('auth.errors.mismatch') : textoDeError(v.codigo ?? e.code, t, te)]))
    if (!Object.keys(errores.value).length) general.value = textoDeError(e.code, t, te)
  } finally { enviando.value = false }
}
</script>

<template>
  <AuthShell :title="t('auth.reset.title')">
    <div v-if="enlaceInvalido" role="alert">
      <p class="rounded-xl bg-danger-bg px-4 py-3 text-sm text-danger">{{ t('auth.reset.invalid') }}</p>
      <RouterLink :to="{ name: 'recover' }" class="mt-4 inline-block font-semibold text-navy hover:text-teal">{{ t('auth.reset.requestNew') }} →</RouterLink>
    </div>

    <form v-else class="flex flex-col gap-4" novalidate @submit.prevent="enviar">
      <PasswordField id="password" v-model="password" :label="t('auth.reset.password')" autocomplete="new-password" show-rules :error="errores.password" />
      <PasswordField id="confirmacion" v-model="confirmacion" :label="t('auth.reset.confirm')" autocomplete="new-password" :error="errores.confirmacion" />
      <p v-if="general" class="rounded-xl bg-danger-bg px-4 py-3 text-sm text-danger" role="alert">{{ general }}</p>
      <p v-if="!queue.online" class="rounded-xl bg-warn-bg px-4 py-3 text-sm text-warn">{{ t('auth.login.needOnline') }}</p>
      <button type="submit" class="rounded-full bg-navy px-6 py-3.5 font-semibold text-white shadow-cta transition hover:bg-blue disabled:opacity-50" :disabled="enviando || !queue.online">
        {{ enviando ? t('auth.reset.submitting') : t('auth.reset.submit') }}
      </button>
    </form>
  </AuthShell>
</template>
