import { afterEach, expect, it, vi } from 'vitest'
import fixture from '../fixtures/wire.json'
import { deferred, transport } from '../support/transport'
import { createApiClient } from '../../src/services/api'
import { createRealtimeClient, type RealtimeSocket } from '../../src/services/realtime'
import { createPlayerStore } from '../../src/stores/player'
import { createLibraryStore } from '../../src/stores/library'
import { createTaskActions } from '../../src/runtime/taskActions'

class Socket implements RealtimeSocket {
  listeners = new Map<string, Set<(event: { data?: unknown }) => void>>()
  closed = false
  addEventListener(type: string, listener: (event: { data?: unknown }) => void) {
    const set = this.listeners.get(type) ?? new Set(); set.add(listener); this.listeners.set(type, set)
  }
  removeEventListener(type: string, listener: (event: { data?: unknown }) => void) { this.listeners.get(type)?.delete(listener) }
  close() { this.closed = true }
  initial(sequence = 12, epoch = fixture.snapshot.epoch) {
    const state = { ...structuredClone(fixture.snapshot), sequence, epoch }
    this.listeners.get('message')?.forEach(listener => listener({ data: JSON.stringify({ type: 'snapshot', protocol_version: 1, sequence, epoch, state }) }))
  }
  disconnect() { this.listeners.get('close')?.forEach(listener => listener({})) }
}
function setup(...responses: Parameters<typeof transport>) {
  vi.useFakeTimers()
  const network = transport(...responses)
  const api = createApiClient({ fetch: network.fetch, origin: 'http://music.local' })
  const store = createPlayerStore(), sockets: Socket[] = []
  const client = createRealtimeClient({ api, store, clock: { setTimeout, clearTimeout, random: () => 0 }, socketFactory: () => { const socket = new Socket(); sockets.push(socket); return socket } })
  return { network, api, store, sockets, client }
}
const flush = async () => { for (let i = 0; i < 30; i++) await Promise.resolve() }
afterEach(() => vi.useRealTimers())

it('initial_snapshot_timeout_reports_and_reconnects', async () => {
  const h = setup()
  h.client.start()
  try {
    await vi.advanceTimersByTimeAsync(9999)
    expect(h.sockets[0]!.closed).toBe(false)
    await vi.advanceTimersByTimeAsync(1)
    expect(h.store.error).toMatchObject({ code: 'INITIAL_SNAPSHOT_TIMEOUT', message: '初始状态读取超时，正在重连' })
    expect(h.store.writable).toBe(false)
    expect(h.sockets[0]!.closed).toBe(true)
    expect([...h.sockets[0]!.listeners.values()].every(set => set.size === 0)).toBe(true)
    await vi.advanceTimersByTimeAsync(500)
    expect(h.sockets).toHaveLength(2)
    h.sockets[1]!.initial()
    expect(h.store.writable).toBe(true)
    expect(h.store.error).toBeNull()
  } finally { h.client.stop() }
  expect(vi.getTimerCount()).toBe(0)
})

it('get_timeout_ends_loading_and_retries', async () => {
  // Transport deliberately ignores abort; the client still must settle.
  const pending = deferred<Response>()
  const h = setup(pending.promise, Response.json({ name: 'Recovered' }))
  h.client.start(); h.sockets[0]!.initial(); h.sockets[0]!.disconnect()
  await vi.advanceTimersByTimeAsync(500)
  const library = createLibraryStore({ api: h.api, player: h.store, decode: value => value as { name: string } })
  let settled = false, error: unknown
  const reading = library.read('/api/library/songs').catch(value => { error = value }).finally(() => { settled = true })
  try {
    await flush()
    expect(library.entry('/api/library/songs').loading).toBe(true)
    await vi.advanceTimersByTimeAsync(10000)
    expect(settled).toBe(true)
    expect(error).toMatchObject({ code: 'READ_TIMEOUT', message: '资源读取超时，请重试' })
    expect(h.network.requests[0]!.init?.signal?.aborted).toBe(true)
    expect(library.entry('/api/library/songs')).toMatchObject({ loading: false, fresh: false })
    await reading
    await library.read('/api/library/songs')
    expect(library.entry('/api/library/songs')).toMatchObject({ data: { name: 'Recovered' }, loading: false, fresh: false, error: null })
    expect(h.store.writable).toBe(false)
    // This reconnect's initial also timed out during the resource read.
    // The second existing backoff is 1,000ms; both read budgets stay 10,000ms.
    await vi.advanceTimersByTimeAsync(1000)
    h.sockets.at(-1)!.initial()
    expect(h.store.writable).toBe(true)
    expect(h.network.requests.every(request => request.init?.method === 'GET')).toBe(true)
  } finally { library.stop(); h.client.stop() }
})

