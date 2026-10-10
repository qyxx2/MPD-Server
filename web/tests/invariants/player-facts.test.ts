import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import fixture from '../fixtures/wire.json'
import { createPlayerStore } from '../../src/stores/player'
import { createApiClient } from '../../src/services/api'
import { createRealtimeClient, type RealtimeSocket } from '../../src/services/realtime'
import { parseSnapshot } from '../../src/services/wire'
import AppShell from '../../src/components/layout/AppShell.vue'
import PlayerView from '../../src/views/PlayerView.vue'

// Real decoder → realtime → store → shell → Player; only the socket/network boundary is injected.
class Socket implements RealtimeSocket {
  listeners = new Map<string, Set<(event: { data?: unknown }) => void>>()
  addEventListener(type: string, listener: (event: { data?: unknown }) => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set())
    this.listeners.get(type)!.add(listener)
  }
  removeEventListener(type: string, listener: (event: { data?: unknown }) => void) { this.listeners.get(type)?.delete(listener) }
  close() {}
  snapshot(value: unknown) {
    const state = parseSnapshot(value)
    this.listeners.get('message')?.forEach(fn => fn({ data: JSON.stringify({ type: 'snapshot', protocol_version: 1, epoch: state.epoch, sequence: state.sequence, state }) }))
  }
}
const wrappers: VueWrapper[] = []
afterEach(() => { wrappers.splice(0).forEach(wrapper => wrapper.unmount()) })
function page(value: unknown = structuredClone(fixture.snapshot)) {
  const store = createPlayerStore()
  const socket = new Socket()
  const api = createApiClient({ origin: 'http://localhost', fetch: async () => { throw new Error('Unexpected HTTP') } })
  const realtime = createRealtimeClient({ api, store, socketFactory: () => socket, clock: { setTimeout, clearTimeout, random: () => 0 } })
  const wrapper = mount(defineComponent({ render: () => h(AppShell, { store, realtime }, { default: () => h(PlayerView) }) }))
  wrappers.push(wrapper)
  socket.snapshot(value)
  return { wrapper, store, socket }
}
describe('Player facts relationship', () => {
  it('unbound actual never labels the persisted song as now playing', async () => {
    const state = structuredClone(fixture.snapshot)
    Object.assign(state.playback_observation, {
      actual_state: 'playing', actual_current: { entry_id: 99, uri: 'external/stranger.flac', position: 0 },
      bound_queue_item_id: null, control_target: null, sync_status: 'UNBOUND', matches_current: false,
      position_seconds: null, reconciliation_required: true,
    })
    const { wrapper, store } = page(state)
    await flushPromises()
    expect(wrapper.get('[data-testid="actual-identity"]').text()).toContain('external/stranger.flac')
    expect(wrapper.get('[data-testid="actual-identity"]').text()).not.toContain('长标题 / Song A')
    expect(wrapper.get('[data-testid="last-business"]').text()).toContain('长标题 / Song A')
    expect(wrapper.get('[data-testid="last-business"]').text()).toContain('最后业务歌曲')
    expect(wrapper.text()).toContain('未绑定')
    expect(store.snapshot?.current_song?.title).toBe('长标题 / Song A')
  })
})

