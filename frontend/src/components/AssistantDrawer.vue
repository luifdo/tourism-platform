<script setup>
import { useI18n } from 'vue-i18n'
import { assistantOpen as isOpen } from '../lib/assistant'

const { t } = useI18n()
</script>

<template>
  <div class="fixed right-[clamp(16px,2.5vw,32px)] z-[60] flex flex-col items-end gap-3.5" style="bottom: calc(env(safe-area-inset-bottom) + clamp(16px, 2.5vw, 28px))">
    <section
      v-if="isOpen"
      class="flex max-h-[min(560px,calc(100vh-140px))] w-[min(380px,calc(100vw-32px))] flex-col overflow-hidden rounded-panel bg-white/95 shadow-[0_30px_70px_-20px_rgba(0,103,152,.6)] backdrop-blur-xl"
      role="dialog" :aria-label="t('assistant.title')"
    >
      <header class="flex items-center justify-between bg-navy-darkest px-5 py-4 text-white">
        <div>
          <p class="font-semibold">{{ t('assistant.title') }}</p>
          <p class="mt-0.5 font-mono text-[10px] tracking-[.08em] text-[#a9ddd4]">{{ t('assistant.note') }}</p>
        </div>
        <button type="button" class="grid size-8 place-items-center rounded-full bg-white/10 text-lg hover:bg-white/25" :aria-label="t('assistant.close')" @click="isOpen = false">×</button>
      </header>
      <div class="flex flex-col gap-3.5 overflow-auto bg-[#EAF4F9] px-5 py-4">
        <p class="self-end rounded-[16px_16px_4px_16px] bg-navy px-3.5 py-2.5 text-sm text-white">{{ t('assistant.q') }}</p>
        <div class="flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
          <span class="text-[10px] tracking-widest text-teal-hover">{{ t('assistant.tools') }}</span>
          <span class="rounded-full border border-border-input bg-white px-2.5 py-0.5 text-ink-control">catalog.buscar</span>
          <span class="rounded-full border border-border-input bg-white px-2.5 py-0.5 text-ink-control">bookings.disponibilidad</span>
        </div>
        <div class="rounded-card border border-[#d7e8f0] bg-white p-3.5 shadow-card">
          <p class="font-mono text-[10px] uppercase tracking-[.12em] text-teal">{{ t('assistant.rec') }}</p>
          <p class="mt-1 font-semibold">{{ t('assistant.recName') }}</p>
          <p class="mt-2 text-[13px] leading-snug text-ink-control"><b>{{ t('assistant.why') }}</b> {{ t('assistant.whyBody') }}</p>
          <a href="#catalogo" class="mt-2.5 inline-block text-[13px] font-medium text-navy">{{ t('assistant.view') }}</a>
        </div>
      </div>
      <form class="flex gap-2.5 bg-white p-3" @submit.prevent>
        <input type="text" :placeholder="t('assistant.ph')" class="flex-1 rounded-xl bg-[#EAF4F9] px-3.5 py-2.5 text-sm outline-none" />
        <button type="submit" class="rounded-full bg-navy px-5 text-sm font-medium text-white">{{ t('assistant.send') }}</button>
      </form>
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
