import { readonly, ref, watch, type InjectionKey } from 'vue'
import type { PlayerStore } from './player'
export function createQueueUi(player: PlayerStore) {
  const expanded = ref(0)
  let baseline: { epoch: string; context: string | null; stop: number | null } | null = null
  let previousPlayed: string[] = []
  const dispose = watch(() => player.snapshot, snapshot => {
    if (!snapshot) return
    const played = snapshot.queue.items.filter(item => item.position < 0).sort((a, b) => b.position - a.position).map(item => item.queue_item_id)
    const oldestRevealed = previousPlayed[Math.min(expanded.value, previousPlayed.length) - 1]
    if (oldestRevealed && played.includes(oldestRevealed)) expanded.value = played.indexOf(oldestRevealed) + 1
    previousPlayed = played
    const context = snapshot.playback?.playback_context_id ?? null
    const generation = snapshot.explicit_stop_generation
    if (baseline && (snapshot.epoch !== baseline.epoch || context !== baseline.context ||
      (generation !== null && baseline.stop !== null && generation > baseline.stop))) expanded.value = 0
    baseline = { epoch: snapshot.epoch, context, stop: generation ?? (snapshot.epoch === baseline?.epoch ? baseline.stop : null) }
  }, { immediate: true, flush: 'sync' })
  return { expandedCount: readonly(expanded), enter() { expanded.value = 0 }, reveal() { expanded.value = Math.min(expanded.value + 1, previousPlayed.length) }, dispose }
}
export type QueueUi = ReturnType<typeof createQueueUi>
export const queueUiKey: InjectionKey<QueueUi> = Symbol('queue-ui')