// These catch falsely confirmed identities/progress and source values labelled as output.
describe('degraded and confirmed representation', () => {
  it.each(['UNBOUND', 'EXTERNAL_DRIFT', 'UNCONFIRMED_STOP', 'SYNC_FAILED'] as const)('%s keeps actual and business facts separate even when matches_current is true', async sync_status => {
    const value = structuredClone(fixture.snapshot)
    value.playback_observation.sync_status = sync_status
    const { wrapper } = page(value)
    await flushPromises()
    expect(wrapper.get('[data-testid="last-business"]').text()).toContain('长标题 / Song A')
    expect(wrapper.get('[data-testid="actual-identity"]').text()).not.toContain('长标题 / Song A')
    expect(wrapper.get('[data-testid="progress"]').text()).not.toContain('0:37')
  })
  it('unknown actual and missing fields never become zero or a queue-derived Context', async () => {
    const value = structuredClone(fixture.empty_snapshot)
    const { wrapper } = page(value)
    await flushPromises()
    expect(wrapper.text()).toContain('实际歌曲未知')
    expect(wrapper.get('[data-testid="progress"]').text()).toContain('未知')
    expect(wrapper.text()).not.toContain('0:00')
    expect(wrapper.text()).not.toContain('context-a')
  })
  it('stale observation and disconnected baseline never retain a confirmed Now Playing label', async () => {
    const value = structuredClone(fixture.snapshot)
    value.playback_observation.freshness = 'stale'
    const { wrapper, store } = page(value)
    await flushPromises()
    expect(wrapper.get('[data-testid="actual-identity"]').text()).not.toContain('长标题 / Song A')
    expect(wrapper.text()).toContain('过期')
    const fresh = structuredClone(fixture.snapshot); fresh.sequence++
    store.acceptRefresh(parseSnapshot(fresh), 1)
    store.markDisconnected()
    await flushPromises()
    expect(wrapper.text()).toContain('只读')
    expect(wrapper.get('[data-testid="last-business"]').text()).toContain('长标题 / Song A')
  })
  it('NO_CANDIDATES still identifies matching current and preserves observed progress', async () => {
    const value = structuredClone(fixture.snapshot)
    Object.assign(value.playback_observation, { sync_status: 'NO_CANDIDATES', actual_state: 'playing' })
    const { wrapper } = page(value)
    await flushPromises()
    expect(wrapper.get('[data-testid="actual-identity"]').text()).toContain('长标题 / Song A')
    expect(wrapper.get('[data-testid="actual-identity"]').text()).not.toContain('正在播放')
    expect(wrapper.text()).toContain('无候选')
    expect(wrapper.get('[data-testid="progress"]').text()).toContain('0:37')
  })
  it('confirmed STOPPED shows only the last business song', async () => {
    const value = structuredClone(fixture.snapshot)
    value.playback.state = 'STOPPED'
    value.playback_observation.actual_state = 'stopped'
    const { wrapper } = page(value)
    await flushPromises()
    expect(wrapper.text()).toContain('已停止')
    expect(wrapper.get('[data-testid="last-business"]').text()).toContain('长标题 / Song A')
  })
  it('source metadata is separate from observed output and unavailable media stays recognizable', async () => {
    const value = structuredClone(fixture.snapshot)
    Object.assign(value.current_song, { codec: 'FLAC', bit_depth: 16, sample_rate_hz: 44100, availability_status: 'MISSING' })
    const { wrapper } = page(value)
    await flushPromises()
    expect(wrapper.get('[data-testid="source-metadata"]').text()).toContain('44.1 kHz')
    expect(wrapper.get('[data-testid="source-metadata"]').text()).toContain('16 bit')
    expect(wrapper.get('[data-testid="output-fact"]').text()).toBe('DAC已启用')
    expect(wrapper.get('[data-testid="output-fact"]').attributes('title')).toContain('96 kHz')
    expect(wrapper.get('[data-testid="output-fact"]').text()).not.toContain('44.1')
    expect(wrapper.text()).toContain('文件缺失')
    expect(wrapper.get('[data-testid="actual-identity"]').text()).toContain('长标题 / Song A')
  })
})

