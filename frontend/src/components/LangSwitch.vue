<script setup>
import { useI18n } from 'vue-i18n'

// Selector ES | EN. Lo usan la cinta superior, la barra fija y el menú móvil: el idioma es de toda la aplicación.
defineProps({ grande: { type: Boolean, default: false } })
const { locale } = useI18n()

function setLang(l) {
  locale.value = l
  document.documentElement.lang = l
  try { localStorage.setItem('lang', l) } catch { /* sin almacenamiento */ }
}
const idiomas = [['es', 'ES', 'Español'], ['en', 'EN', 'English']]
</script>

<template>
  <div role="group" aria-label="Idioma / Language" class="inline-flex items-center" :class="grande ? 'rounded-full border border-sand/40 bg-white p-0.5 shadow-card' : ''">
    <template v-for="([l, corto, largo], i) in idiomas" :key="l">
      <span v-if="!grande && i" class="mx-1 text-muted" aria-hidden="true">|</span>
      <button
        type="button" :aria-pressed="locale === l" :lang="l" :title="largo"
        :class="[
          grande ? 'min-w-9 rounded-full px-2.5 py-1 font-mono text-[12px] font-semibold transition' : '',
          grande ? (locale === l ? 'bg-navy text-white' : 'text-ink-control hover:text-navy') : (locale === l ? 'font-bold text-navy' : 'text-muted'),
        ]"
        @click="setLang(l)"
      >{{ corto }}</button>
    </template>
  </div>
</template>
