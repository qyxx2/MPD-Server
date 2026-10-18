import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { shellPage, setViewport } from '../support/shell'

let page: Awaited<ReturnType<typeof shellPage>> | undefined
afterEach(() => { page?.wrapper.unmount(); page = undefined; vi.unstubAllGlobals() })

it('keeps one session across landscape routes', async () => {
  setViewport(1194, 834)
  page = await shellPage()
  const panel = page.wrapper.get('.player').element
  const session = page.session
  const shell = page.wrapper.get('.app-shell').element
  const background = page.wrapper.get('.app-background').element
  for (const path of ['/queue', '/library', '/settings', '/']) {
    await page.router.push(path); await flushPromises()
    expect(page.wrapper.findAll('.player')).toHaveLength(1)
    expect(page.wrapper.get('.player').element).toBe(panel)
    expect(page.session).toBe(session)
    expect(page.wrapper.get('.app-shell').element).toBe(shell)
    expect(page.wrapper.get('.app-background').element).toBe(background)
    expect(page.wrapper.get('nav a').text()).toBe('歌词')
    expect(page.wrapper.findAll('.lyrics-stage')).toHaveLength(path === '/' ? 1 : 0)
    expect(page.wrapper.find('[aria-label="显示封面"]').exists()).toBe(false)
  }
  expect(page.realtime.start).toHaveBeenCalledTimes(1)
  expect(page.realtime.stop).not.toHaveBeenCalled()
  expect(page.network.requests.filter(r => r.init?.method !== 'GET')).toHaveLength(0)
  page.wrapper.unmount(); expect(page.realtime.stop).toHaveBeenCalledTimes(1); page = undefined
})

it('restores portrait media mode after rotation', async () => {
  setViewport(834, 1194); page = await shellPage()
  await page.wrapper.get('[aria-label="显示歌词"]').trigger('click')
  expect(page.wrapper.find('[aria-label="显示封面"]').exists()).toBe(true)
  setViewport(1194, 834); await flushPromises()
  expect(page.wrapper.findAll('.lyrics-stage')).toHaveLength(1)
  expect(page.wrapper.find('[aria-label="显示封面"]').exists()).toBe(false)
  setViewport(834, 1194); await flushPromises()
  expect(page.wrapper.find('[aria-label="显示封面"]').exists()).toBe(true)
  expect(page.wrapper.find('[aria-label="显示歌词"]').exists()).toBe(false)
  expect(page.router.currentRoute.value.path).toBe('/')
  expect(page.network.requests.filter(r => r.init?.method !== 'GET')).toHaveLength(0)
})

it('uses one layout mode at the width boundary', async () => {
  setViewport(899, 700); page = await shellPage()
  await page.router.push('/queue'); await flushPromises()
  for (const [width, height, landscape] of [[899, 700, false], [900, 700, true], [901, 700, true], [900, 900, false], [844, 390, false]] as const) {
    setViewport(width, height); await flushPromises()
    expect(page.wrapper.findAll('.player')).toHaveLength(landscape ? 1 : 0)
    expect(page.wrapper.get('nav a').text()).toBe(landscape ? '歌词' : '正在播放')
  }
  const remove = vi.spyOn(window, 'removeEventListener')
  page.wrapper.unmount(); page = undefined
  expect(remove).toHaveBeenCalledWith('resize', expect.any(Function))
})

it('uses the CSS media query when innerWidth rounds up at the boundary', async () => {
  // Browser zoom can report innerWidth=900 at a fractional CSS width <900.
  // The media query is the browser's authoritative width/orientation result.
  setViewport(900, 700)
  let matches = false
  vi.stubGlobal('matchMedia', () => ({ matches }))
  page = await shellPage()
  await page.router.push('/queue'); await flushPromises()
  expect(page.wrapper.get('.app-shell').attributes('data-layout')).toBe('portrait')
  expect(page.wrapper.findAll('.player')).toHaveLength(0)
  matches = true
  window.dispatchEvent(new Event('resize')); await flushPromises()
  expect(page.wrapper.get('.app-shell').attributes('data-layout')).toBe('landscape')
  expect(page.wrapper.findAll('.player')).toHaveLength(1)
  expect(page.realtime.start).toHaveBeenCalledTimes(1)
  expect(page.network.requests.filter(r => r.init?.method !== 'GET')).toHaveLength(0)
})

it('keeps player geometry ownership across library children and preserves settings draft', async () => {
  setViewport(1194, 834); page = await shellPage()
  const panel = page.wrapper.get('.player').element
  for (const path of ['/library', '/library/search', '/library/favorites', '/library/playlists', '/library/playlists/p1', ...['albums', 'artists', 'genres', 'years', 'tags'].map(kind => `/library/${kind}/id`)]) {
    await page.router.push(path); await flushPromises()
    expect(page.wrapper.get('nav a[aria-current="page"]').attributes('href')).toBe('/library')
    expect(page.wrapper.get('.player').element).toBe(panel)
  }
  await page.router.push('/settings'); await flushPromises()
  const input = page.wrapper.get('input.mpd-host-input')
  await input.setValue('draft.example')
  const settings = input.element
  setViewport(834, 1194); await flushPromises()
  expect(page.wrapper.get('input.mpd-host-input').element).toBe(settings)
  expect((settings as HTMLInputElement).value).toBe('draft.example')
  setViewport(1194, 834); await flushPromises()
  expect((page.wrapper.get('input.mpd-host-input').element as HTMLInputElement).value).toBe('draft.example')
  page.router.back(); await flushPromises()
  expect(page.wrapper.get('nav a[aria-current="page"]').attributes('href')).toBe('/library')
})