describe('artwork resource identity', () => {
  const artwork = { artwork_id: 'art-a', source: 'EMBEDDED', picture_index: 0, mime_type: 'image/png', width: null, height: null, content_sha256: 'hash-a' }
  function withArtwork() {
    const value = structuredClone(fixture.snapshot)
    Object.assign(value.current_song, { artwork })
    return value
  }
  afterEach(() => vi.unstubAllGlobals())
  it.each([404, 503])('Artwork API %s preserves a deliberate placeholder', async status => {
    vi.stubGlobal('fetch', async () => new Response('', { status }))
    const { wrapper } = page(withArtwork())
    await flushPromises()
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.get('[data-testid="artwork-placeholder"]').attributes('aria-label')).toContain(status === 404 ? '无封面' : '封面读取失败')
  })
  it('network and image decode failure are distinct from absent artwork', async () => {
    vi.stubGlobal('fetch', async () => { throw new Error('offline') })
    const { wrapper } = page(withArtwork())
    await flushPromises()
    expect(wrapper.get('[data-testid="artwork-placeholder"]').attributes('aria-label')).toContain('封面读取失败')
  })
  it('late artwork after a song change cannot cover the new identity or retain old lyrics references', async () => {
    const { deferred } = await import('../support/transport')
    const old = deferred<Response>()
    vi.stubGlobal('fetch', () => old.promise)
    vi.stubGlobal('URL', class extends URL { static createObjectURL() { return 'blob:old' }; static revokeObjectURL() {} })
    const { wrapper, store } = page(withArtwork())
    await flushPromises()
    const next = structuredClone(fixture.snapshot); next.sequence++
    Object.assign(next.current_song, { song_id: 'song-b', title: '新歌曲', file_uri: 'b.flac', lyrics: 'new text' })
    store.acceptRefresh(parseSnapshot(next), 1)
    await flushPromises()
    old.resolve(new Response('old image', { status: 200 }))
    await flushPromises()
    expect(wrapper.get('[data-testid="actual-identity"]').text()).toContain('新歌曲')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.get('[data-testid="artwork-placeholder"]').attributes('aria-label')).toContain('无封面')
    const { derivePlayerFacts } = await import('../../src/components/player/playerFacts')
    expect(derivePlayerFacts(store.snapshot, store.writable).song?.lyrics).toBe('new text')
    expect(derivePlayerFacts(store.snapshot, store.writable).song?.lyrics).not.toContain('fixture')
  })
  it('late artwork from an older library revision is rejected for the same song', async () => {
    const { deferred } = await import('../support/transport')
    const first = deferred<Response>(), second = deferred<Response>()
    let requests = 0
    vi.stubGlobal('fetch', () => ++requests === 1 ? first.promise : second.promise)
    vi.stubGlobal('URL', class extends URL { static createObjectURL(blob: Blob) { return `blob:${blob.size}` }; static revokeObjectURL() {} })
    const { wrapper, store } = page(withArtwork())
    await flushPromises()
    const next = withArtwork(); next.sequence++; next.revisions.library++
    store.acceptRefresh(parseSnapshot(next), 1)
    await flushPromises()
    second.resolve(new Response('new')); await flushPromises()
    expect(wrapper.get('img').attributes('src')).toBe('blob:3')
    first.resolve(new Response('old artwork')); await flushPromises()
    expect(wrapper.get('img').attributes('src')).toBe('blob:3')
    await wrapper.get('img').trigger('error')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain('封面读取失败')
  })
})

describe('application route and connection ownership', () => {
  it('default route renders Player without Task 9 navigation', async () => {
    const { createMemoryHistory, RouterView } = await import('vue-router')
    const { createPlayerRouter } = await import('../../src/router')
    const router = createPlayerRouter(createMemoryHistory())
    const store = createPlayerStore(), socket = new Socket()
    const api = createApiClient({ origin: 'http://localhost', fetch: async () => { throw new Error('Unexpected HTTP') } })
    let opened = 0
    const realtime = createRealtimeClient({ api, store, socketFactory: () => { opened++; return socket }, clock: { setTimeout, clearTimeout, random: () => 0 } })
    await router.push('/'); await router.isReady()
    const wrapper = mount(defineComponent({ render: () => h(AppShell, { store, realtime }, { default: () => h(RouterView) }) }), { global: { plugins: [router] } })
    wrappers.push(wrapper)
    socket.snapshot(fixture.snapshot); await flushPromises()
    expect(wrapper.get('[data-testid="actual-identity"]').text()).toContain('长标题 / Song A')
    expect(wrapper.find('nav').exists()).toBe(false)
    await router.push('/unknown'); await flushPromises()
    expect(router.currentRoute.value.path).toBe('/')
    expect(opened).toBe(1)
    wrapper.unmount(); wrappers.pop()
    expect([...socket.listeners.values()].every(listeners => listeners.size === 0)).toBe(true)
    expect(store.writable).toBe(false)
  })
})

