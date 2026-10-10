import { afterEach, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPlayerStore } from '../../src/stores/player'
import { createPlayerClock } from '../../src/components/player/playerClock'
import { playerState, flushPromises, fixture } from '../support/player'
import { FakeClock } from '../support/transport'
let wrapper: VueWrapper | undefined
let dispose: (() => void) | undefined
afterEach(() => { wrapper?.unmount(); dispose?.(); vi.unstubAllGlobals() })
it('lyrics highlight uses the player display clock', async () => {
  const module = await import('../../src/components/player/LyricsStage.vue').catch(() => null)
  expect(module?.default).toBeDefined()
  const store = createPlayerStore(), time = new FakeClock(), s = playerState()
  s.current_song!.lyrics = '[00:37]第一行\n[00:39]第二行'
  s.current_song!.lyrics_format = 'lrc'; s.current_song!.lyrics_status = 'available'
  s.playback_observation.actual_state = 'playing'
  store.beginConnection(1); store.acceptInitial(s, 1)
  const clock = createPlayerClock(store, time.now); dispose = clock.dispose
  store.acceptRefresh(s, 1, { receivedAt: 0, roundTripMs: 0 })
  wrapper = mount(module!.default, { props: { song: store.snapshot!.current_song, position: clock.position(), resourceScope: 'epoch/item-a' } })
  expect(wrapper.findAll('[aria-current="true"]').map(e => e.text())).toEqual(['第一行'])
  time.advance(2000); await wrapper.setProps({ position: clock.position() })
  expect(wrapper.findAll('[aria-current="true"]').map(e => e.text())).toEqual(['第二行'])
  expect(store.snapshot!.playback_observation.position_seconds).toBe(37)
})
async function lyrics(song = playerState().current_song, position: number | null = 37, scope = 'a') {
  const { default: Stage } = await import('../../src/components/player/LyricsStage.vue')
  wrapper = mount(Stage, { props: { song, position, resourceScope: scope } })
  return wrapper
}
it('read_error retains fallback text and source; plain, missing and malformed LRC remain distinguishable in header details', async () => {
  const { playerPage } = await import('../support/player')
  const h = playerPage(); wrapper = h.wrapper
  let sequence = playerState().sequence
  const song = playerState().current_song!
  async function update(update: Partial<typeof song>) {
    const state = playerState(); state.sequence = ++sequence
    state.current_song = { ...song, ...update }
    h.store.acceptRefresh(state, 1); await flushPromises()
  }
  Object.assign(song, { lyrics: '<b>普通歌词</b>', lyrics_format: 'plain', lyrics_source: 'embedded', lyrics_status: 'read_error' })
  await update({})
  await wrapper.get('button[aria-label="显示歌词"]').trigger('click')
  const notice = () => wrapper!.get('.page-header [data-testid="operation-status"]').text()
  expect(notice()).toContain('歌词读取失败'); expect(wrapper.get('.lyrics-content').text()).toContain('<b>普通歌词</b>'); expect(wrapper.find('b').exists()).toBe(false)
  expect(notice()).toContain('embedded'); expect(notice()).toContain('普通文本'); expect(wrapper.find('[aria-current]').exists()).toBe(false)
  expect(wrapper.get('.lyrics-stage').text()).not.toContain('歌词读取失败')
  await update({ lyrics: '[坏标签]原文', lyrics_format: 'lrc', lyrics_status: 'available' })
  expect(notice()).toContain('无法同步'); expect(wrapper.get('.lyrics-content').text()).toContain('[坏标签]原文')
  await update({ lyrics: null, lyrics_status: 'missing' }); expect(notice()).toContain('无歌词'); expect(notice()).not.toContain('读取失败')
  await update({ lyrics: null, lyrics_status: 'read_error' }); expect(notice()).toContain('读取失败'); expect(notice()).not.toContain('无歌词')
})
it('offset and simultaneous cues use valid progress only; lost binding removes highlight', async () => {
  const song = playerState().current_song!
  Object.assign(song, { lyrics: '[offset:1000]\n[00:38]甲\n[00:38]乙', lyrics_format: 'lrc' })
  const w = await lyrics(song)
  expect(w.findAll('[aria-current="true"]').map(e => e.text())).toEqual(['甲', '乙'])
  await w.setProps({ position: null }); expect(w.find('[aria-current="true"]').exists()).toBe(false)
})
it('manual scrolling resumes synchronized follow only after three idle seconds and retires timers on occurrence changes', async () => {
  vi.useFakeTimers()
  const scroll = vi.fn(); Object.defineProperty(Element.prototype, 'scrollTo', { configurable: true, value: scroll })
  vi.stubGlobal('matchMedia', () => ({ matches: true }))
  const song = playerState().current_song!
  Object.assign(song, { lyrics: '[00:37]甲\n[00:38]乙\n[00:39]丙', lyrics_format: 'lrc' })
  const w = await lyrics(song); await flushPromises()
  expect(w.text()).not.toContain('同步歌词'); expect(w.text()).not.toContain('跟随当前行')
  expect(w.find('button[aria-label="回到当前行"]').exists()).toBe(false)
  const content = w.get('[aria-label="歌词内容"]')
  await content.trigger('pointerdown', { clientX: 0, clientY: 0 })
  scroll.mockClear(); await w.setProps({ position: 38 })
  await vi.advanceTimersByTimeAsync(4000); expect(scroll).not.toHaveBeenCalled()
  await content.trigger('pointerup')
  await vi.advanceTimersByTimeAsync(2000); await content.trigger('scroll')
  await vi.advanceTimersByTimeAsync(2999); expect(scroll).not.toHaveBeenCalled()
  await vi.advanceTimersByTimeAsync(1)
  expect(scroll).toHaveBeenLastCalledWith(expect.objectContaining({ behavior: 'auto' }))
  scroll.mockClear(); await content.trigger('wheel'); await w.setProps({ position: 39 })
  expect(scroll).not.toHaveBeenCalled()
  await w.setProps({ resourceScope: 'next', position: 37 }); await flushPromises()
  expect(scroll).toHaveBeenCalled()
  scroll.mockClear(); await vi.advanceTimersByTimeAsync(3000); expect(scroll).not.toHaveBeenCalled()
  await content.trigger('keydown', { key: 'ArrowDown' }); w.unmount(); scroll.mockClear()
  await vi.advanceTimersByTimeAsync(3000); expect(scroll).not.toHaveBeenCalled()
})
it('plain lyrics keep their manual position without a timer or seek', async () => {
  vi.useFakeTimers()
  const scroll = vi.fn(); Object.defineProperty(Element.prototype, 'scrollTo', { configurable: true, value: scroll })
  const w = await lyrics({ ...playerState().current_song!, lyrics: '普通文本', lyrics_format: 'text' })
  await w.get('[aria-label="歌词内容"]').trigger('wheel')
  await w.get('.lyrics-plain').trigger('click'); await vi.advanceTimersByTimeAsync(10000)
  expect(scroll).not.toHaveBeenCalled(); expect(w.emitted('seek')).toBeUndefined()
})
it('cue activation seeks with inverse offset but dragging, long presses and selection do not seek', async () => {
  vi.useFakeTimers()
  const w = await lyrics({ ...playerState().current_song!, lyrics: '[offset:1000]\n[00:38]甲\n[00:40]乙', lyrics_format: 'lrc' })
  await w.setProps({ seekEnabled: true, duration: 180 })
  const content = w.get('[aria-label="歌词内容"]'), cue = w.findAll('.lyric-cue')[1]!
  await content.trigger('pointerdown', { clientX: 10, clientY: 10 })
  await content.trigger('pointermove', { clientX: 10, clientY: 30 })
  await content.trigger('pointerup'); await cue.trigger('click')
  expect(w.emitted('seek')).toBeUndefined()
  await content.trigger('pointerdown'); await vi.advanceTimersByTimeAsync(600)
  await content.trigger('pointerup'); await cue.trigger('click')
  expect(w.emitted('seek')).toBeUndefined()
  vi.spyOn(window, 'getSelection').mockReturnValue({ isCollapsed: false } as Selection)
  await cue.trigger('keydown', { key: 'Enter' }); expect(w.emitted('seek')).toBeUndefined()
  vi.mocked(window.getSelection).mockReturnValue(null)
  await cue.trigger('keydown', { key: 'Enter' })
  expect(w.emitted('seek')).toEqual([[39]])
  await w.setProps({ seekEnabled: false }); await cue.trigger('keydown', { key: 'Enter' })
  expect(w.emitted('seek')).toHaveLength(1)
})
it('product cue seek shares target, pending lock and progress preview without rewriting canonical position', async () => {
  const { playerPage } = await import('../support/player')
  const { deferred } = await import('../support/transport')
  const receipt = deferred<Response>(), s = playerState(); s.sequence++
  Object.assign(s.current_song!, { lyrics: '[offset:500]\n[00:40]跳到这里\n[99:00]超出时长', lyrics_format: 'lrc' })
  const h = playerPage(receipt.promise, Response.json(s)); wrapper = h.wrapper
  h.store.acceptRefresh(s, 1); await flushPromises()
  await wrapper.get('button[aria-label="显示歌词"]').trigger('click')
  const cues = wrapper.findAll('.lyric-cue')
  await cues[0]!.trigger('click')
  const posts = h.network.requests.filter(r => r.init?.method === 'POST')
  expect(posts).toHaveLength(1)
  expect(JSON.parse(posts[0]!.init!.body as string)).toEqual({ seconds: 39.5, target: s.playback_observation.control_target })
  expect(posts[0]!.url).toContain('/api/playback/seek')
  expect(wrapper.get('[data-testid="progress"]').text()).toContain('待确认位置 0:39')
  expect(h.store.snapshot!.playback_observation.position_seconds).toBe(37)
  await cues[0]!.trigger('click'); expect(h.network.requests.filter(r => r.init?.method === 'POST')).toHaveLength(1)
  receipt.resolve(Response.json({ ...fixture.playback_receipt, updated_at: '2026-10-09T08:00:00Z' })); await flushPromises()
  await cues[1]!.trigger('click'); expect(h.network.requests.filter(r => r.init?.method === 'POST')).toHaveLength(1)
  h.store.markDisconnected(); await flushPromises()
  await cues[0]!.trigger('click'); expect(h.network.requests.filter(r => r.init?.method === 'POST')).toHaveLength(1)
})
it('the real Player switches through the whole artwork and return icon and retires old lyrics on song and library revision changes', async () => {
  const { playerPage } = await import('../support/player')
  const h = playerPage(); wrapper = h.wrapper
  const s = playerState(); s.sequence++
  Object.assign(s.current_song!, { lyrics: '[00:37]旧歌词', lyrics_format: 'lrc', lyrics_status: 'available' })
  h.store.acceptRefresh(s, 1); await flushPromises()
  expect(wrapper.find('.media-selector').exists()).toBe(false)
  expect(wrapper.get('button[aria-label="显示歌词"]').find('.artwork-stage').exists()).toBe(true)
  await wrapper.get('button[aria-label="显示歌词"]').trigger('click')
  expect(wrapper.find('.artwork-stage').exists()).toBe(false)
  expect(wrapper.get('button[aria-label="显示封面"]').find('svg[aria-hidden="true"]').exists()).toBe(true)
  expect(wrapper.get('button[aria-label="显示封面"]').text()).toBe('')
  await wrapper.get('[aria-label="歌词内容"]').trigger('click')
  expect(wrapper.find('.lyrics-stage').exists()).toBe(true)
  expect(wrapper.findAll('[aria-current="true"]').map(e => e.text())).toEqual(['旧歌词'])
  const next = structuredClone(s); next.sequence++; next.current_song!.song_id = 'new-song'; next.current_song!.lyrics = '[00:37]新歌词'; next.playback!.song_id = 'new-song'
  next.playback_observation.control_target!.token = 'new'; next.playback_observation.actual_current!.entry_id = 99
  h.store.acceptRefresh(next, 1); await flushPromises()
  expect(wrapper.text()).toContain('新歌词'); expect(wrapper.text()).not.toContain('旧歌词')
  h.store.acceptRefresh(s, 1); await flushPromises(); expect(wrapper.text()).not.toContain('旧歌词')
  next.sequence++; next.revisions.library++; next.current_song!.lyrics = '扫描后的普通文本'; next.current_song!.lyrics_format = 'plain'
  h.store.acceptRefresh(next, 1); await flushPromises(); expect(wrapper.text()).toContain('扫描后的普通文本'); expect(wrapper.find('[aria-current="true"]').exists()).toBe(false)
  h.store.markDisconnected(); await flushPromises(); expect(wrapper.find('[aria-current="true"]').exists()).toBe(false)
  await wrapper.get('button[aria-label="显示封面"]').trigger('click'); expect(wrapper.find('.lyrics-stage').exists()).toBe(false)
})
it('late HTTP lyrics from an old connection cannot replace the new song baseline', async () => {
  const { createApiClient } = await import('../../src/services/api')
  const { createRealtimeClient } = await import('../../src/services/realtime')
  const { transport, deferred } = await import('../support/transport')
  const { playerKey } = await import('../../src/components/player/playerFacts')
  const { default: Player } = await import('../../src/views/PlayerView.vue')
  const response = deferred<Response>(), network = transport(response.promise), store = createPlayerStore()
  type Message = { data: string }
  const sockets: { message?: (e: Message) => void; closeEvent?: () => void }[] = []
  const realtime = createRealtimeClient({ api: createApiClient({ origin: 'http://localhost', fetch: network.fetch }), store,
    socketFactory: () => {
      const handlers: typeof sockets[number] = {}; sockets.push(handlers)
      return { addEventListener(type: string, callback: any) { if (type === 'message') handlers.message = callback; if (type === 'close') handlers.closeEvent = callback }, removeEventListener() {}, close() {} }
    }, clock: { setTimeout, clearTimeout, random: () => 0 } })
  const old = playerState(); old.current_song!.lyrics = '[00:37]旧连接歌词'; old.current_song!.lyrics_format = 'lrc'
  const frame = (s: typeof old) => ({ data: JSON.stringify({ type: 'snapshot', protocol_version: 1, epoch: s.epoch, sequence: s.sequence, state: s }) })
  realtime.start(); sockets[0]!.message!(frame(old))
  wrapper = mount(Player, { global: { provide: { [playerKey as symbol]: store } } })
  await wrapper.get('button[aria-label="显示歌词"]').trigger('click')
  const pendingRead = realtime.refresh(); await Promise.resolve()
  realtime.stop(); realtime.start()
  const fresh = structuredClone(old); fresh.epoch = 'next-epoch'; fresh.current_song!.lyrics = '[00:37]新连接歌词'
  sockets[1]!.message!(frame(fresh)); await flushPromises()
  response.resolve(Response.json(old)); await pendingRead; await flushPromises()
  expect(wrapper.text()).toContain('新连接歌词'); expect(wrapper.text()).not.toContain('旧连接歌词')
  realtime.stop()
})
it('the product progress and lyrics advance on one display clock without a new canonical position', async () => {
  vi.useFakeTimers(); let elapsed = 0
  vi.spyOn(performance, 'now').mockImplementation(() => elapsed)
  const { playerPage } = await import('../support/player')
  const h = playerPage(); wrapper = h.wrapper
  const s = playerState(); s.sequence++; s.playback_observation.actual_state = 'playing'
  Object.assign(s.current_song!, { lyrics: '[00:37]开始\n[00:39]共同时钟', lyrics_format: 'lrc', lyrics_status: 'available' })
  h.store.acceptRefresh(s, 1, { receivedAt: 0, roundTripMs: 0 })
  await wrapper.get('button[aria-label="显示歌词"]').trigger('click')
  elapsed = 2000; await vi.advanceTimersByTimeAsync(2000)
  expect(wrapper.get('[data-testid="progress"]').text()).toContain('0:39')
  expect(wrapper.findAll('[aria-current="true"]').map(e => e.text())).toEqual(['共同时钟'])
  expect(h.store.snapshot!.playback_observation.position_seconds).toBe(37)
  expect(h.network.requests).toHaveLength(0)
})
