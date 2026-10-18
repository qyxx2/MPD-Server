import { afterEach, expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { libraryPage } from '../support/library'
import { setViewport } from '../support/shell'
import { deferred } from '../support/transport'
import { fixture, playerState } from '../support/player'
let page: Awaited<ReturnType<typeof libraryPage>> | undefined
afterEach(() => { page?.wrapper.unmount(); page = undefined })
// A mode-keyed RouterView would lose draft, focus and scroll.
it('preserves drafts and route when layout changes', async () => {
  setViewport(1194, 834)
  page = await libraryPage('/library/search?q=draft', path => path.startsWith('/api/library/search/results') ? Promise.resolve(Response.json({ groups: [], song_ids: [] })) : undefined)
  document.body.appendChild(page.wrapper.element)
  const search = page.wrapper.get('input[type="search"]').element as HTMLInputElement
  search.focus()
  for (const [w, h] of [[834, 1194], [1194, 834], [899, 700], [901, 700]] as const) {
    setViewport(w, h); await flushPromises()
    expect(page.router.currentRoute.value.fullPath).toBe('/library/search?q=draft')
    expect(page.wrapper.get('input[type="search"]').element).toBe(search)
    expect(search.value).toBe('draft'); expect(document.activeElement).toBe(search)
  }
  await page.router.push('/settings'); await flushPromises()
  const host = page.wrapper.get('[name="mpd-host"]'), port = page.wrapper.get('[name="mpd-port"]')
  await host.setValue('draft.example'); await port.setValue('16600')
  const scroller = page.wrapper.get('.shell-content').element
  scroller.scrollTop = 150; (host.element as HTMLElement).focus()
  for (const [w, h] of [[834, 1194], [1194, 834]] as const) {
    setViewport(w, h); await flushPromises()
    expect(page.router.currentRoute.value.path).toBe('/settings')
    expect(page.wrapper.get('[name="mpd-host"]').element).toBe(host.element)
    expect((host.element as HTMLInputElement).value).toBe('draft.example')
    expect((port.element as HTMLInputElement).value).toBe('16600')
    expect(document.activeElement).toBe(host.element); expect(scroller.scrollTop).toBe(150)
  }
  // Cancel by leaving without submitting the form, preserving existing semantics.
  await page.router.push('/library'); await page.router.push('/settings'); await flushPromises()
  expect((page.wrapper.get('[name="mpd-host"]').element as HTMLInputElement).value).toBe('mpd')
  expect(page.requests.filter(r => r.init?.method !== 'GET')).toHaveLength(0)
})
// A view-owned task would lose pending intent or retry under navigation/rotation.
it('keeps pending ownership across workspace navigation', async () => {
  setViewport(1194, 834)
  const reply = deferred<Response>(); let writes = 0
  page = await libraryPage('/settings', (path, init) => {
    if (path === '/api/system/output' && init?.method === 'PUT') return ++writes === 1 ? reply.promise : Promise.resolve(Response.json(fixture.rest_output))
    if (path === '/api/state') return Promise.resolve(Response.json(playerState()))
  })
  await page.wrapper.get('[data-output-switch]').trigger('click')
  const pending = page.tasks.entries.value.find(r => r.intent.path === '/api/system/output')!
  expect(pending.state).toBe('pending'); const key = pending.intent.key
  for (const route of ['/queue', '/library', '/settings']) {
    await page.router.push(route); setViewport(834, 1194); await flushPromises()
    setViewport(1194, 834); await flushPromises()
    expect(page.tasks.entries.value.find(r => r.intent.key === key)?.state).toBe('pending')
  }
  expect(page.wrapper.get('[data-output-switch]').attributes('disabled')).toBeDefined()
  reply.reject(new TypeError('lost ACK')); await flushPromises()
  expect(page.tasks.entries.value.find(r => r.intent.key === key)?.state).toBe('unknown')
  expect(page.wrapper.get('[data-save-mpd]').attributes('disabled')).toBeDefined()
  await page.router.push('/library'); await flushPromises()
  await page.tasks.entries.value.find(r => r.intent.key === key)!.retry!(); await flushPromises()
  const requests = page.requests.filter(r => r.init?.method === 'PUT')
  expect(requests).toHaveLength(2); expect(requests[1]!.path).toBe(requests[0]!.path)
  expect(requests[1]!.init!.body).toBe(requests[0]!.init!.body)
  expect(new Headers(requests[1]!.init!.headers).get('Idempotency-Key')).toBe(key)
  expect(new Headers(requests[0]!.init!.headers).get('Idempotency-Key')).toBe(key)
  expect(page.tasks.entries.value.find(r => r.intent.key === key)?.state).toBe('confirmed')
  await page.router.push('/settings'); page.store.markDisconnected(); await flushPromises()
  expect(page.wrapper.get('[data-save-mpd]').attributes('disabled')).toBeDefined()
  expect(page.wrapper.get('[data-output-switch]').attributes('disabled')).toBeDefined()
})