it('body_timeout_and_late_response_cannot_restore_baseline', async () => {
  const body = deferred<unknown>()
  // Real Response headers resolve immediately; its body is permanently pending
  // until after timeout and reconnection. No abort cooperation from this mock.
  const response = Response.json(fixture.snapshot)
  vi.spyOn(response, 'json').mockImplementation(() => body.promise)
  const h = setup(response, Response.json({ ...fixture.snapshot, sequence: 20 }))
  h.client.start(); h.sockets[0]!.initial()
  let settled = false, error: unknown
  const read = h.client.refresh().catch(value => { error = value }).finally(() => { settled = true })
  try {
    await flush()
    expect(h.network.requests).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(10000)
    expect(settled).toBe(true)
    expect(error).toMatchObject({ code: 'READ_TIMEOUT', message: '状态读取超时，请重试' })
    expect(h.store.snapshot?.sequence).toBe(12)
    expect(h.store.error).toMatchObject({ code: 'READ_TIMEOUT' })
    expect(h.network.requests[0]!.init?.signal?.aborted).toBe(true)
    await read
    h.sockets[0]!.disconnect()
    await vi.advanceTimersByTimeAsync(500)
    await h.client.refresh()
    expect(h.store.snapshot?.sequence).toBe(20)
    expect(h.store.writable).toBe(false)
    h.sockets[1]!.initial(20)
    body.resolve({ ...fixture.snapshot, sequence: 99 })
    await flush()
    expect(h.store.snapshot?.sequence).toBe(20)
    expect(h.store.writable).toBe(true)
  } finally { h.client.stop() }
  expect(vi.getTimerCount()).toBe(0)
})

it('success_stop_and_reconnect_clear_timeout_timers', async () => {
  const pending = deferred<Response>(), next = deferred<Response>()
  const h = setup(Response.json(fixture.snapshot), pending.promise, next.promise)
  h.client.start()
  try {
    expect(vi.getTimerCount()).toBe(1)
    h.sockets[0]!.initial()
    expect(vi.getTimerCount()).toBe(0)
    await h.client.refresh()
    expect(vi.getTimerCount()).toBe(0)
    const stopped = h.client.refresh()
    await flush()
    expect(vi.getTimerCount()).toBe(1)
    h.client.stop(); await stopped
    expect(h.network.requests[1]!.init?.signal?.aborted).toBe(true)
    expect(vi.getTimerCount()).toBe(0)
    h.client.start(); h.sockets[1]!.initial()
    const obsolete = h.client.refresh()
    await flush()
    h.sockets[1]!.disconnect(); await obsolete
    expect(h.network.requests[2]!.init?.signal?.aborted).toBe(true)
    expect(vi.getTimerCount()).toBe(1) // Only the existing reconnect backoff.
    await vi.advanceTimersByTimeAsync(500)
    h.sockets[2]!.initial()
    expect(vi.getTimerCount()).toBe(0)
    pending.resolve(Response.json({ ...fixture.snapshot, sequence: 90 }))
    next.resolve(Response.json({ ...fixture.snapshot, sequence: 99 }))
    await flush()
    expect(h.store.snapshot?.sequence).toBe(12)
    expect(h.store.error).toBeNull()
  } finally { h.client.stop() }
  expect(vi.getTimerCount()).toBe(0)
})

