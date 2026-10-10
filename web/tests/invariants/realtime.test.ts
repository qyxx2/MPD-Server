import { afterEach, describe, expect, it, vi } from 'vitest'
import fixture from '../fixtures/wire.json'
import { deferred, transport } from '../support/transport'
import { createApiClient } from '../../src/services/api'
import { createRealtimeClient, type RealtimeSocket } from '../../src/services/realtime'
import { createPlayerStore } from '../../src/stores/player'

const snapshot = (sequence = 1, epoch = 'one', library = 1, playlist = 1) => ({
  ...structuredClone(fixture.snapshot), epoch, sequence, revisions: { library, playlist },
})
class Socket implements RealtimeSocket {
  listeners = new Map<string, Set<(event: { data?: unknown }) => void>>()
  closed = false
  addEventListener(type: string, listener: (event: { data?: unknown }) => void) {
    const set = this.listeners.get(type) ?? new Set(); set.add(listener); this.listeners.set(type, set)
  }
  removeEventListener(type: string, listener: (event: { data?: unknown }) => void) { this.listeners.get(type)?.delete(listener) }
  close() { this.closed = true }
  emit(type: string, value?: unknown) { this.listeners.get(type)?.forEach(listener => listener({ data: JSON.stringify(value) })) }
  initial(sequence = 1, epoch = 'one', library = 1, playlist = 1) {
    this.emit('message', { type: 'snapshot', protocol_version: 1, epoch, sequence, state: snapshot(sequence, epoch, library, playlist) })
  }
  invalidate(sequence: number, library = 1, playlist = 1, epoch = 'one') {
    this.emit('message', { type: 'invalidate', protocol_version: 1, epoch, sequence, domains: ['library', 'playlist'], revisions: { library, playlist } })
  }
}
function setup(...responses: Parameters<typeof transport>) {
  const network = transport(...responses)
  const api = createApiClient({ fetch: network.fetch, origin: 'http://music.local' })
  const store = createPlayerStore()
  const sockets: Socket[] = []
  const clock = { setTimeout, clearTimeout, random: () => 0 }
  const client = createRealtimeClient({ api, store, clock, socketFactory: () => { const socket = new Socket(); sockets.push(socket); return socket } })
  return { network, api, store, sockets, client }
}
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve() }
afterEach(() => vi.useRealTimers())

describe('REST / WebSocket → canonical state', () => {
  it('late GET cannot replace a newer connection baseline', async () => {
    vi.useFakeTimers()
    const old = deferred<Response>()
    const h = setup(old.promise)
    h.client.start(); h.sockets[0]!.initial()
    const reading = h.client.refresh()
    await flush()
    expect(h.network.requests).toHaveLength(1)
    h.sockets[0]!.emit('close')
    vi.advanceTimersByTime(500)
    h.sockets[1]!.initial(9, 'two')
    old.resolve(Response.json(snapshot(8)))
    await reading
    expect(h.store.snapshot?.epoch).toBe('two')
    expect(h.store.snapshot?.sequence).toBe(9)
    expect(h.store.writable).toBe(true)
    expect(h.network.requests.every(r => r.init?.method === 'GET')).toBe(true)
    h.client.stop()
  })
})

