<script setup lang="ts">
import { computed } from 'vue'
import type { PlayerActions } from './playerActions'
import { formatTime } from './playerFacts'
const props = defineProps<{ actions?: PlayerActions; position: number | null; duration: number | null }>()
// Submitted seek is a labelled UI proposal, never a canonical playback position.
const position = computed(() => props.actions?.ui.draft ?? props.actions?.ui.seekPreview?.seconds ?? props.position)
const duration = computed(() => props.actions?.ui.seekPreview?.duration ?? props.duration)
const editKeys = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End', 'PageUp', 'PageDown']
function keydown(event: KeyboardEvent) {
  if (event.key === 'Escape') { event.preventDefault(); props.actions?.cancelDraft() }
  else if (editKeys.includes(event.key) && props.actions?.ui.draft === null) props.actions.beginSeek()
}
function keyup(event: KeyboardEvent) { if (editKeys.includes(event.key)) void props.actions?.releaseSeek() }
function input(event: Event) { props.actions?.preview(Number((event.target as HTMLInputElement).value)) }
</script>
<template>
  <div data-testid="progress" class="progress-control">
    <input type="range" aria-label="播放进度" min="0" :max="duration ?? 0" step="1" :value="position ?? 0"
      :disabled="!actions?.facts.value.capabilities.seek || actions.locked"
      :aria-valuetext="formatTime(position)" @pointerdown="actions?.beginSeek()" @input="input"
      @keydown="keydown" @keyup="keyup" @blur="actions?.releaseSeek()" @pointerup="actions?.releaseSeek()" @pointercancel="actions?.cancelDraft()" />
    <div class="progress-readout"><span>{{ actions?.ui.draft !== null && actions ? '预览位置' : actions?.ui.seekPreview ? '待确认位置' : '观察位置' }} {{ formatTime(position) }}</span><span>时长 {{ formatTime(duration) }}</span></div>

  </div>
</template>
<style scoped>
input { width: 100%; min-height: 44px; accent-color: var(--accent); }
input:disabled { opacity: .4; }
</style>
