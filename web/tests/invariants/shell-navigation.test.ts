import { expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { playerState } from '../support/player'
import { shellPage } from '../support/shell'
it('one_shell_one_connection_four_routes', async () => {
  const h = await shellPage()
  expect(h.router.currentRoute.value.path).toBe('/')
  expect(h.wrapper.findAll('nav a')).toHaveLength(4)
  const shell = h.wrapper.get('.app-shell').element, header = h.wrapper.get('.page-header').element
  const nav = h.wrapper.get('nav').element, background = h.wrapper.get('.app-background').element
  for (const path of ['/queue', '/library', '/settings', '/library/search?q=夜航', '/library/playlists/p1', '/library/albums/a1', '/']) {
    await h.router.push(path); await flushPromises()
    expect(h.router.currentRoute.value.path).toBe(path.split('?')[0])
    expect(h.wrapper.get('.app-shell').element).toBe(shell)
    expect(h.wrapper.get('.page-header').element).toBe(header)
    expect(h.wrapper.get('nav').element).toBe(nav)
    expect(h.wrapper.get('.app-background').element).toBe(background)
    const active = h.wrapper.get('nav a[aria-current="page"]')
    expect(active.attributes('href')).toBe(path.startsWith('/library') ? '/library' : path)
    expect(h.wrapper.findAll('[data-testid="operation-status"]')).toHaveLength(1)
  }
  await h.router.push('/library/favorites'); h.router.back(); await flushPromises()
  expect(h.wrapper.find('[data-testid="actual-identity"]').exists()).toBe(true)
  await h.router.push('/library/not-a-category/a'); await flushPromises()
  expect(h.router.currentRoute.value.path).toBe('/')
  expect(h.realtime.start).toHaveBeenCalledTimes(1)
  expect(h.realtime.stop).not.toHaveBeenCalled()
  h.wrapper.unmount()
  expect(h.realtime.stop).toHaveBeenCalledTimes(1)
})

it('activity_success_survives_navigation_without_another_mutation_or_poll_reordering', async () => {
  const h = await shellPage(new Response(null, { status: 204 }), Response.json(playerState()))
  const intent = h.api.createIntent('DELETE', '/api/playback/queue/items/a', undefined)
  await h.tasks.run(intent, () => undefined, async () => {}, '删除队列条目'); await flushPromises()
  await h.wrapper.get('.status-toggle').trigger('click')
  const center = h.wrapper.get('.playback-status').element
  const entry = h.wrapper.get(`[data-notice="${intent.key}"]`).element
  await h.router.push('/library'); await flushPromises()
  await h.router.push('/'); await flushPromises()
  expect(h.wrapper.get('.playback-status').element).toBe(center)
  expect(h.wrapper.get(`[data-notice="${intent.key}"]`).element).toBe(entry)
  expect(h.wrapper.get(`[data-notice="${intent.key}"]`).attributes('data-status')).toBe('success')
  expect(h.wrapper.find(`[aria-label="重试操作 ${intent.key}"]`).exists()).toBe(false)
  expect(h.network.requests.filter(r => r.init?.method === 'DELETE')).toHaveLength(1)
  h.wrapper.unmount()
})
