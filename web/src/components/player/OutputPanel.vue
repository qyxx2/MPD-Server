<script setup lang="ts">
import { computed, inject } from 'vue'
import { outputActionsKey } from '../settings/outputActions'
import { outputMetadata } from './playerFacts'
const actions = inject(outputActionsKey, null)
const facts = computed(() => actions?.facts.value)
const observed = computed(() => facts.value?.output)
const hasConfirmedState = computed(() => facts.value?.outputFreshness !== 'unknown' && (observed.value?.status === 'ACTIVE' || observed.value?.status === 'INACTIVE'))
const summary = computed(() => !facts.value || facts.value.outputFreshness === 'unknown' ? 'DAC尚未确认' : facts.value.outputFreshness === 'stale' ? '最后确认 · DAC状态已过期' : observed.value?.status === 'ACTIVE' ? 'DAC已启用' : observed.value?.status === 'INACTIVE' ? 'DAC未启用' : 'DAC不可用')
</script>
<template>
  <section class="settings-section" aria-label="音频输出">
    <h2>音频输出</h2>
    <div data-testid="confirmed-output">
      <div class="output-status-row"><p>NAS DAC · {{ summary }}</p><button data-output-switch class="output-switch" :role="hasConfirmedState ? 'switch' : 'button'" aria-label="NAS DAC 输出" :aria-checked="hasConfirmedState ? observed?.status === 'ACTIVE' : undefined" :disabled="!actions || actions.locked.value || !hasConfirmedState" @click="actions?.setEnabled(observed?.status !== 'ACTIVE')"><span class="output-switch-track" aria-hidden="true"><span class="output-switch-thumb" /></span></button></div>
      <p class="muted">{{ facts?.outputFreshness === 'unknown' ? '参数未知' : outputMetadata(observed ?? null) }}</p>
    </div>
    <button data-client-stream disabled>CLIENT_STREAM · 尚未支持</button>
  </section>
</template>
