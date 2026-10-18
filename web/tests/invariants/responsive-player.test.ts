import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { shellPage, setViewport } from '../support/shell'
import { playerState, fixture } from '../support/player'
import { deferred } from '../support/transport'

let page: Awaited<ReturnType<typeof shellPage>> | undefined
afterEach(() => { page?.wrapper.unmount(); page = undefined })

// jsdom has no layout. Supply browser measurements at the DOM boundary only;
// shell/session/controls and the observer-driven mode transitions remain real.
function geometry(initialHeight: number, buttonWidth = 0) {
  let height = initialHeight
  const observers = new Set<{ callback: ResizeObserverCallback; elements: Set<Element> }>()
  const original = Element.prototype.getBoundingClientRect
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
    if (this.classList.contains('layout-capacity')) return { width: 16, height } as DOMRect
    if (this.classList.contains('player-information')) {
      const compact = this.closest('[data-player-density="compact"]')
      return { width: 300, height: compact ? 220 : 300 } as DOMRect
    }
    if (this.matches('.transport-row button')) return { width: buttonWidth, height: 64 } as DOMRect
    return original.call(this)
  })
  vi.stubGlobal('ResizeObserver', class {
    elements = new Set<Element>()
    constructor(public callback: ResizeObserverCallback) { observers.add(this) }
    observe(element: Element) { this.elements.add(element); queueMicrotask(() => { if (this.elements.size) this.callback([], this as unknown as ResizeObserver) }) }
    disconnect() { this.elements.clear(); observers.delete(this) }
    unobserve(element: Element) { this.elements.delete(element) }
  })
  return async (next = height) => {
    height = next
    // Browser RO delivers a new measurement after compact styles are applied.
    for (let frame = 0; frame < 3; frame++) {
      for (const observer of [...observers]) observer.callback([], observer as unknown as ResizeObserver)
      await flushPromises()
    }
  }
}

it('keeps core controls reachable in compact mode', async () => {
  setViewport(1024, 600); const measure = geometry(440)
  page = await shellPage(); await measure()
  expect(page.wrapper.get('.app-shell').attributes('data-player-density')).toBe('compact')
  expect(page.wrapper.get('.app-shell').attributes('data-layout')).toBe('landscape')
  expect(page.wrapper.find('[aria-label="播放进度"]').exists()).toBe(true)
  expect(page.wrapper.get('[aria-label="播放控制"]').findAll('button')).toHaveLength(3)
  expect(page.wrapper.get('[data-testid="actual-identity"]').text()).toContain(playerState().current_song!.title)
  expect(page.wrapper.findAll('.player')).toHaveLength(1)
})

it('does not oscillate when height is insufficient', async () => {
  setViewport(932, 430); const measure = geometry(180)
  page = await shellPage(); await measure()
  expect(page.wrapper.get('.app-shell').attributes('data-layout')).toBe('portrait')
  const panel = page.wrapper.get('.player').element
  for (let i = 0; i < 4; i++) {
    window.dispatchEvent(new Event('resize')); await measure()
    expect(page.wrapper.get('.app-shell').attributes('data-layout')).toBe('portrait')
    expect(page.wrapper.get('.player').element).toBe(panel)
  }
  await measure(500)
  expect(page.wrapper.get('.app-shell').attributes('data-layout')).toBe('landscape')
  expect(page.realtime.start).toHaveBeenCalledTimes(1)
  expect(page.network.requests.filter(r => r.init?.method === 'POST')).toHaveLength(0)
  const remove = vi.spyOn(window, 'removeEventListener')
  page.wrapper.unmount(); page = undefined
  expect(remove).toHaveBeenCalledWith('resize', expect.any(Function))
  await measure(180) // disconnected observers cannot schedule a new layout
})

it('falls back when enlarged core controls cannot fit the Player width', async () => {
  setViewport(1194, 834); const measure = geometry(680, 160)
  page = await shellPage(); await measure()
  expect(page.wrapper.get('.app-shell').attributes('data-layout')).toBe('portrait')
  expect(page.wrapper.findAll('[aria-label="播放控制"] button')).toHaveLength(3)
  for (let i = 0; i < 3; i++) {
    await measure()
    expect(page.wrapper.get('.app-shell').attributes('data-layout')).toBe('portrait')
  }
})

