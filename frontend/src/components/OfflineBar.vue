<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { queue, discard, retry } from '../lib/offlineQueue'
import { useCatalog } from '../lib/useCatalog'

const { t, d } = useI18n()
const { updatedAt } = useCatalog()
const open = ref(false)

const count = computed(() => queue.items.length)
const visible = computed(() => !queue.online || count.value > 0 || queue.syncing)
const stamp = computed(() => updatedAt.value
  ? d(updatedAt.value, { dateStyle: 'medium', timeStyle: 'short' })
  : t('offline.never'))

</script>

<template>
  <div v-if="visible" class="relative z-40" role="status" aria-live="polite">
    <div v-if="visible" class="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 px-[clamp(16px,3vw,32px)] py-2 text-[13px]" :class="queue.online ? 'bg-ok-bg text-ok' : 'bg-navy-darkest text-white'">
      <span v-if="!queue.online" class="flex items-center gap-2 font-medium">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M3 3l18 18M8.5 8.5A7 7 0 005 12M16 12a4 4 0 00-1.5-3M12 18h.01M2 8a14 14 0 013-2M12 5a14 14 0 019 3" /></svg>
        {{ t('offline.banner') }}
      </span>
      <span v-else-if="queue.syncing" class="font-medium">{{ t('offline.syncing') }}</span>
      <span class="font-mono text-[11px] opacity-80">{{ t('offline.updated') }}: {{ stamp }}</span>
      <button v-if="count" type="button" class="rounded-full border border-current px-3 py-0.5 font-mono text-[11px] font-semibold" @click="open = !open">
        {{ t('offline.pendingN', { n: count }) }}
      </button>
    </div>

    <div v-if="open" class="mx-auto my-3 max-w-xl rounded-card border border-sand/30 bg-white p-4 shadow-elevated">
      <div class="flex items-center justify-between">
        <h2 class="text-sm font-semibold text-navy-darkest">{{ t('offline.panel') }}</h2>
        <button v-if="open" type="button" class="text-xs text-muted hover:text-navy" @click="open = false">{{ t('offline.close') }}</button>
      </div>
      <p v-if="!count" class="mt-2 text-sm text-muted">{{ t('offline.empty') }}</p>
      <ul v-else class="mt-3 flex flex-col gap-2">
        <li v-for="i in queue.items" :key="i.id" class="flex items-center justify-between gap-3 rounded-xl border border-border-input px-3 py-2">
          <div class="min-w-0">
            <p class="truncate text-sm font-medium text-ink">{{ i.label }}</p>
            <p class="font-mono text-[11px]" :class="i.status === 'pending' ? 'text-muted' : 'text-danger'">{{ t(`offline.status.${i.status}`) }}</p>
          </div>
          <div class="flex shrink-0 gap-2 text-xs">
            <button v-if="i.status !== 'pending'" type="button" class="font-semibold text-navy" @click="retry(i.id)">{{ t('offline.retry') }}</button>
            <button type="button" class="text-muted hover:text-danger" @click="discard(i.id)">{{ t('offline.discard') }}</button>
          </div>
        </li>
      </ul>

    </div>
  </div>
</template>
