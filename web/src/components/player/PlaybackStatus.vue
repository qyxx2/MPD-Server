<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import type { PlayerActions } from './playerActions'
import type { NoticeStore } from '../../stores/notices'
const props = defineProps<{ actions?: PlayerActions; activities: NoticeStore }>()
const recent = computed(() => props.activities.recent())
const feedback = computed(() => recent.value.map(n => [n.description, n.resource, n.message].filter(Boolean).join(' · ')).join(' · '))
const busy = computed(() => props.activities.summary.value.busy)
const warning = computed(() => props.activities.summary.value.warning)
// One display clock lives in the persistent AppBar. History and recovery stay in the store.
const deadlines = new Map<string, { order: number; expires: number }>()
const now = ref(Date.now())
let expiryTimer: ReturnType<typeof setTimeout> | undefined
function scheduleExpiry() {
  clearTimeout(expiryTimer)
  now.value = Date.now()
  const next = Math.min(...[...deadlines.values()].map(n => n.expires).filter(t => t > now.value))
  if (Number.isFinite(next)) expiryTimer = setTimeout(scheduleExpiry, next - now.value)
}
watch(() => props.activities.entries.value, entries => {
  const ids = new Set(entries.map(n => n.id))
  for (const id of deadlines.keys()) if (!ids.has(id)) deadlines.delete(id)
  for (const notice of entries) {
    if (notice.status !== 'info' && notice.status !== 'success' || notice.level === 'warning') deadlines.delete(notice.id)
    else if (deadlines.get(notice.id)?.order !== notice.updatedOrder) {
      deadlines.set(notice.id, { order: notice.updatedOrder, expires: Date.now() + 5000 })
    }
  }
  scheduleExpiry()
}, { immediate: true, flush: 'sync' })
onUnmounted(() => clearTimeout(expiryTimer))
const information = computed(() => props.activities.entries.value.some(n => (deadlines.get(n.id)?.expires ?? 0) > now.value))
const focused = ref(false)
const expanded = ref(false)
const visible = computed(() => warning.value || busy.value || information.value || expanded.value || focused.value)
const toggleButton = ref<HTMLButtonElement | null>(null)
const details = ref<HTMLDivElement | null>(null)
async function toggle() { expanded.value = !expanded.value; await nextTick(); if (expanded.value) details.value?.querySelector<HTMLButtonElement>('button')?.focus(); else toggleButton.value?.focus() }
function close() { expanded.value = false; toggleButton.value?.focus() }
watch(() => [feedback.value, busy.value], () => { if (!feedback.value && !busy.value) expanded.value = false })
const label = (id: string, type: 'retry' | 'read') => id.startsWith('player-operation:') || ['connection', 'read', 'playback-status'].includes(id) ? type === 'retry' ? '重试原操作' : '重新读取状态' : type === 'retry' ? `重试操作 ${id}` : `重新读取 ${id}`
</script>
<template>
  <div class="playback-status" @keydown.esc="close()">
    <span data-testid="operation-status" role="status" aria-live="polite" class="status-description">{{ feedback }}<template v-if="activities.summary.value.hiddenUnresolved"> · 另有{{ activities.summary.value.hiddenUnresolved }}项未完成</template></span>
    <button ref="toggleButton" v-if="visible" type="button" class="status-toggle" :class="{ warning }" :aria-label="warning ? '查看活动异常' : busy ? '查看正在处理的活动' : '查看最近活动'" :aria-expanded="expanded" aria-controls="playback-status-details" @click="toggle()" @focus="focused = true" @blur="focused = false">
      <svg v-if="warning" class="status-warning" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3 22 21H2Z" /><path d="M12 9v5m0 3h.01" /></svg>
      <svg v-else-if="busy" class="status-spinner" viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="2" opacity=".25" /><path d="M12 4a8 8 0 0 1 8 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" /></svg>
      <svg v-else viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="8" /><path d="M12 7v6m0 4h.01" /></svg>
    </button>
    <div ref="details" role="dialog" aria-label="最近活动详情" v-show="expanded" id="playback-status-details" class="status-details" @keydown.esc="close()">
      <div v-for="notice in recent" :key="notice.id" :data-notice="notice.id" :data-status="notice.status" class="notice-entry">
        <p class="diagnostic"><span v-if="notice.description">{{ notice.description }} · </span><span v-if="notice.resource">{{ notice.resource }} · </span>{{ notice.message }}</p>
        <div v-if="notice.retry || notice.read" class="recovery-row"><button v-if="notice.retry" :disabled="!actions?.facts.value.writable || notice.busy" :aria-label="label(notice.id, 'retry')" @click="notice.retry()">重试原操作</button><button v-if="notice.read" :aria-label="label(notice.id, 'read')" :disabled="notice.busy" @click="notice.read()">重新读取</button></div>
      </div>
      <div v-if="activities.summary.value.hiddenUnresolved" class="activity-summary"><p>另有{{ activities.summary.value.hiddenUnresolved }}项未完成，完整记录见日志</p><button aria-label="重新读取未完成状态" @click="activities.readUnfinished()">重新读取未完成状态</button></div>
      <slot />
      <button type="button" class="details-close" aria-label="关闭播放状态详情" @click="close()">关闭</button>
    </div>
  </div>
</template>
<style scoped>
.playback-status { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); width: 32px; height: 32px; }
.status-description { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
.status-toggle { display: grid; place-items: center; width: 44px; height: 44px; min-width: 44px; min-height: 44px; transform: translate(-6px, -6px); padding: 0; border: 0; background: transparent; color: var(--accent); cursor: pointer; }
.status-toggle.warning { color: var(--status-warning); }
.status-spinner { animation: status-spin 1s linear infinite; }
@keyframes status-spin { to { transform: rotate(360deg); } }
.status-details { position: absolute; top: calc(100% + .5rem); left: 50%; transform: translateX(-50%); width: min(20rem, calc(100vw - 2rem)); max-height: calc(100dvh - 5rem); overflow-y: auto; overflow-wrap: anywhere; z-index: 10; padding: .625rem; font-size: .8125rem; line-height: 1.5; border: 1px solid var(--subtle-border); border-radius: var(--radius-small); background: var(--overlay-surface); box-shadow: 0 .5rem 1.5rem rgba(0, 0, 0, .3); }
.notice-entry + .notice-entry, .status-details > p + p { margin-top: .375rem; }
.recovery-row { display: flex; flex-wrap: wrap; gap: .375rem; margin-top: .375rem; }
.status-details button { border: 1px solid var(--subtle-border); border-radius: var(--radius-small); background: transparent; color: var(--text-primary); font-size: inherit; line-height: inherit; padding: .375rem .5rem; min-height: 44px; min-width: 44px; }
.status-details :deep(.last-business > p:not(.label)) { font-size: inherit; line-height: 1.5; }
.status-details :deep(.last-business > p + p) { margin-top: .375rem; }
.details-close { margin-top: .375rem; }
.app-shell[data-layout="landscape"] .status-toggle svg { width: 24px; height: 24px; }
@media (prefers-reduced-motion: reduce) { .status-spinner { animation: none; } }
</style>