it('same epoch new connection rejects old GET and restores writes only on initial', async () => {
  vi.useFakeTimers()
  const old = deferred<Response>()
  const h = setup(old.promise, Response.json(snapshot(5)))
  h.client.start(); h.sockets[0]!.initial(3)
  const reading = h.client.refresh()
  await flush()
  h.sockets[0]!.emit('close')
  expect(h.store.writable).toBe(false)
  vi.advanceTimersByTime(500)
  await h.client.refresh()
  expect(h.store.snapshot?.sequence).toBe(5)
  expect(h.store.writable).toBe(false)
  h.sockets[1]!.initial(5)
  old.resolve(Response.json(snapshot(99))); await reading
  expect(h.store.snapshot?.sequence).toBe(5)
  expect(h.store.writable).toBe(true)
  h.client.stop()
})
it('same epoch initial cannot regress sequence or known revision watermarks', () => {
  vi.useFakeTimers()
  const h = setup()
  h.client.start(); h.sockets[0]!.initial(9, 'one', 8)
  h.sockets[0]!.emit('close'); vi.advanceTimersByTime(500)
  h.sockets[1]!.initial(8, 'one', 7)
  expect(h.store.snapshot?.sequence).toBe(9)
  expect(h.store.writable).toBe(false)
  expect(h.sockets[1]!.closed).toBe(true)
  h.client.stop()
})
it('cross epoch GET requires new socket confirmation without replacing canonical', async () => {
  vi.useFakeTimers()
  const h = setup(Response.json(snapshot(100, 'two')))
  h.client.start(); h.sockets[0]!.initial(3)
  await h.client.refresh()
  expect(h.store.snapshot?.epoch).toBe('one')
  expect(h.store.writable).toBe(false)
  expect(h.sockets[0]!.closed).toBe(true)
  vi.advanceTimersByTime(500); h.sockets[1]!.initial(1, 'two')
  expect(h.store.snapshot?.sequence).toBe(1)
  expect(h.store.writable).toBe(true)
  h.client.stop()
})
it('duplicate and old sequence are ignored without replacing canonical or issuing reads', async () => {
  const h = setup(Response.json(snapshot(5)))
  h.client.start(); h.sockets[0]!.initial(5)
  const accepted = h.store.snapshot
  await h.client.refresh()
  expect(h.store.snapshot).toBe(accepted)
  h.sockets[0]!.invalidate(4); h.sockets[0]!.invalidate(5)
  await flush()
  expect(h.network.requests).toHaveLength(1)
  h.client.stop()
})
it('in-flight GET cannot clear a higher invalidation and revisions advance immediately', async () => {
  const first = deferred<Response>(); const second = deferred<Response>()
  const h = setup(first.promise, second.promise)
  h.client.start(); h.sockets[0]!.initial()
  h.sockets[0]!.invalidate(2, 2)
  const reading = h.client.refresh()
  await flush()
  h.sockets[0]!.invalidate(4, 3)
  expect(h.store.marker.revisions.library).toBe(3)
  expect(h.network.requests).toHaveLength(1)
  first.resolve(Response.json(snapshot(2, 'one', 2))); await flush()
  expect(h.store.snapshot?.sequence).toBe(1)
  expect(h.network.requests).toHaveLength(2)
  second.resolve(Response.json(snapshot(4, 'one', 3))); await reading
  expect(h.store.snapshot?.sequence).toBe(4)
  expect(h.store.marker.sequence).toBe(4)
  expect(h.store.error).toBeNull()
  h.client.stop()
})
it('failed refresh preserves invalidation obligation and error until read retry covers it', async () => {
  vi.useFakeTimers()
  const second = deferred<Response>()
  const h = setup(new Error('offline'), second.promise)
  h.client.start(); h.sockets[0]!.initial()
  h.sockets[0]!.invalidate(3, 3)
  await flush()
  expect(h.store.snapshot?.sequence).toBe(1)
  expect(h.store.marker.revisions.library).toBe(3)
  expect(h.store.error).not.toBeNull()
  vi.advanceTimersByTime(500)
  await flush()
  expect(h.network.requests).toHaveLength(2)
  second.resolve(Response.json(snapshot(3, 'one', 3))); await flush()
  expect(h.store.snapshot?.sequence).toBe(3)
  expect(h.store.error).toBeNull()
  expect(h.network.requests.every(r => r.init?.method === 'GET')).toBe(true)
  h.client.stop()
})
it.each(['broken', 'invalidate-first', 'socket-error'])('initial %s fails closed and cleans listeners', async mode => {
  vi.useFakeTimers()
  const h = setup()
  h.client.start()
  if (mode === 'broken') h.sockets[0]!.emit('message', { type: 'snapshot', protocol_version: 99 })
  else if (mode === 'invalidate-first') h.sockets[0]!.invalidate(2)
  else h.sockets[0]!.emit('error')
  expect(h.store.writable).toBe(false)
  expect(h.store.status).toBe('error')
  expect(h.sockets[0]!.closed).toBe(true)
  expect([...h.sockets[0]!.listeners.values()].every(set => set.size === 0)).toBe(true)
  h.client.stop(); vi.advanceTimersByTime(20000)
  expect(h.sockets).toHaveLength(1)
})
it('bounded reconnect backoff resets on initial; start and stop do not duplicate listeners', () => {
  vi.useFakeTimers()
  const h = setup()
  h.client.start(); h.client.start()
  expect(h.sockets).toHaveLength(1)
  for (const delay of [500, 1000, 2000, 4000, 8000, 8000]) {
    h.sockets.at(-1)!.emit('close')
    const count = h.sockets.length
    vi.advanceTimersByTime(delay - 1); expect(h.sockets).toHaveLength(count)
    vi.advanceTimersByTime(1); expect(h.sockets).toHaveLength(count + 1)
  }
  h.sockets.at(-1)!.initial(); h.sockets.at(-1)!.emit('close')
  const count = h.sockets.length
  vi.advanceTimersByTime(500); expect(h.sockets).toHaveLength(count + 1)
  h.client.stop(); h.client.stop(); vi.advanceTimersByTime(50000)
  expect(h.sockets).toHaveLength(count + 1)
  expect(h.sockets.every(socket => socket.closed && [...socket.listeners.values()].every(set => set.size === 0))).toBe(true)
})

