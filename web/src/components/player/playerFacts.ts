import type { InjectionKey } from 'vue'
import type { PlayerStore } from '../../stores/player'

export const playerKey: InjectionKey<PlayerStore> = Symbol('player')
type Snapshot = PlayerStore['snapshot']
const diagnostics = {
  CONFIRMED: '已确认', UNBOUND: '实际播放未绑定', EXTERNAL_DRIFT: '实际播放与业务状态不一致',
  UNCONFIRMED_STOP: '外部停止尚未确认', SYNC_FAILED: '播放同步失败', NO_CANDIDATES: '无候选歌曲',
}
export function derivePlayerFacts(snapshot: Snapshot, writable: boolean) {
  const observation = snapshot?.playback_observation
  const actualFresh = writable && observation?.actual_freshness === 'fresh'
  const fresh = actualFresh && observation?.freshness === 'fresh'
  const bound = fresh && observation?.matches_current === true && observation.bound_queue_item_id !== null &&
    (observation.sync_status === 'CONFIRMED' || observation.sync_status === 'NO_CANDIDATES')
  const current = snapshot?.current_song ?? null
  const active = bound && (observation?.actual_state === 'playing' || observation?.actual_state === 'paused')
  const song = active ? current : null
  const actualState = observation?.actual_state
  const stateLabel = actualState === 'playing' ? '正在播放' : actualState === 'paused' ? '已暂停' : actualState === 'stopped' ? '已停止' : '实际状态未知'
  const stale = !writable || observation?.freshness === 'stale' || observation?.actual_freshness === 'stale'
  const output = snapshot?.output.states.find(state => state.mode === 'NAS_DAC') ?? null
  const outputKnown = Boolean(output && snapshot?.output_observation.observed_at) && snapshot?.output_observation.freshness !== 'unknown'
  const outputFreshness = !outputKnown ? 'unknown' : !writable || snapshot?.output_observation.freshness === 'stale' || output?.stale === true ? 'stale' : 'fresh'
  const actualStale = !writable || observation?.actual_freshness === 'stale'
  const target = bound ? observation?.control_target ?? null : null
  const currentItem = bound ? snapshot?.queue.items.find(item => item.queue_item_id === observation?.bound_queue_item_id) : null
  return {
    song, lastSong: song ? null : current,
    title: song?.title || observation?.actual_current?.uri || '实际歌曲未知',
    stateLabel: `${actualStale ? '最后观察（已过期）· ' : !actualFresh ? '未确认 · ' : ''}${stateLabel}`,
    diagnostic: observation ? diagnostics[observation.sync_status] : '等待完整状态',
    stale, writable, bound: Boolean(bound),
    position: active ? observation?.position_seconds ?? null : null,
    duration: active ? observation?.duration_seconds ?? null : null,
    output, outputFreshness,
    // UI capability only; W4 owns dispatch/pending and the backend revalidates every intent.
    capabilities: {
      pause: Boolean(active && actualState === 'playing'),
      resume: Boolean(active && actualState === 'paused' && target),
      seek: Boolean(active && target && (observation?.duration_seconds ?? 0) > 0),
      next: Boolean(active && currentItem && snapshot?.queue.items.some(item => item.position > currentItem.position)),
      previous: Boolean(active && currentItem && snapshot?.queue.items.some(item => item.position < currentItem.position)),
      stop: writable,
    },
  }
}
export type PlayerFacts = ReturnType<typeof derivePlayerFacts>
export function formatTime(value: number | null) {
  if (value === null) return '未知'
  const seconds = Math.floor(value)
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}
export function sourceMetadata(song: PlayerFacts['song']) {
  return [song?.codec, song?.bit_depth == null ? null : `${song.bit_depth} bit`,
    song?.sample_rate_hz == null ? null : `${song.sample_rate_hz / 1000} kHz`,
    song?.channel_count == null ? null : `${song.channel_count} 声道`].filter(Boolean).join(' · ') || '未知'
}
export function outputMetadata(output: PlayerFacts['output']) {
  return [output?.format, output?.bit_depth == null ? null : `${output.bit_depth} bit`,
    output?.sample_rate == null ? null : `${output.sample_rate / 1000} kHz`,
    output?.channels == null ? null : `${output.channels} 声道`].filter(Boolean).join(' · ') || '参数未知'
}
