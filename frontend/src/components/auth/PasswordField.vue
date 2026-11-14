<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { evaluarPassword } from '../../domain/auth/rules'

// Contraseña con botón de mostrar/ocultar y, si se pide, la lista de requisitos que se va marcando (regla del dominio)
const props = defineProps({
  id: { type: String, required: true },
  label: { type: String, required: true },
  modelValue: { type: String, default: '' },
  autocomplete: { type: String, default: 'current-password' },
  error: String,
  showRules: Boolean,
})
defineEmits(['update:modelValue'])

const { t } = useI18n()
const visible = ref(false)
const reglas = computed(() => evaluarPassword(props.modelValue))
</script>

<template>
  <div>
    <label :for="id" class="block text-sm font-medium text-ink-control">{{ label }}</label>
    <div class="relative mt-1">
      <input
        :id="id" :type="visible ? 'text' : 'password'" :value="modelValue" :autocomplete="autocomplete"
        autocapitalize="off" spellcheck="false"
        :aria-invalid="!!error" :aria-describedby="[error ? `${id}-error` : '', showRules ? `${id}-reglas` : ''].filter(Boolean).join(' ') || undefined"
        class="w-full rounded-xl border bg-white py-3 pl-4 pr-12 text-[15px] text-ink outline-none transition focus:border-teal focus:shadow-[0_0_0_3px_rgba(93,154,146,.18)]"
        :class="error ? 'border-danger' : 'border-border-input'"
        @input="$emit('update:modelValue', $event.target.value)"
      />
      <button
        type="button" class="absolute inset-y-0 right-0 grid w-12 place-items-center text-muted hover:text-navy"
        :aria-label="visible ? t('auth.passwordRules.hide') : t('auth.passwordRules.show')" :aria-pressed="visible" @click="visible = !visible"
      >
        <svg v-if="!visible" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></svg>
        <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 3l18 18M10.6 6.2A9.8 9.8 0 0112 6c6.5 0 10 6 10 6a17 17 0 01-3.2 3.8M6.6 6.6A17 17 0 002 12s3.5 6 10 6a9.7 9.7 0 004.4-1" /></svg>
      </button>
    </div>
    <p v-if="error" :id="`${id}-error`" class="mt-1 text-sm text-danger">{{ error }}</p>
    <ul v-if="showRules" :id="`${id}-reglas`" class="mt-2 space-y-1 text-[13px]" :aria-label="t('auth.passwordRules.title')">
      <li v-for="[k, ok] in [['length', reglas.longitud], ['letter', reglas.letra], ['number', reglas.numero]]" :key="k" class="flex items-center gap-2" :class="ok ? 'text-ok' : 'text-muted'">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path v-if="ok" d="M5 12l5 5 9-10" /><circle v-else cx="12" cy="12" r="4" /></svg>
        {{ t(`auth.passwordRules.${k}`) }}
      </li>
    </ul>
  </div>
</template>