it('no output sample shows unknown rather than an unavailable or enabled fact', async () => {
  const state = structuredClone(fixture.empty_snapshot); state.output.states = []
  const { wrapper } = page(state); await flushPromises()
  expect(wrapper.get('[data-testid="output-fact"]').text()).toBe('DAC尚未确认')
  expect(wrapper.get('[data-testid="output-fact"]').text()).not.toContain('已启用')
})

it('current-specific capabilities stay disabled without proof while Stop follows connection permission', async () => {
  const { derivePlayerFacts } = await import('../../src/components/player/playerFacts')
  const value = structuredClone(fixture.snapshot)
  const store = createPlayerStore(); store.beginConnection(4); store.acceptInitial(parseSnapshot(value), 4)
  expect(derivePlayerFacts(store.snapshot, true).capabilities.resume).toBe(true)
  expect(derivePlayerFacts(store.snapshot, true).capabilities.seek).toBe(false)
  expect(derivePlayerFacts(store.snapshot, false).capabilities).toEqual({ pause: false, resume: false, seek: false, next: false, previous: false, stop: false })
  value.sequence++; value.playback_observation.bound_queue_item_id = null as unknown as string
  store.acceptRefresh(parseSnapshot(value), 4)
  expect(derivePlayerFacts(store.snapshot, true).capabilities).toEqual({ pause: false, resume: false, seek: false, next: false, previous: false, stop: true })
})

it('an output fallback with no successful observation never implies historical confirmation', async () => {
  const value = structuredClone(fixture.empty_snapshot)
  value.output.states[0].status = 'UNAVAILABLE'
  const { wrapper } = page(value); await flushPromises()
  const text = wrapper.get('[data-testid="output-fact"]').text()
  expect(text).toContain('尚未确认')
  expect(text).not.toContain('最后确认')
  expect(text).not.toContain('已启用')
})

it.each([
  ['ACTIVE', 'fresh', 'DAC已启用'],
  ['INACTIVE', 'fresh', 'DAC未启用'],
  ['UNAVAILABLE', 'fresh', 'DAC不可用'],
  ['ACTIVE', 'stale', 'DAC状态已过期'],
  ['ACTIVE', 'unknown', 'DAC尚未确认'],
] as const)('compact DAC summary preserves %s/%s authority without claiming a physical connection', async (status, freshness, label) => {
  const value = structuredClone(fixture.snapshot)
  Object.assign(value.output.states[0], { status, stale: freshness === 'stale' })
  value.output_observation.freshness = freshness
  const { wrapper, store } = page(value)
  await flushPromises()
  expect(wrapper.get('[data-testid="output-fact"]').text()).toBe(label)
  expect(wrapper.get('[data-testid="output-fact"]').text()).not.toContain('已连接')
  store.markDisconnected(); await flushPromises()
  expect(wrapper.get('[data-testid="output-fact"]').text()).toBe(freshness === 'unknown' ? 'DAC尚未确认' : 'DAC状态已过期')
})

it('Player keeps one brand header and places the DAC summary beside source metadata', async () => {
  const value = structuredClone(fixture.snapshot)
  Object.assign(value.current_song, { codec: 'FLAC' })
  const { wrapper } = page(value); await flushPromises()
  expect(wrapper.find('h1').exists()).toBe(false)
  expect(wrapper.get('.page-header').text()).toContain('MPD SERVER')
  expect(wrapper.get('.page-header').text()).toContain('实时连接')
  expect(wrapper.get('.metadata-row [data-testid="output-fact"]').text()).toBe('DAC已启用')
  expect(wrapper.get('.metadata-row [data-testid="source-metadata"]').text()).toContain('FLAC')
  expect(wrapper.find('.output-summary').exists()).toBe(false)
})

