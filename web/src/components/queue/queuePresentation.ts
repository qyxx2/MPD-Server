import type { DeepReadonly } from 'vue'
import type { FullStateSnapshot } from '../../types/api'
export function deriveQueue(snapshot: DeepReadonly<FullStateSnapshot> | null, writable = false) {
  const items = snapshot?.queue.items ?? []
  const current = items.find(item => item.position === 0) ?? null
  const observation = snapshot?.playback_observation
  const confirmed = Boolean(writable && current && observation?.freshness === 'fresh' &&
    observation.actual_freshness === 'fresh' && observation.matches_current === true &&
    observation.bound_queue_item_id === current.queue_item_id &&
    (observation.sync_status === 'CONFIRMED' || observation.sync_status === 'NO_CANDIDATES') &&
    (observation.actual_state === 'playing' || observation.actual_state === 'paused'))
  const pending = items.filter(item => item.position > 0).sort((a, b) => a.position - b.position)
  const manual = pending.filter(item => item.source === 'MANUAL')
  const next = manual.length ? manual : current && snapshot?.playback?.autoplay_enabled
    ? pending.filter(item => item.source === 'AUTOPLAY').slice(0, 1) : []
  return {
    current, confirmed,
    currentIcon: confirmed ? observation?.actual_state === 'paused' ? 'paused' : 'playing' : null,
    currentLabel: confirmed ? observation?.actual_state === 'paused' ? '已暂停' : '正在播放' : '业务当前',
    played: items.filter(item => item.position < 0).sort((a, b) => b.position - a.position),
    next,
  }
}
