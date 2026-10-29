<script setup>
import { useI18n } from 'vue-i18n'
import { queue } from '../lib/offlineQueue'
import { assistantOpen } from '../lib/assistant'

const { t } = useI18n()
</script>

<template>
  <section id="compromiso" class="bg-cream px-[clamp(20px,6vw,96px)] py-[clamp(56px,8vw,100px)]">
    <div class="mx-auto grid max-w-[1200px] gap-8 rounded-panel border border-sand/30 bg-white p-[clamp(24px,4vw,48px)] shadow-elevated lg:grid-cols-[1.5fr_1fr]">
      <div>
        <p class="kicker">{{ t('ethics.kicker') }}</p>
        <h2 class="mt-3 text-[clamp(28px,3.4vw,42px)] font-bold leading-[1.12] tracking-[-.02em] text-navy-darkest text-balance">{{ t('ethics.title') }}</h2>
        <p class="mt-4 leading-relaxed text-muted">{{ t('ethics.body') }}</p>
        <div class="mt-7 grid gap-5 sm:grid-cols-2">
          <div class="flex gap-3">
            <svg class="mt-0.5 shrink-0 text-teal" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M8.5 12l2.5 2.5 4.5-5" /></svg>
            <div><p class="text-sm font-semibold text-navy-darkest">{{ t('ethics.offlineT') }}</p><p class="mt-1 text-sm leading-snug text-muted">{{ t('ethics.offlineB') }}</p></div>
          </div>
          <div class="flex gap-3">
            <svg class="mt-0.5 shrink-0 text-teal" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M8.5 12l2.5 2.5 4.5-5" /></svg>
            <div><p class="text-sm font-semibold text-navy-darkest">{{ t('ethics.dataT') }}</p><p class="mt-1 text-sm leading-snug text-muted">{{ t('ethics.dataB') }}</p></div>
          </div>
        </div>
        <RouterLink
          :to="{ name: 'home', hash: '#catalogo' }"
          class="mt-8 inline-block rounded-full bg-navy px-7 py-3.5 font-medium text-white shadow-cta transition hover:-translate-y-0.5 hover:bg-blue"
          :class="{ 'pointer-events-none opacity-50': !queue.online }"
          :aria-disabled="!queue.online" :tabindex="queue.online ? 0 : -1"
        >{{ t('ethics.cta') }}</RouterLink>
        <p v-if="!queue.online" class="mt-2 text-sm text-muted">{{ t('offline.needsOnline') }}</p>
      </div>

      <div class="flex flex-col items-center justify-center rounded-card border border-sand/30 bg-cream p-7 text-center">
        <span class="grid size-14 place-items-center rounded-full bg-navy text-white">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="8" width="16" height="11" rx="3" /><path d="M12 8V5M9 13h.01M15 13h.01M9 16h6" /></svg>
        </span>
        <h3 class="mt-4 font-semibold text-navy-darkest">{{ t('ethics.askT') }}</h3>
        <p class="mt-2 text-sm leading-snug text-muted">{{ t('ethics.askB') }}</p>
        <button type="button" class="mt-5 w-full rounded-full bg-navy px-5 py-3 text-sm font-medium text-white shadow-cta transition hover:bg-blue" @click="assistantOpen = true">{{ t('ethics.askCta') }}</button>
      </div>
    </div>
  </section>
</template>
