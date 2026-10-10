import { watch } from 'vue'
import type { PlayerStore } from '../../stores/player'
import { derivePlayerFacts } from './playerFacts'

// A display estimate only. No commands, canonical writes, or device/browser wall-clock subtraction.
export function createPlayerClock(store: PlayerStore, now: () => number = () => performance.now()) {
  let visible = true, awaitingRead = false, foregroundAt = -Infinity, frozen: number | null = null
  let key: string | null = null, startedAt: number | null = null, expiresAt = 0, leased = false
  let base: number | null = null, timingVersion: object | null = null
  function sampleKey() {
    const s = store.snapshot, o = s?.playback_observation
    return s && o ? JSON.stringify([s.epoch, o.bound_queue_item_id, o.control_target?.token, o.actual_current?.entry_id, o.observed_at]) : null
  }
  function calibrate() {
    const s = store.snapshot, o = s?.playback_observation
    const nextKey = sampleKey()
    if (nextKey !== key) { key = nextKey; startedAt = null; expiresAt = 0; leased = false }
    base = derivePlayerFacts(s, store.writable).position
    const t = store.readTiming
    if (!visible || !s || !o || !t || t === timingVersion || t.epoch !== s.epoch || t.sequence !== s.sequence || t.observedAt !== o.observed_at) return
    timingVersion = t
    if (t.requestedAt < foregroundAt) return
    awaitingRead = false
    const age = t.sampleAgeMs
    if (age === null || !Number.isFinite(age) || age < 0 || !Number.isFinite(t.receivedAt)) { expiresAt = 0; return }
    const deadline = t.receivedAt + Math.max(0, 6000 - age)
    if (!leased) { leased = true; expiresAt = deadline }
    else expiresAt = Math.min(expiresAt, deadline) // The same sample cannot acquire a new lease.
    if (startedAt === null) startedAt = t.receivedAt
  }
  const dispose = watch(() => [store.snapshot, store.writable, store.readTiming], calibrate, { immediate: true, flush: 'sync' })
  function position(): number | null {
    if (!visible) return frozen
    const facts = derivePlayerFacts(store.snapshot, store.writable)
    if (facts.position === null) return null
    const o = store.snapshot?.playback_observation
    let value = base ?? facts.position
    if (!awaitingRead && facts.bound && o?.actual_state === 'playing' && startedAt !== null) {
      value += Math.max(0, Math.min(now(), expiresAt) - startedAt) / 1000
    }
    return facts.duration !== null && facts.duration > 0 ? Math.min(value, facts.duration) : value
  }
  return {
    position, dispose,
    needsRead: () => awaitingRead,
    setVisible(value: boolean) {
      if (value === visible) return
      if (!value) frozen = position()
      visible = value
      if (value) { awaitingRead = true; foregroundAt = now(); startedAt = null; frozen = null }
    },
  }
}
export type PlayerClock = ReturnType<typeof createPlayerClock>