it('confirmed Stop uses actual freshness without requiring bound progress freshness', async () => {
  const value = structuredClone(fixture.snapshot)
  value.playback.state = 'STOPPED'
  Object.assign(value.playback_observation, { actual_state: 'stopped', sync_status: 'CONFIRMED', actual_freshness: 'fresh', freshness: 'unknown', matches_current: null, bound_queue_item_id: null, control_target: null, position_seconds: null, duration_seconds: null })
  const { wrapper } = page(value); await flushPromises()
  expect((await import('../../src/components/player/playerFacts')).derivePlayerFacts(parseSnapshot(value), true).stateLabel).toBe('已停止')
  expect(wrapper.get('[data-testid="actual-identity"]').find('.eyebrow').exists()).toBe(false)
  expect(wrapper.get('[data-testid="actual-identity"]').text()).not.toContain('未确认')
  expect(wrapper.get('[data-testid="last-business"]').text()).toContain('长标题 / Song A')
  expect(wrapper.get('[data-testid="progress"]').text()).not.toContain('0:37')
})

it('fresh unbound actual state remains an actual observation while its business identity stays unconfirmed', async () => {
  const value = structuredClone(fixture.snapshot)
  Object.assign(value.playback_observation, { actual_state: 'playing', actual_freshness: 'fresh', freshness: 'unknown', matches_current: null, bound_queue_item_id: null, sync_status: 'UNBOUND' })
  const { wrapper } = page(value); await flushPromises()
  expect((await import('../../src/components/player/playerFacts')).derivePlayerFacts(parseSnapshot(value), true).stateLabel).toBe('正在播放')
  expect(wrapper.get('[data-testid="actual-identity"]').find('.eyebrow').exists()).toBe(false)
  expect(wrapper.get('[data-testid="actual-identity"]').text()).not.toContain('未确认')
  expect(wrapper.text()).toContain('未绑定')
  expect(wrapper.get('[data-testid="last-business"]').text()).toContain('长标题 / Song A')
})

it('artwork remains loaded through a local action handoff but a new same-URI occurrence rejects late artwork', async () => {
  const { playerPage, playerState } = await import('../support/player')
  const { deferred } = await import('../support/transport')
  const action = deferred<Response>(), image = deferred<Response>()
  const fetchImage = vi.fn(() => image.promise)
  vi.stubGlobal('fetch', fetchImage)
  vi.stubGlobal('URL', class extends URL { static createObjectURL(blob: Blob) { return `blob:${blob.size}` }; static revokeObjectURL() {} })
  const h = playerPage(action.promise); wrappers.push(h.wrapper)
  const initial = playerState(); initial.sequence++; initial.current_song!.artwork = { artwork_id: 'art-a', source: 'EMBEDDED', picture_index: 0, mime_type: 'image/png', width: null, height: null, content_sha256: 'hash-a' }
  h.store.acceptRefresh(parseSnapshot(initial), 1); await flushPromises()
  expect(fetchImage).toHaveBeenCalledTimes(1)
  await h.wrapper.get('button[aria-label="继续播放"]').trigger('click')
  const unknown = structuredClone(initial); unknown.sequence++
  Object.assign(unknown.playback_observation, fixture.empty_snapshot.playback_observation)
  h.store.acceptRefresh(parseSnapshot(unknown), 1); await flushPromises()
  image.resolve(new Response('image')); await flushPromises()
  expect(h.wrapper.get('img').attributes('src')).toBe('blob:5')
  const fresh = structuredClone(initial); fresh.sequence += 2
  h.store.acceptRefresh(parseSnapshot(fresh), 1); await flushPromises()
  expect(fetchImage).toHaveBeenCalledTimes(1)
  expect(h.wrapper.get('img').attributes('src')).toBe('blob:5')
  const old = deferred<Response>(), current = deferred<Response>()
  fetchImage.mockImplementationOnce(() => old.promise).mockImplementationOnce(() => current.promise)
  fresh.sequence++; fresh.playback_observation.control_target!.token = 'replayed-occurrence'
  h.store.acceptRefresh(parseSnapshot(fresh), 1); await flushPromises()
  fresh.sequence++; fresh.playback_observation.control_target!.token = 'another-occurrence'; fresh.playback_observation.actual_current!.entry_id = 9
  h.store.acceptRefresh(parseSnapshot(fresh), 1); await flushPromises()
  current.resolve(new Response('current')); await flushPromises()
  old.resolve(new Response('obsolete')); await flushPromises()
  expect(h.wrapper.get('img').attributes('src')).toBe('blob:7')
  action.reject(new Error('retired')); await flushPromises()
})
