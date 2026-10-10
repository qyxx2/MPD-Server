import type { createApiClient } from './api'
import { parseRealtimeFrame, parseSnapshot, WireError } from './wire'
import type { PlayerStore } from '../stores/player'

export interface RealtimeSocket {
  addEventListener(type: string, listener: (event: { data?: unknown }) => void): void
  removeEventListener(type: string, listener: (event: { data?: unknown }) => void): void
  close(): void
}
export interface RealtimeClock {
  setTimeout(callback: () => void, ms: number): ReturnType<typeof setTimeout>
  clearTimeout(timer: ReturnType<typeof setTimeout>): void
  random(): number
}
export function createRealtimeClient(options: {
  api: ReturnType<typeof createApiClient>; store: PlayerStore
  now?: () => number; socketFactory: (url: string) => RealtimeSocket; clock: RealtimeClock
}) {
  const { api, store, clock } = options
  let running = false
  let generation = 0
  let dispose: (() => void) | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let readTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempt = 0
  let readAttempt = 0
  let flight: { id: number; promise: Promise<void> } | null = null
  const delay = (attempt: number) => Math.min(500 * 2 ** Math.min(attempt, 4), 8000) * (1 + Math.max(0, Math.min(clock.random(), 1)) * 0.2)
  function cancelRead() { if (readTimer !== null) clock.clearTimeout(readTimer); readTimer = null }
  function disconnect(error: unknown = null) {
    ++generation
    dispose?.(); dispose = null; flight = null; cancelRead()
    store.markDisconnected(error)
    if (running && reconnectTimer === null) {
      reconnectTimer = clock.setTimeout(() => { reconnectTimer = null; connect() }, delay(reconnectAttempt++))
    }
  }
  function connect() {
    const id = ++generation
    store.beginConnection(id)
    let socket: RealtimeSocket
    try { socket = options.socketFactory(api.realtimeUrl) }
    catch (error) { disconnect(error); return }
    let initial = false
    const message = (event: { data?: unknown }) => {
      if (!running || id !== generation) return
      try {
        const frame = parseRealtimeFrame(JSON.parse(String(event.data)))
        if (!initial) {
          if (frame.type !== 'snapshot' || !store.acceptInitial(frame.state, id)) throw new WireError('Initial snapshot required at current watermark')
          initial = true; reconnectAttempt = 0; readAttempt = 0
        } else {
          if (frame.type !== 'invalidate' || frame.epoch !== store.marker.epoch) throw new WireError('Invalid live frame or epoch')
          if (store.invalidate(frame, id)) void refresh().catch(() => {})
        }
      } catch (error) { disconnect(error) }
    }
    const close = () => { if (running && id === generation) disconnect() }
    const error = () => { if (running && id === generation) disconnect(new Error('Realtime connection failed')) }
    socket.addEventListener('message', message); socket.addEventListener('close', close); socket.addEventListener('error', error)
    dispose = () => {
      socket.removeEventListener('message', message); socket.removeEventListener('close', close); socket.removeEventListener('error', error)
      socket.close()
    }
  }
  function retryRead(id: number) {
    if (!running || id !== generation || readTimer !== null) return
    readTimer = clock.setTimeout(() => { readTimer = null; void refresh().catch(() => {}) }, delay(readAttempt++))
  }
  function refresh(): Promise<void> {
    if (!running || dispose === null) return Promise.resolve()
    const id = generation
    if (flight?.id === id) return flight.promise
    cancelRead()
    // A microtask starts the read only after the flight is installed (including synchronous errors).
    const promise = Promise.resolve().then(async () => {
      while (running && id === generation) {
        const startedSequence = store.marker.sequence
        try {
          const now = options.now ?? (() => performance.now())
          const startedAt = now()
          const snapshot = await api.get('/api/state', parseSnapshot)
          const receivedAt = now()
          if (!running || id !== generation) return
          const result = store.acceptRefresh(snapshot, id, { receivedAt, roundTripMs: receivedAt - startedAt })
          if (result === 'epoch-changed') { disconnect(new WireError('Epoch needs socket confirmation')); return }
          if (result === 'covered') { readAttempt = 0; return }
          // A higher notification during the read requires another read, even with no future event.
          if (store.marker.sequence > startedSequence) continue
          retryRead(id); return
        } catch (error) {
          if (!running || id !== generation) return
          store.markReadError(error); retryRead(id)
          throw error
        }
      }
    }).finally(() => { if (flight?.id === id) flight = null })
    flight = { id, promise }
    return promise
  }
  return {
    start() { if (running) return; running = true; connect() },
    stop() {
      running = false; ++generation
      if (reconnectTimer !== null) clock.clearTimeout(reconnectTimer)
      reconnectTimer = null; cancelRead(); dispose?.(); dispose = null; flight = null
      reconnectAttempt = 0; readAttempt = 0; store.markDisconnected()
    },
    refresh,
  }
}
