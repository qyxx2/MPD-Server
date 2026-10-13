import { computed, watch, type InjectionKey } from 'vue'
import type { PlayerStore } from '../../stores/player'
import type { PlayerRuntime } from '../player/playerActions'
import type { TaskActions } from '../../runtime/taskActions'
import type { createNoticeStore } from '../../stores/notices'
import { derivePlayerFacts } from '../player/playerFacts'
import { parseRestOutput } from '../../services/wire'
export function createOutputActions(player: PlayerStore, runtime: PlayerRuntime, tasks: TaskActions, notices: ReturnType<typeof createNoticeStore>, playerLocked: () => boolean) {
  const facts = computed(() => derivePlayerFacts(player.snapshot, player.writable))
  const locked = computed(() => !player.writable || facts.value.outputFreshness !== 'fresh' || facts.value.output?.status === 'UNAVAILABLE' || !facts.value.output || playerLocked() || Boolean(runtime.mutationLocked?.()) || player.snapshot?.output.last_request?.status === 'PREPARING')
  const stop = watch(() => player.snapshot, () => {
    const request = player.snapshot?.output.last_request
    if (request?.status === 'PREPARING' || request?.status === 'SWITCH_FAILED') notices.set({ id: 'output-server-request', scope: 'output', message: request.status === 'PREPARING' ? '输出请求 · 准备中' : `输出请求 · ${request.error_code ?? ''} ${request.error_message ?? ''}`, busy: request.status === 'PREPARING', read: runtime.refresh })
    else notices.remove('output-server-request')
  }, { immediate: true })
  return { facts, locked, setEnabled(enabled: boolean) {
    if (locked.value || facts.value.output?.status === (enabled ? 'ACTIVE' : 'INACTIVE')) return Promise.resolve()
    const intent = runtime.api.createIntent('PUT', '/api/system/output', { mode: 'NAS_DAC', enabled })
    return tasks.run(intent, parseRestOutput, async () => {}, enabled ? '启用 NAS DAC' : '停用 NAS DAC')
  }, dispose() { stop(); notices.remove('output-server-request') } }
}
export type OutputActions = ReturnType<typeof createOutputActions>
export const outputActionsKey: InjectionKey<OutputActions> = Symbol('output-actions')