it('get_after_timeout_does_not_enable_mutations', async () => {
  const h = setup(deferred<Response>().promise, Response.json({ ...fixture.snapshot, sequence: 20 }))
  const tasks = createTaskActions({ api: h.api, player: h.store, refresh: h.client.refresh })
  h.client.start(); h.sockets[0]!.initial()
  const baseline = h.store.snapshot
  let error: unknown
  const timed = h.client.refresh().catch(value => { error = value })
  try {
    await flush(); await vi.advanceTimersByTimeAsync(10000)
    expect(error).toMatchObject({ code: 'READ_TIMEOUT' })
    await timed
    expect(h.store.snapshot).toBe(baseline)
    expect(h.store.writable).toBe(false)
    await vi.advanceTimersByTimeAsync(500)
    await h.client.refresh()
    expect(h.store.snapshot?.sequence).toBe(20)
    expect(h.store.writable).toBe(false)
    const intent = h.api.createIntent('POST', '/api/playback/next', undefined)
    await tasks.run(intent, () => undefined, async () => {})
    expect(h.network.requests.every(request => request.init?.method === 'GET')).toBe(true)
    expect(tasks.entries.value).toHaveLength(0)
    h.sockets[1]!.initial(20)
    expect(h.store.writable).toBe(true)
  } finally { tasks.dispose(); h.client.stop() }
})

it.each(['fetch', 'body'] as const)('never_settling_abort_ignored_%s_uses_one_total_budget', async stage => {
  vi.useFakeTimers()
  const headers = deferred<Response>(), body = deferred<unknown>()
  const response = Response.json({ name: 'late' })
  vi.spyOn(response, 'json').mockImplementation(() => body.promise)
  const network = transport(headers.promise)
  const api = createApiClient({ origin: 'http://music.local', fetch: network.fetch })
  let settled = false, failure: unknown
  const read = api.get('/api/library/songs', value => value).catch(error => { failure = error }).finally(() => { settled = true })
  await flush()
  await vi.advanceTimersByTimeAsync(7000)
  if (stage === 'body') { headers.resolve(response); await flush() }
  await vi.advanceTimersByTimeAsync(2999)
  expect(settled).toBe(false)
  await vi.advanceTimersByTimeAsync(1)
  expect(settled).toBe(true)
  expect(failure).toMatchObject({ code: 'READ_TIMEOUT', message: '资源读取超时，请重试' })
  expect(network.requests[0]!.init?.signal?.aborted).toBe(true)
  await read
  expect(vi.getTimerCount()).toBe(0)
  // Neither headers nor body is ever resolved after abort.
})

it('abort_rejection_cannot_replace_typed_read_timeout', async () => {
  vi.useFakeTimers()
  const api = createApiClient({ origin: 'http://music.local', fetch: (_input, init) => new Promise((_resolve, reject) => {
    init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
  }) })
  let failure: unknown
  const read = api.get('/api/state', value => value).catch(error => { failure = error })
  await vi.advanceTimersByTimeAsync(10000)
  expect(failure).toMatchObject({ code: 'READ_TIMEOUT', message: '状态读取超时，请重试' })
  await read
  expect(vi.getTimerCount()).toBe(0)
})

it.each(['network', 'json', 'http', 'decode'] as const)('terminal_%s_failure_clears_read_timer', async stage => {
  vi.useFakeTimers()
  const response = stage === 'json' ? new Response('{') : Response.json({}, { status: stage === 'http' ? 503 : 200 })
  const network = transport(stage === 'network' ? new Error('offline') : response)
  const api = createApiClient({ origin: 'http://music.local', fetch: network.fetch })
  await expect(api.get('/api/state', value => { if (stage === 'decode') throw new Error('invalid state'); return value })).rejects.toBeInstanceOf(Error)
  expect(vi.getTimerCount()).toBe(0)
  await vi.advanceTimersByTimeAsync(10000)
  expect(network.requests).toHaveLength(1)
})

