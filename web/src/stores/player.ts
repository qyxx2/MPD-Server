import { readonly, shallowReactive } from 'vue'
import type { FullStateSnapshot, InvalidateFrame, Revisions } from '../types/api'

export interface ResourceMarker {
  readonly epoch: string | null
  readonly sequence: number
  readonly revisions: Readonly<Revisions>
  readonly generation: number
  readonly trusted: boolean
}
export interface ReadTiming {
  readonly epoch: string; readonly sequence: number; readonly observedAt: string | null
  readonly receivedAt: number; readonly requestedAt: number; readonly sampleAgeMs: number | null
}
export function createPlayerStore() {
  const state = shallowReactive({
    snapshot: null as FullStateSnapshot | null, writable: false,
    readTiming: null as ReadTiming | null,
    status: 'disconnected' as 'disconnected' | 'connecting' | 'ready' | 'error', error: null as unknown,
    marker: { epoch: null, sequence: 0, revisions: { library: 0, playlist: 0 }, generation: 0, trusted: false } as ResourceMarker,
  })
  let connection: number | null = null
  function marker(update: Partial<ResourceMarker>) { state.marker = freeze({ ...state.marker, ...update }) }
  function covers(snapshot: FullStateSnapshot) {
    const known = state.marker
    return snapshot.epoch === known.epoch && snapshot.sequence >= known.sequence &&
      snapshot.revisions.library >= known.revisions.library && snapshot.revisions.playlist >= known.revisions.playlist
  }
  function apply(snapshot: FullStateSnapshot) {
    if (!state.snapshot || snapshot.epoch !== state.snapshot.epoch || snapshot.sequence > state.snapshot.sequence) {
      state.snapshot = freeze(structuredClone(snapshot))
    }
    marker({ epoch: snapshot.epoch, sequence: snapshot.sequence, revisions: { ...snapshot.revisions } })
    state.error = null
  }
  const view = readonly(state)
  return {
    get snapshot() { return view.snapshot },
    get readTiming() { return view.readTiming },
    get writable() { return state.writable },
    get status() { return state.status },
    get error() { return state.error },
    get marker() { return view.marker },
    beginConnection(id: number) {
      connection = id; state.writable = false; state.status = 'connecting'
      marker({ trusted: false, generation: state.marker.generation + 1 })
    },
    acceptInitial(snapshot: FullStateSnapshot, id: number) {
      if (id !== connection) return false
      if (snapshot.epoch === state.marker.epoch && !covers(snapshot)) return false
      apply(snapshot); state.writable = true; state.status = 'ready'
      marker({ trusted: true })
      return true
    },
    acceptRefresh(snapshot: FullStateSnapshot, id: number, timing?: { receivedAt: number; roundTripMs: number }) {
      if (id !== connection) return 'obsolete' as const
      if (state.marker.epoch !== null && snapshot.epoch !== state.marker.epoch) return 'epoch-changed' as const
      if (state.marker.epoch !== null && !covers(snapshot)) return 'uncovered' as const
      apply(snapshot)
      if (timing) {
        // Same sequence may estimate age, but never replace canonical or its observed_at.
        const observedAt = state.snapshot?.playback_observation.observed_at ?? null
        const delta = observedAt ? Date.parse(snapshot.captured_at) - Date.parse(observedAt) : NaN
        const rtt = timing.roundTripMs
        state.readTiming = Object.freeze({ epoch: snapshot.epoch, sequence: snapshot.sequence, observedAt,
          receivedAt: timing.receivedAt, requestedAt: timing.receivedAt - rtt,
          sampleAgeMs: Number.isFinite(delta) && delta >= 0 && Number.isFinite(rtt) && rtt >= 0 ? delta + rtt : null })
      }
      return 'covered'  as const
    },
    invalidate(frame: InvalidateFrame, id: number) {
      if (id !== connection || frame.epoch !== state.marker.epoch) return false
      if (frame.sequence <= state.marker.sequence) return false
      marker({ sequence: frame.sequence, revisions: {
        library: Math.max(frame.revisions.library, state.marker.revisions.library),
        playlist: Math.max(frame.revisions.playlist, state.marker.revisions.playlist),
      } })
      return true
    },
    markReadError(error: unknown) { state.error = error },
    markDisconnected(error: unknown = null) {
      connection = null; state.writable = false; state.status = error ? 'error' : 'disconnected'; state.error = error
      marker({ trusted: false, generation: state.marker.generation + 1 })
    },
  }
}
function freeze<T>(value: T): T {
  if (value !== null && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value) }
  return value
}
export type PlayerStore = ReturnType<typeof createPlayerStore>