it('same epoch refresh cannot regress revision or sequence and retries without future notifications', async () => {
  vi.useFakeTimers()
  const h = setup(Response.json(snapshot(2, 'one', 1)), Response.json(snapshot(3, 'one', 3)))
  h.client.start(); h.sockets[0]!.initial(1, 'one', 2)
  h.sockets[0]!.invalidate(3, 3)
  await flush()
  expect(h.store.snapshot?.sequence).toBe(1)
  vi.advanceTimersByTime(500); await flush()
  expect(h.store.snapshot?.sequence).toBe(3)
  expect(h.store.snapshot?.revisions.library).toBe(3)
  h.client.stop()
})
it('stop prevents pending GET writes and stale socket callbacks; restart has one fresh listener set', async () => {
  const pending = deferred<Response>()
  const h = setup(pending.promise)
  h.client.start(); h.sockets[0]!.initial()
  const callback = [...h.sockets[0]!.listeners.get('message')!][0]!
  const read = h.client.refresh(); await flush()
  h.client.stop(); h.client.start(); h.sockets[1]!.initial(8, 'two')
  callback({ data: JSON.stringify({ type: 'snapshot', protocol_version: 1, epoch: 'one', sequence: 99, state: snapshot(99) }) })
  pending.resolve(Response.json(snapshot(99))); await read
  expect(h.store.snapshot?.epoch).toBe('two')
  expect(h.store.snapshot?.sequence).toBe(8)
  expect(h.sockets[1]!.listeners.get('message')!.size).toBe(1)
  expect(Object.isFrozen(h.store.snapshot?.queue.items)).toBe(true)
  h.client.stop()
})
it('reconnect jitter is capped at twenty percent', () => {
  vi.useFakeTimers()
  const store = createPlayerStore(); const sockets: Socket[] = []
  const api = createApiClient({ fetch: transport().fetch, origin: 'https://music.local' })
  const client = createRealtimeClient({ api, store, socketFactory: () => { const socket = new Socket(); sockets.push(socket); return socket }, clock: { setTimeout, clearTimeout, random: () => 1 } })
  client.start(); sockets[0]!.emit('close')
  vi.advanceTimersByTime(599); expect(sockets).toHaveLength(1)
  vi.advanceTimersByTime(1); expect(sockets).toHaveLength(2)
  client.stop()
})
it('untrusted GET can populate read-only display before initial but does not unlock writes', async () => {
  const h = setup(Response.json(snapshot(3)))
  h.client.start(); await h.client.refresh()
  expect(h.store.snapshot?.sequence).toBe(3)
  expect(h.store.writable).toBe(false)
  expect(h.store.marker.trusted).toBe(false)
  h.sockets[0]!.initial(3)
  expect(h.store.writable).toBe(true)
  h.client.stop()
})
