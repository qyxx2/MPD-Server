import { computed, reactive, watch, type InjectionKey } from 'vue'
import type { createApiClient } from '../../services/api'
import { parsePlaybackState } from '../../services/wire'
import type { PlayerStore } from '../../stores/player'
import type { JsonValue, MutationIntent } from '../../types/api'
import { ApiError } from '../../types/api'
import { derivePlayerFacts } from './playerFacts'
export interface PlayerRuntime { api: ReturnType<typeof createApiClient>; refresh(): Promise<void> }
export const playerRuntimeKey: InjectionKey<PlayerRuntime> = Symbol('player-runtime')
export function controlIdentity(store: PlayerStore) {
  const s = store.snapshot, o = s?.playback_observation, t = o?.control_target
  return s ? JSON.stringify([s.epoch, store.marker.generation, o?.bound_queue_item_id, t?.queue_item_id, t?.token, o?.actual_current?.entry_id]) : null
}
// Used only to retire an interaction when the canonical business current changes;
// never to certify actual playback, enable controls, or create a control target.
function pendingScope(store: PlayerStore) {
  const s = store.snapshot
  return JSON.stringify([s?.epoch, store.marker.generation, s?.playback?.song_id,
    s?.playback?.playback_context_id, s?.queue.items.find(item => item.position === 0)?.queue_item_id])
}
function observationUnknown(store: PlayerStore) {
  const o = store.snapshot?.playback_observation
  return o?.freshness === 'unknown' && o.actual_freshness === 'unknown' &&
    o.actual_state === null && o.actual_current === null && o.bound_queue_item_id === null && o.control_target === null &&
    o.sync_status === 'UNBOUND' && !o.reconciliation_required && !o.error_code && !o.error_message
}
type Action = 'pause' | 'resume' | 'next' | 'previous' | 'seek' | 'stop'
type SeekPreview = { seconds: number; duration: number }
export function createPlayerActions(store: PlayerStore, runtime: PlayerRuntime) {
  const ui = reactive({ draft: null as number | null, seekPreview: null as SeekPreview | null, pending: false, stopPending: false, syncing: false, error: '', unknown: false, confirmed: false, readFailed: false, action: null as Action | null })
  const facts = computed(() => derivePlayerFacts(store.snapshot, store.writable))
  let draftIdentity: string | null = null
  let version = 0, stopVersion = 0, primaryScope = ''
  let retry: { intent: MutationIntent; action: Action; identity: string | null; version: number; preview: SeekPreview | null } | null = null
  let waiting: { identity: string; scope: string; updatedAt: number } | null = null
  function cancelDraft() { ui.draft = null; draftIdentity = null }
  function revoke() { ++version; cancelDraft(); ui.seekPreview = null; waiting = null; retry = null; ui.pending = false; ui.syncing = false; ui.unknown = false; ui.confirmed = false; ui.readFailed = false; ui.error = '' }
  function converge() {
    if (!waiting) return
    const o = store.snapshot?.playback_observation
    if (observationUnknown(store) && pendingScope(store) === waiting.scope && store.writable) return
    if (controlIdentity(store) !== waiting.identity || !store.writable || facts.value.stale) { waiting = null; ui.syncing = false; ui.seekPreview = null; return }
    if (facts.value.bound && o?.observed_at && Date.parse(o.observed_at) >= waiting.updatedAt) { waiting = null; ui.syncing = false; ui.seekPreview = null }
  }
  const dispose = watch(() => [controlIdentity(store), store.writable, store.snapshot, store.marker.generation, pendingScope(store)] as const, (value, old) => {
    if (value[0] !== old[0] || value[4] !== old[4] || !value[1]) {
      if (value[1] && observationUnknown(store) && pendingScope(store) === primaryScope && (ui.pending || ui.confirmed)) cancelDraft()
      else if (value[1] && value[4] === old[4] && waiting && controlIdentity(store) === waiting.identity) cancelDraft()
      else revoke()
    }
    if (value[3] !== old[3] || !value[1]) { ++stopVersion; ui.stopPending = false }
    if (facts.value.stale) ui.seekPreview = null
    if (ui.seekPreview && !facts.value.bound && !observationUnknown(store)) revoke()
    converge()
  }, { flush: 'sync' })
  async function read() {
    try { await runtime.refresh(); ui.readFailed = Boolean(store.error) }
    catch { ui.readFailed = true }
    converge()
  }
  async function send(intent: MutationIntent, action: Action, identity: string | null, serial: number) {
    const stopping = action === 'stop'
    const valid = () => stopping ? serial === stopVersion : serial === version && (identity === controlIdentity(store) || (observationUnknown(store) && pendingScope(store) === primaryScope))
    try {
      const receipt = await runtime.api.send(intent, value => value === null ? null : parsePlaybackState(value))
      if (valid()) {
        retry = null; ui.unknown = false; ui.confirmed = true
        if (action === 'seek' && receipt && identity) {
          waiting = { identity, scope: primaryScope, updatedAt: Date.parse(receipt.updated_at) }; ui.syncing = true; converge()
        }
      }
      await read()
    } catch (error) {
      if (valid()) {
        ui.error = error instanceof ApiError ? error.code : String(error)
        // A non-terminal transport/wire failure can have happened after the server committed.
        ui.unknown = !(error instanceof ApiError) || error.kind !== 'http'
        retry = ui.unknown ? { intent, action, identity, version: serial, preview: ui.seekPreview } : null
        ui.seekPreview = null
      }
      if (error instanceof ApiError && error.kind === 'http') await read()
    } finally {
      if (valid()) { if (stopping) ui.stopPending = false; else ui.pending = false; if (!ui.syncing) ui.seekPreview = null }
    }
  }
  function act(action: Action, seconds?: number) {
    if (!store.writable) return Promise.resolve()
    if (action === 'stop') {
      if (ui.stopPending) return Promise.resolve()
      revoke(); ui.action = 'stop'; ui.stopPending = true
      return send(runtime.api.createIntent('POST', '/api/playback/stop', undefined), action, null, ++stopVersion)
    }
    if (ui.pending || ui.stopPending || ui.syncing || ui.unknown || !facts.value.capabilities[action]) return Promise.resolve()
    const target = store.snapshot?.playback_observation.control_target
    const payload: JsonValue | undefined = action === 'resume' && target ? { target: { ...target } }
      : action === 'seek' && target ? { seconds: seconds!, target: { ...target } } : undefined
    primaryScope = pendingScope(store)
    ui.seekPreview = action === 'seek' && seconds !== undefined && facts.value.duration !== null ? { seconds, duration: facts.value.duration } : null
    ui.action = action; ui.pending = true; ui.confirmed = false; ui.readFailed = false; ui.error = ''; ui.unknown = false
    return send(runtime.api.createIntent('POST', `/api/playback/${action}`, payload), action, controlIdentity(store), ++version)
  }
  return {
    ui, facts, dispose() { dispose(); revoke(); ++stopVersion; ui.stopPending = false },
    get locked() { return ui.pending || ui.stopPending || ui.syncing || ui.unknown },
    beginSeek() { if (!facts.value.capabilities.seek || this.locked) return; draftIdentity = controlIdentity(store); ui.draft = facts.value.position ?? 0 },
    preview(seconds: number) { if (draftIdentity && ui.draft !== null && Number.isFinite(seconds)) ui.draft = Math.max(0, Math.min(seconds, facts.value.duration!)) },
    cancelDraft,
    releaseSeek() {
      if (ui.draft === null || draftIdentity !== controlIdentity(store) || !store.writable) { cancelDraft(); return Promise.resolve() }
      const seconds = ui.draft; cancelDraft(); return act('seek', seconds)
    },
    act,
    retry() {
      if (!retry || !store.writable || ui.pending || ui.stopPending) return Promise.resolve()
      const old = retry
      if (old.action !== 'stop' && old.identity !== controlIdentity(store)) { revoke(); return Promise.resolve() }
      ui.unknown = false; ui.error = ''
      ui.seekPreview = facts.value.capabilities.seek ? old.preview : null
      if (old.action === 'stop') ui.stopPending = true; else ui.pending = true
      return send(old.intent, old.action, old.identity, old.version)
    },
    refresh: read,
  }
}
export type PlayerActions = ReturnType<typeof createPlayerActions>