it('preserves media choice and seek locks', async () => {
  setViewport(1194, 834); const measure = geometry(680)
  const receipt = deferred<Response>()
  page = await shellPage(receipt.promise, Response.json(playerState()))
  const state = playerState(); state.sequence++
  Object.assign(state.current_song!, { lyrics: '[00:37]当前\n[00:40]目标', lyrics_format: 'lrc' })
  page.store.acceptRefresh(state, 1); await flushPromises()
  page.session.mediaMode.value = 'lyrics'
  await page.wrapper.get('.lyric-cue:last-child').trigger('click')
  expect(page.network.requests.filter(r => r.init?.method === 'POST')).toHaveLength(1)
  await measure(180)
  expect(page.wrapper.get('.app-shell').attributes('data-layout')).toBe('portrait')
  expect(page.wrapper.find('[aria-label="显示封面"]').exists()).toBe(true)
  expect(page.wrapper.get('[aria-label="播放进度"]').attributes('disabled')).toBeDefined()
  expect(page.wrapper.get('[data-testid="primary-playback"]').attributes('disabled')).toBeDefined()
  await measure(680)
  expect(page.wrapper.find('[aria-label="显示封面"]').exists()).toBe(false)
  expect(page.session.mediaMode.value).toBe('lyrics')
  expect(page.wrapper.get('[aria-label="播放进度"]').element).toHaveProperty('value', '40')
  page.store.markDisconnected(); await measure(180)
  expect(page.wrapper.get('[data-testid="primary-playback"]').attributes('disabled')).toBeDefined()
  receipt.resolve(Response.json(fixture.playback_receipt)); await flushPromises()
  expect(page.network.requests.filter(r => r.init?.method === 'POST')).toHaveLength(1)
  expect(page.router.currentRoute.value.path).toBe('/')
})

it('exposes complete long identity on touch and keyboard without a playback write', async () => {
  setViewport(1194, 834); page = await shellPage()
  const state = playerState(); state.sequence++
  const title = '很长的歌曲标题🎵'.repeat(12) + 'LongEnglishTitleWithoutSpaces'.repeat(8)
  Object.assign(state.current_song!, { title, artists: ['很长的艺术家名字'.repeat(12)], album: '完整专辑🎹'.repeat(12) })
  page.store.acceptRefresh(state, 1); await flushPromises()
  await page.wrapper.get('summary[aria-label="查看完整歌曲信息"]').trigger('click')
  const details = page.wrapper.get('details.player-song-details')
  expect(details.element).toHaveProperty('open', true)
  expect(details.get('.player-song-information').text()).toContain(title)
  expect(details.get('.player-song-information').text()).toContain(state.current_song!.album)
  await details.trigger('keydown', { key: 'Escape' })
  expect(details.element).toHaveProperty('open', false)
  expect(page.network.requests.filter(r => r.init?.method === 'POST')).toHaveLength(0)
})

it('keeps an unknown mutation locked across fallback and recovery', async () => {
  setViewport(1194, 834); const measure = geometry(680)
  page = await shellPage(new Error('transport timeout'))
  await page.wrapper.get('[data-testid="primary-playback"]').trigger('click'); await flushPromises()
  expect(page.wrapper.text()).toContain('结果未知')
  for (const height of [180, 680, 180]) {
    await measure(height)
    expect(page.wrapper.get('[aria-label="播放进度"]').attributes('disabled')).toBeDefined()
    expect(page.wrapper.get('[data-testid="primary-playback"]').attributes('disabled')).toBeDefined()
    expect(page.wrapper.text()).toContain('结果未知')
  }
  expect(page.network.requests.filter(r => r.init?.method === 'POST')).toHaveLength(1)
  expect(page.realtime.start).toHaveBeenCalledTimes(1)
})
