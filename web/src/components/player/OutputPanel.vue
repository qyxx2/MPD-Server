<script setup lang="ts">
import { computed, inject, onUnmounted, ref, shallowRef, watch } from 'vue'
import { ApiError, type MutationIntent } from '../../types/api'
import { parseRestOutput } from '../../services/wire'
import { playerKey, derivePlayerFacts, outputMetadata } from './playerFacts'
import { playerRuntimeKey } from './playerActions'
const store = inject(playerKey)!
const runtime = inject(playerRuntimeKey, null)
const facts = computed(() => derivePlayerFacts(store.snapshot, store.writable))
const observed = computed(() => facts.value.output)
const summary = computed(() => facts.value.outputFreshness === 'unknown' ? 'DAC尚未确认' : facts.value.outputFreshness === 'stale' ? '最后确认 · DAC状态已过期' : observed.value?.status === 'ACTIVE' ? 'DAC已启用' : observed.value?.status === 'INACTIVE' ? 'DAC未启用' : 'DAC不可用')
const pending = ref(false), unknown = ref(false), feedback = ref(''), readError = ref('')
const intent = shallowRef<MutationIntent | null>(null)
let generation = 0
const preparing = computed(() => store.snapshot?.output.last_request?.status === 'PREPARING')
const available = computed(() => Boolean(runtime && store.writable && facts.value.outputFreshness === 'fresh' && observed.value?.status !== 'UNAVAILABLE'))
const locked = computed(() => !available.value || pending.value || unknown.value || preparing.value)
const serverRequestFeedback = computed(() => {
  const request = store.snapshot?.output.last_request
  return request?.status === 'PREPARING' ? '服务端最近输出请求 · 准备中' : request?.status === 'SWITCH_FAILED' ? `服务端最近输出请求失败 · ${request.error_code || ''} ${request.error_message || ''}` : ''
})
function retire() { generation++; pending.value = false; unknown.value = false; feedback.value = ''; readError.value = ''; intent.value = null }
watch(() => JSON.stringify([store.marker.epoch, store.marker.generation]), retire, { flush: 'sync' })
onUnmounted(retire)
async function execute(captured: MutationIntent) {
  if (!available.value || pending.value || !runtime) return
  const version = ++generation
  pending.value = true; unknown.value = false; readError.value = ''
  feedback.value = captured.payload && typeof captured.payload === 'object' && !Array.isArray(captured.payload) && captured.payload.enabled ? '正在启用 NAS DAC' : '正在停用 NAS DAC'
  try {
    const receipt = await runtime.api.send(captured, parseRestOutput)
    if (version !== generation) return
    // A terminal replay acknowledges this request; never install its states as observed output.
    const request = receipt.last_request
    feedback.value = request?.status === 'SWITCH_FAILED' ? `输出请求失败 · ${request.error_code || ''} ${request.error_message || ''}` : '此输出请求已确认'
    intent.value = null
  } catch (error) {
    if (version !== generation) return
    unknown.value = !(error instanceof ApiError) || error.kind !== 'http'
    feedback.value = error instanceof ApiError && error.kind === 'http' ? `输出请求失败 · ${error.code} · ${error.message}` : '输出请求结果未知 · 可用原请求重试'
    if (!unknown.value) intent.value = null
  }
  if (version !== generation) return
  try { await runtime.refresh() }
  catch { if (version === generation) readError.value = '输出状态读取失败 · 保留最后确认事实' }
  finally { if (version === generation) pending.value = false }
}
function act(enabled: boolean) {
  if (locked.value || !runtime) return
  intent.value = runtime.api.createIntent('PUT', '/api/system/output', { mode: 'NAS_DAC', enabled })
  void execute(intent.value)
}
function retry() { if (unknown.value && intent.value && !pending.value) void execute(intent.value) }
</script>
<template>
  <section class="output-panel" aria-label="音频输出" :aria-busy="pending">
    <div data-testid="confirmed-output" class="output-confirmed">
      <p class="label">NAS DAC · 确认事实</p><p>{{ summary }}</p>
      <p class="muted">{{ facts.outputFreshness === 'unknown' ? '参数未知' : outputMetadata(observed) }}</p>
      <p v-if="store.snapshot?.output_observation.error_message || observed?.error_message" class="warning">{{ store.snapshot?.output_observation.error_message || observed?.error_message }}</p>
    </div>
    <div class="output-buttons">
      <button aria-label="启用 NAS DAC" :disabled="locked || observed?.status === 'ACTIVE'" @click="act(true)">启用</button>
      <button aria-label="停用 NAS DAC" :disabled="locked || observed?.status === 'INACTIVE'" @click="act(false)">停用</button>
    </div>
    <p data-testid="output-request" role="status" aria-live="polite" class="diagnostic">{{ feedback }}</p>
    <p v-if="serverRequestFeedback" data-testid="server-output-request" role="status" aria-live="polite" class="diagnostic">{{ serverRequestFeedback }}</p>
    <p v-if="readError" role="status" class="warning">{{ readError }}</p>
    <button v-if="unknown" aria-label="重试输出请求" :disabled="!available || pending" @click="retry">重试原输出请求</button>
    <p class="muted">CLIENT_STREAM · 尚未支持</p>
  </section>
</template>
<style scoped>
.output-panel { margin-top: .25rem; border: 1px solid var(--subtle-border); border-radius: var(--radius-medium); background: rgba(14, 24, 39, .8); padding: .75rem; display: grid; gap: .4rem; overflow-wrap: anywhere; }
.output-confirmed { line-height: 1.6; font-size: .875rem; }
.output-buttons { display: flex; gap: .5rem; }
button { border: 1px solid var(--subtle-border); border-radius: var(--radius-small); padding: .25rem .75rem; color: var(--accent); background: transparent; }
button:disabled { opacity: .5; color: var(--text-muted); }
</style>
