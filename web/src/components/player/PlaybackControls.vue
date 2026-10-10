<script setup lang="ts">
import { computed } from 'vue'
import type { PlayerActions } from './playerActions'
const props = defineProps<{ actions: PlayerActions; handoff?: boolean; displayPrimary?: 'pause' | 'resume'; statusFeedback?: string }>()
const primary = computed(() => props.displayPrimary ?? (props.actions.facts.value.capabilities.pause ? 'pause' : 'resume'))
const label = computed(() => primary.value === 'pause' ? '暂停播放' : '继续播放')
</script>
<template>
  <section aria-label="播放控制" class="playback-controls" :aria-busy="actions.ui.pending || actions.ui.stopPending || actions.ui.syncing || handoff">
    <div class="transport-row">
      <button aria-label="上一首" :disabled="actions.locked || !actions.facts.value.capabilities.previous" @click="actions.act('previous')">|◀</button>
      <button class="primary" data-testid="primary-playback" :aria-label="label" :disabled="actions.locked || !actions.facts.value.capabilities[primary]" @click="actions.act(primary)"><span aria-hidden="true">{{ primary === 'pause' ? 'Ⅱ' : '▶' }}</span></button>
      <button aria-label="下一首" :disabled="actions.locked || !actions.facts.value.capabilities.next" @click="actions.act('next')">▶|</button>
    </div>
  </section>
</template>
<style scoped>
.transport-row { display: flex; align-items: center; justify-content: center; gap: .75rem; }
button { border: 1px solid var(--subtle-border); border-radius: 50%; background: var(--glass-surface, #182638); color: var(--text-primary); padding: .65rem; }
button:disabled { opacity: .4; cursor: default; }
.primary { width: 64px; height: 64px; color: #071320; background: var(--accent); font-size: 1.5rem; }
</style>
