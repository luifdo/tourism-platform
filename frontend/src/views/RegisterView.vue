<script setup>
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { AuthError } from '../domain/auth/errors'
import { ROLES_AUTORREGISTRO, rutaSegura } from '../domain/auth/rules'
import { queue } from '../lib/offlineQueue'
import { repartirError, textoDeError } from '../ui/authErrors'
import { useSession } from '../ui/useSession'
import AuthShell from '../components/auth/AuthShell.vue'
import AuthField from '../components/auth/AuthField.vue'
import PasswordField from '../components/auth/PasswordField.vue'

/* UC1 (registro) + UC6 (consentimiento de datos, Ley 1581) + mayoría de edad (18+) */
const { t, te } = useI18n()
const route = useRoute()
const router = useRouter()
const { registrar } = useSession()

const form = reactive({ nombre: '', email: '', password: '', rol: 'Turista', habeasData: false, mayorDeEdad: false })
const enviando = ref(false)
const errores = ref({})
const general = ref('')

const roles = computed(() => ROLES_AUTORREGISTRO.map((r) => ({ valor: r, clave: r === 'Turista' ? 'Turista' : 'Prestador' })))

async function enviar() {
  errores.value = {}; general.value = ''
  enviando.value = true
  try {
    const r = await registrar({
      email: form.email, password: form.password, nombre: form.nombre, rol: form.rol,
      habeasDataAceptado: form.habeasData, esMayorDeEdad: form.mayorDeEdad,
    })
    const destino = rutaSegura(route.query.redirect)
    if (r.sesionIniciada) router.replace(destino)
    else router.replace({ name: 'login', query: { creada: '1', ...(route.query.redirect ? { redirect: destino } : {}) } })
  } catch (e) {
    if (!(e instanceof AuthError)) { general.value = textoDeError('generic', t, te); return }
    const r = repartirError(e)
    errores.value = Object.fromEntries(Object.entries(r.campos).map(([k, v]) => [k, textoDeError(v.codigo ?? e.code, t, te)]))
    if (r.general) general.value = textoDeError(r.general, t, te)
  } finally { enviando.value = false }
}
</script>

<template>
  <AuthShell :title="t('auth.register.title')" :lead="t('auth.register.lead')">
    <form class="flex flex-col gap-4" novalidate @submit.prevent="enviar">
      <AuthField id="nombre" v-model="form.nombre" :label="t('auth.register.name')" autocomplete="name" :error="errores.nombre" />
      <AuthField id="email" v-model="form.email" :label="t('auth.register.email')" type="email" autocomplete="username" inputmode="email" :error="errores.email" />
      <PasswordField id="password" v-model="form.password" :label="t('auth.register.password')" autocomplete="new-password" show-rules :error="errores.password" />

      <fieldset>
        <legend class="text-sm font-medium text-ink-control">{{ t('auth.register.role') }}</legend>
        <div class="mt-2 grid gap-2 sm:grid-cols-2">
          <label
            v-for="r in roles" :key="r.valor"
            class="flex cursor-pointer gap-3 rounded-xl border p-3 transition has-[:checked]:border-navy has-[:checked]:bg-navy/5 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-teal"
            :class="errores.rol ? 'border-danger' : 'border-border-input'"
          >
            <input v-model="form.rol" type="radio" name="rol" :value="r.valor" class="mt-1 accent-[#006798]" />
            <span>
              <span class="block text-sm font-semibold text-navy-darkest">{{ t(`auth.register.role${r.clave}`) }}</span>
              <span class="block text-[13px] leading-snug text-muted">{{ t(`auth.register.role${r.clave}Help`) }}</span>
            </span>
          </label>
        </div>
        <p v-if="errores.rol" class="mt-1 text-sm text-danger">{{ errores.rol }}</p>
      </fieldset>

      <div class="flex flex-col gap-2.5">
        <label class="flex cursor-pointer items-start gap-3 text-sm leading-snug text-ink-control">
          <input v-model="form.habeasData" type="checkbox" class="mt-0.5 size-4 accent-[#006798]" :aria-invalid="!!errores.habeasData" aria-describedby="habeas-error" />
          {{ t('auth.register.habeas') }}
        </label>
        <p v-if="errores.habeasData" id="habeas-error" class="-mt-1 text-sm text-danger">{{ errores.habeasData }}</p>
        <label class="flex cursor-pointer items-start gap-3 text-sm leading-snug text-ink-control">
          <input v-model="form.mayorDeEdad" type="checkbox" class="mt-0.5 size-4 accent-[#006798]" :aria-invalid="!!errores.mayorDeEdad" aria-describedby="adult-error" />
          {{ t('auth.register.adult') }}
        </label>
        <p v-if="errores.mayorDeEdad" id="adult-error" class="-mt-1 text-sm text-danger">{{ errores.mayorDeEdad }}</p>
      </div>

      <p v-if="general" class="rounded-xl bg-danger-bg px-4 py-3 text-sm text-danger" role="alert">{{ general }}</p>
      <p v-if="!queue.online" class="rounded-xl bg-warn-bg px-4 py-3 text-sm text-warn">{{ t('auth.register.needOnline') }}</p>

      <button type="submit" class="rounded-full bg-navy px-6 py-3.5 font-semibold text-white shadow-cta transition hover:bg-blue disabled:opacity-50" :disabled="enviando || !queue.online">
        {{ enviando ? t('auth.register.submitting') : t('auth.register.submit') }}
      </button>
    </form>

    <template #footer>
      {{ t('auth.register.haveAccount') }}
      <RouterLink :to="{ name: 'login', query: route.query.redirect ? { redirect: route.query.redirect } : {} }" class="font-semibold text-navy hover:text-teal">{{ t('auth.register.signIn') }}</RouterLink>
    </template>
  </AuthShell>
</template>
