<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { PlayerActions } from './playerActions'
const props = defineProps<{ actions?: PlayerActions; handoff?: boolean; statusFeedback?: string; notices?: readonly { id: string; message: string; busy?: boolean }[] }>()
const operation = computed(() => {
  const ui = props.actions?.ui
  if (!ui) return ''
  if (ui.unknown) return `结果未知 · ${ui.error}`
  if (ui.error) return ui.error
  if (ui.confirmed && ui.readFailed) return `操作已确认 · 状态未同步${ui.syncing ? ' · 正在同步进度（等待新观察）' : ''}`
  if (props.handoff) return `${ui.confirmed ? '操作已确认 · ' : ''}${ui.action === 'seek' ? '正在同步进度' : '正在同步'} · 展示上次确认数据`
  if (ui.confirmed && ui.syncing) return ui.action === 'seek' ? '操作已确认 · 正在同步进度' : '操作已确认 · 正在同步播放状态'
  return ''
})
const feedback = computed(() => [operation.value, props.statusFeedback, ...(props.notices ?? []).map(notice => notice.message)].filter(Boolean).join(' · '))
const busy = computed(() => props.actions?.ui.pending || props.actions?.ui.stopPending || props.actions?.ui.syncing || props.handoff || props.notices?.some(notice => notice.busy))
const warning = computed(() => props.actions?.ui.unknown || Boolean(props.actions?.ui.error) || props.actions?.ui.readFailed || Boolean(props.statusFeedback && !props.handoff) || props.notices?.some(notice => !notice.busy))
const expanded = ref(false)
watch(() => [feedback.value, busy.value], () => { if (!feedback.value && !busy.value) expanded.value = false })
</script>
<template>
  <div class="playback-status" @keydown.esc="expanded = false">
    <span data-testid="operation-status" role="status" aria-live="polite" class="status-description">{{ feedback }}</span>
    <button v-if="busy || feedback" type="button" class="status-toggle" :class="{ warning }" :aria-label="warning ? '查看播放操作异常' : busy ? '正在同步播放状态' : '查看播放状态'" :aria-expanded="expanded" aria-controls="playback-status-details" @click="expanded = !expanded">
      <svg v-if="busy && !warning" class="status-spinner" viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="2" opacity=".25" /><path d="M12 4a8 8 0 0 1 8 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" /></svg>
      <svg v-else viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="8" /><path d="M12 7v6m0 4h.01" /></svg>
    </button>
    <div v-show="expanded" id="playback-status-details" class="status-details" @keydown.esc="expanded = false">
      <p v-if="operation" :class="warning ? 'warning' : 'diagnostic'">{{ operation }}</p>
      <p v-if="statusFeedback" class="diagnostic">{{ statusFeedback }}</p>
      <p v-for="notice in notices" :key="notice.id" :data-notice="notice.id" class="diagnostic">{{ notice.message }}</p>
      <p v-if="!feedback" class="diagnostic">正在处理播放操作</p>
      <slot />
      <div v-if="actions && (warning || actions.ui.unknown || (actions.ui.confirmed && actions.ui.readFailed))" class="recovery-row"><button v-if="actions.ui.unknown" aria-label="重试原操作" :disabled="!actions.facts.value.writable || actions.ui.pending || actions.ui.stopPending" @click="actions.retry()">重试原操作</button><button aria-label="重新读取状态" @click="actions.refresh()">重新读取状态</button></div>
      <button type="button" class="details-close" aria-label="关闭播放状态详情" @click="expanded = false">关闭</button>
    </div>
  </div>
</template>
<style scoped>
.playback-status { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); width: 32px; height: 32px; }
.status-description { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
.status-toggle { display: grid; place-items: center; width: 32px; height: 32px; min-width: 32px; min-height: 32px; padding: 0; border: 0; background: transparent; color: var(--accent); cursor: pointer; }
.status-toggle.warning { color: var(--warning); }
.status-spinner { animation: status-spin 1s linear infinite; }
@keyframes status-spin { to { transform: rotate(360deg); } }
.status-details { position: absolute; top: calc(100% + .5rem); left: 50%; transform: translateX(-50%); width: min(20rem, calc(100vw - 2rem)); max-height: calc(100dvh - 5rem); overflow-y: auto; z-index: 10; padding: .75rem; border: 1px solid var(--subtle-border); border-radius: var(--radius-small); background: var(--overlay-surface); box-shadow: 0 .5rem 1.5rem rgba(0, 0, 0, .3); }
.status-details > p + p { margin-top: .5rem; }
.recovery-row { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .5rem; }
.status-details button { border: 1px solid var(--subtle-border); border-radius: var(--radius-small); background: transparent; color: var(--text-primary); }
.details-close { margin-top: .5rem; }
@media (prefers-reduced-motion: reduce) { .status-spinner { animation: none; } }
</style>