it('injected_budgets_use_fixture_clock_and_dispose_old_initial', async () => {
  vi.useFakeTimers()
  const sockets: Socket[] = [], network = transport(deferred<Response>().promise)
  const clock = { setTimeout: vi.fn(setTimeout), clearTimeout: vi.fn(clearTimeout) }
  const api = createApiClient({ origin: 'http://music.local', fetch: network.fetch, clock, readTimeoutMs: 25 })
  const store = createPlayerStore()
  const client = createRealtimeClient({ api, store, clock: { ...clock, random: () => 0 }, initialSnapshotTimeoutMs: 40,
    socketFactory: () => { const socket = new Socket(); sockets.push(socket); return socket } })
  client.start()
  const late = [...sockets[0]!.listeners.get('message')!][0]!
  let failure: unknown
  const read = api.get('/api/state', value => value).catch(error => { failure = error })
  try {
    await vi.advanceTimersByTimeAsync(25)
    expect(failure).toMatchObject({ code: 'READ_TIMEOUT' })
    await read
    expect(store.error).toBeNull()
    await vi.advanceTimersByTimeAsync(15)
    expect(store.error).toMatchObject({ code: 'INITIAL_SNAPSHOT_TIMEOUT' })
    late({ data: JSON.stringify({ type: 'snapshot', protocol_version: 1, sequence: 12, epoch: fixture.snapshot.epoch, state: fixture.snapshot }) })
    expect(store.writable).toBe(false)
    await vi.advanceTimersByTimeAsync(500)
    sockets[1]!.initial()
    expect(store.writable).toBe(true)
    expect(clock.setTimeout.mock.calls.map(call => call[1])).toEqual([40, 25, 500, 40])
    expect(vi.getTimerCount()).toBe(0)
  } finally { client.stop() }
})

it('resource_timeout_ends_loading_and_uses_existing_notice_read', async () => {
  const { mount } = await import('@vue/test-utils')
  const { computed, defineComponent, h: render, provide } = await import('vue')
  const { libraryResourcesKey, createAppLibraryStore } = await import('../../src/stores/library')
  const { playerKey } = await import('../../src/components/player/playerFacts')
  const { noticeKey, createNoticeStore } = await import('../../src/stores/notices')
  const { useLibraryResource } = await import('../../src/components/library/libraryResources')
  const harness = setup(deferred<Response>().promise, Response.json({ items: [], count: 0 }))
  harness.client.start(); harness.sockets[0]!.initial()
  const library = createAppLibraryStore({ api: harness.api, player: harness.store }).resources
  const notices = createNoticeStore()
  const Probe = defineComponent({ setup() {
    useLibraryResource(computed(() => '/api/library/songs'), computed(() => '歌曲'))
    return () => null
  } })
  const wrapper = mount(defineComponent({ setup() {
    provide(playerKey, harness.store); provide(libraryResourcesKey, library); provide(noticeKey, notices)
    return () => render(Probe)
  } }))
  try {
    await flush()
    expect(notices.entries.value[0]?.busy).toBe(true)
    await vi.advanceTimersByTimeAsync(10000)
    expect(library.entry('/api/library/songs').loading).toBe(false)
    expect(notices.entries.value).toHaveLength(1)
    expect(notices.entries.value[0]).toMatchObject({ status: 'failed', busy: false, message: '歌曲 · 资源读取超时，请重试' })
    await notices.readUnfinished()
    expect(library.entry('/api/library/songs')).toMatchObject({ fresh: true, loading: false, error: null })
    expect(notices.entries.value).toHaveLength(0)
    expect(harness.network.requests.every(request => request.init?.method === 'GET')).toBe(true)
  } finally { wrapper.unmount(); library.stop(); harness.client.stop() }
  expect(vi.getTimerCount()).toBe(0)
})

it('generation_change_cannot_restart_a_timed_out_resource_budget', async () => {
  const h = setup(deferred<Response>().promise, deferred<Response>().promise)
  h.client.start(); h.sockets[0]!.initial()
  const library = createLibraryStore({ api: h.api, player: h.store, decode: value => value })
  let settled = false, failure: unknown
  const read = library.read('/api/library/songs').catch(error => { failure = error }).finally(() => { settled = true })
  try {
    await flush(); await vi.advanceTimersByTimeAsync(5000)
    h.sockets[0]!.disconnect()
    await vi.advanceTimersByTimeAsync(5000)
    expect(settled).toBe(true)
    expect(failure).toMatchObject({ code: 'READ_TIMEOUT' })
    expect(h.network.requests).toHaveLength(1)
    expect(library.entry('/api/library/songs')).toMatchObject({ loading: false, fresh: false, data: null, error: null })
    await read
  } finally { library.stop(); h.client.stop() }
})
