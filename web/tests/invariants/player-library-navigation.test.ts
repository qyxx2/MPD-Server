import { expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { libraryPage, wire } from '../support/library'
import { playerState } from '../support/player'
import { deferred } from '../support/transport'

async function page() {
  const h = await libraryPage('/')
  const state = playerState(); state.sequence++
  Object.assign(state.current_song!, { artists: [wire.artists.items[0]!.name], album: '当前专辑', album_id: 'album / stable' })
  h.store.acceptRefresh(state, 1); await flushPromises()
  return h
}
it.each(['artists', 'albums'])('player metadata opens the exact %s collection without changing playback', async kind => {
  const h = await page()
  try {
    await h.wrapper.get(`[data-player-library="${kind}"]`).trigger('click'); await flushPromises()
    expect(h.router.currentRoute.value.path).toBe(`/library/${kind}/${encodeURIComponent(kind === 'artists' ? wire.artists.items[0]!.artist_id : 'album / stable')}`)
    expect(h.requests.every(request => request.init?.method === 'GET')).toBe(true)
    h.router.back(); await flushPromises()
    expect(h.wrapper.find('[data-testid="actual-identity"]').exists()).toBe(true)
  } finally { h.wrapper.unmount() }
})
it('each artist has its own target and missing album metadata stays noninteractive', async () => {
  const h = await page()
  try {
    const state = playerState(); state.sequence += 2
    Object.assign(state.current_song!, { artists: ['另一位', wire.artists.items[0]!.name], album_id: null })
    h.store.acceptRefresh(state, 1); await flushPromises()
    const row = h.wrapper.get('.player-artist-row')
    expect(row.findAll('[data-player-library="artists"]')).toHaveLength(2)
    expect(row.get('[data-favorite-toggle]').element.parentElement).toBe(row.element)
    expect(h.wrapper.find('[data-player-library="albums"]').exists()).toBe(false)
    await row.findAll('[data-player-library="artists"]')[1]!.trigger('click'); await flushPromises()
    expect(h.router.currentRoute.value.params.id).toBe(wire.artists.items[0]!.artist_id)
  } finally { h.wrapper.unmount() }
})
it('a late artist lookup cannot navigate after leaving the player', async () => {
  const late = deferred<Response>()
  const h = await libraryPage('/', path => path === '/api/library/artists' ? late.promise : undefined)
  try {
    await h.wrapper.get('[data-player-library="artists"]').trigger('click')
    await h.router.push('/queue'); await flushPromises()
    late.resolve(Response.json({ items: [{ artist_id: 'real-id', name: 'Artist', song_count: 1 }], count: 1 })); await flushPromises()
    expect(h.router.currentRoute.value.path).toBe('/queue')
  } finally { h.wrapper.unmount() }
})
it.each(['missing', 'failed'])('an artist lookup that is %s reports a read error without guessing an identity', async mode => {
  const h = await libraryPage('/', path => path === '/api/library/artists'
    ? Promise.resolve(mode === 'failed' ? Response.json({}, { status: 500 }) : Response.json({ items: [], count: 0 })) : undefined)
  try {
    await h.wrapper.get('[data-player-library="artists"]').trigger('click'); await flushPromises()
    expect(h.router.currentRoute.value.path).toBe('/')
    expect(h.wrapper.get('[data-testid="operation-status"]').text()).toContain('艺术家')
    expect(h.wrapper.get('[data-player-library="artists"]').attributes('disabled')).toBeUndefined()
    expect(h.requests.every(request => request.init?.method === 'GET')).toBe(true)
  } finally { h.wrapper.unmount() }
})
