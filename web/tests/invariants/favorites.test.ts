import { expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import playlistWire from '../fixtures/playlists.json'
import { libraryPage, wire } from '../support/library'
import { deferred } from '../support/transport'
import { playerState } from '../support/player'
async function page(mode = '', path = '/library?kind=songs') {
  let members = ['c', 'a'], writes = 0, readFailure = false
  const late = deferred<Response>()
  const h = await libraryPage(path, (path, init) => {
    if (path.startsWith('/api/library/songs/')) { const id = path.split('/').at(-1)!; const song = wire.songs.items.find(s => s.song_id === id); if (song) return Promise.resolve(Response.json(song)) }
    if (path.startsWith('/api/playlists/')) return Promise.resolve(Response.json(path.endsWith('/songs') ? playlistWire.songs : playlistWire.detail))
    if (path.startsWith('/api/library/search/results?')) return Promise.resolve(Response.json({ groups: [], song_ids: ['a', 'b'] }))
    if (path === '/api/playback/collections/play') return Promise.resolve(Response.json(null))
    if (!path.startsWith('/api/favorites')) return undefined
    if (init?.method === 'PUT' || init?.method === 'DELETE') {
      writes++
      if (mode === 'unknown' && writes === 1) return Promise.reject(new TypeError('lost ACK'))
      if (mode === 'pending') return late.promise
      if (mode === 'failure') return Promise.resolve(Response.json({ error: { code: 'FAV_FAILED', message: 'rejected' } }, { status: 409 }))
      const id = path.split('/').at(-1)!
      members = init.method === 'DELETE' ? members.filter(i => i !== id) : [id, ...members]
      readFailure = mode === 'readFailure'
      return Promise.resolve(init.method === 'DELETE' ? new Response(null, { status: 204 }) : Response.json({ source_type: 'FAVORITES', source_id: null, song_ids: members.filter(i => i !== 'c'), unavailable_song_ids: members.filter(i => i === 'c'), random_seed: null }))
    }
    if (path === '/api/favorites/members') return Promise.resolve(readFailure ? Response.json({}, { status: 500 }) : Response.json({ song_ids: members }))
    return undefined
  })
  return { ...h, late, setMembers(ids: string[]) { members = ids }, restoreRead() { readFailure = false } }
}
it('unavailable_membership_and_cross_view_stars', async () => {
  const h = await page()
  expect(h.wrapper.findAll('[data-favorite-display]').map(e => e.attributes('data-favorite-display'))).toEqual(['a', 'c'])
  expect(h.wrapper.find('[data-song-id="b"] [data-favorite-display]').exists()).toBe(false)
  await h.wrapper.get('[data-song-id="c"] .song-open').trigger('click'); await flushPromises()
  expect(h.wrapper.get('[data-favorite-toggle="c"]').attributes('disabled')).toBeUndefined()
  await h.wrapper.get('[data-favorite-toggle="c"]').trigger('click'); await flushPromises()
  expect(h.requests.filter(r => r.path.startsWith('/api/playback'))).toHaveLength(0)
  await h.router.push('/library/favorites'); await flushPromises()
  expect(h.wrapper.findAll('[data-song-id]').map(e => e.attributes('data-song-id'))).toEqual(['a'])
  await h.router.push('/'); await flushPromises()
  expect(h.wrapper.find('[data-favorite-toggle]').exists()).toBe(true)
  h.wrapper.unmount()
})
it('failure_and_unknown_do_not_speculate_membership', async () => {
  const h = await page('unknown')
  await h.wrapper.get('[data-song-id="a"] .song-open').trigger('click'); await flushPromises()
  await h.wrapper.get('[data-favorite-toggle="a"]').trigger('click'); await flushPromises()
  expect(h.wrapper.find('[data-favorite-display="a"]').exists()).toBe(true)
  await h.router.push('/library/favorites'); await flushPromises()
  expect(h.requests.filter(r => r.init?.method === 'DELETE')).toHaveLength(1)
  await h.wrapper.get('[data-song-id="a"] .song-open').trigger('click'); await flushPromises()
  expect(h.wrapper.get('[data-favorite-toggle="a"]').attributes('disabled')).toBeDefined()
  h.store.markDisconnected(1); await h.tasks.entries.value[0]!.retry!()
  expect(h.requests.filter(r => r.init?.method === 'DELETE')).toHaveLength(1)
  h.store.beginConnection(2); h.store.acceptInitial(playerState(), 2)
  await h.tasks.entries.value[0]!.retry!(); await flushPromises()
  const writes = h.requests.filter(r => r.init?.method === 'DELETE')
  expect(writes).toHaveLength(2)
  expect(new Headers(writes[0]!.init?.headers).get('Idempotency-Key')).toBe(new Headers(writes[1]!.init?.headers).get('Idempotency-Key'))
  expect(h.wrapper.find('[data-song-id="a"]').exists()).toBe(false)
  h.wrapper.unmount()
  const failed = await page('failure')
  await failed.wrapper.get('[data-song-id="a"] .song-open').trigger('click'); await flushPromises()
  await failed.wrapper.get('[data-favorite-toggle="a"]').trigger('click'); await flushPromises()
  expect(failed.wrapper.find('[data-favorite-display="a"]').exists()).toBe(true)
  expect(failed.wrapper.get('[data-testid="operation-status"]').text()).toContain('FAV_FAILED')
  failed.wrapper.unmount()
})
it('both_revisions_read_and_confirmed_204_read_failure_never_resends', async () => {
  const h = await page('readFailure')
  for (const domain of ['library', 'playlist'] as const) {
    h.setMembers(domain === 'library' ? ['b'] : ['a', 'c'])
    const s = playerState(); s.sequence = h.store.marker.sequence + 1; s.revisions = { ...h.store.marker.revisions, [domain]: h.store.marker.revisions[domain] + 1 }
    h.store.invalidate({ type: 'invalidate', protocol_version: 1, epoch: s.epoch, sequence: s.sequence, domains: [domain], revisions: s.revisions }, 1)
    await flushPromises()
    expect(h.wrapper.find(`[data-favorite-display="${domain === 'library' ? 'b' : 'a'}"]`).exists()).toBe(true)
  }
  await h.wrapper.get('[data-song-id="a"] .song-open').trigger('click'); await flushPromises()
  await h.wrapper.get('[data-favorite-toggle="a"]').trigger('click'); await flushPromises()
  const record = h.tasks.entries.value[0]!
  expect(record.state).toBe('confirmed'); expect(record.readFailed).toBe(true); expect(record.retry).toBeUndefined()
  h.restoreRead(); await record.read(); await flushPromises()
  expect(h.requests.filter(r => r.init?.method === 'DELETE')).toHaveLength(1)
  expect(h.wrapper.find('[data-favorite-display="a"]').exists()).toBe(false)
  h.wrapper.unmount()
})
it('pending_same_song_and_epoch_retire_receipt_without_optimistic_state', async () => {
  const h = await page('pending')
  await h.wrapper.get('[data-song-id="a"] .song-open').trigger('click'); await flushPromises()
  await h.wrapper.get('[data-favorite-toggle="a"]').trigger('click'); await flushPromises()
  expect(h.wrapper.find('[data-favorite-display="a"]').exists()).toBe(true)
  expect(h.wrapper.get('[data-favorite-toggle="a"]').attributes('disabled')).toBeDefined()
  await h.wrapper.get('[data-favorite-toggle="a"]').trigger('click'); await flushPromises()
  expect(h.requests.filter(r => r.init?.method === 'DELETE')).toHaveLength(1)
  await h.router.push('/settings'); await flushPromises()
  const next = playerState(); next.epoch = 'new-favorites-epoch'; h.store.beginConnection(2); h.store.acceptInitial(next, 2)
  h.late.resolve(new Response(null, { status: 204 })); await flushPromises()
  expect(h.tasks.entries.value[0]!.state).toBe('retired')
  await h.router.push('/library?kind=songs'); await flushPromises()
  expect(h.wrapper.find('[data-favorite-display="a"]').exists()).toBe(true)
  expect(h.requests.filter(r => r.init?.method === 'DELETE')).toHaveLength(1)
  h.wrapper.unmount()
})
it('favorites_full_order_and_collection_playback_use_server_source', async () => {
  const h = await page('', '/library/favorites')
  expect(h.wrapper.findAll('[data-song-id]').map(e => e.attributes('data-song-id'))).toEqual(['c', 'a'])
  await h.wrapper.get('[data-play-all]').trigger('click'); await flushPromises()
  const write = h.requests.find(r => r.path === '/api/playback/collections/play')!
  expect(JSON.parse(String(write.init?.body))).toMatchObject({ source_type: 'FAVORITES', randomize: false })
  expect(h.wrapper.findAll('[data-song-id]').map(e => e.attributes('data-song-id'))).toEqual(['c', 'a'])
  h.wrapper.unmount()
})

it('cross_view_hearts_are_display_only_and_player_or_menu_toggle_never_plays', async () => {
  const h = await page()
  h.setMembers(['a', 'c', 'song-a'])
  const state = playerState(); state.sequence++; state.revisions.playlist++
  h.store.invalidate({ type: 'invalidate', protocol_version: 1, epoch: state.epoch, sequence: state.sequence, domains: ['playlist'], revisions: state.revisions }, 1)
  await flushPromises()
  for (const path of ['/library/playlists/p', '/library/search?q=夜航', '/queue']) {
    await h.router.push(path); await flushPromises()
    expect(h.wrapper.find(`[data-favorite-display="${path === '/queue' ? 'song-a' : 'a'}"]`).exists()).toBe(true)
    expect(h.wrapper.find('[data-favorite-toggle]').exists()).toBe(false)
  }
  await h.wrapper.get('[data-favorite-display="song-a"]').trigger('click'); await flushPromises()
  expect(h.requests.filter(r => r.path.startsWith('/api/playback'))).toHaveLength(0)
  await h.wrapper.get('.queue-more').trigger('click'); await flushPromises()
  expect(h.wrapper.findAll('[data-favorite-toggle]')).toHaveLength(1)
  await h.wrapper.get('[data-favorite-toggle]').trigger('click'); await flushPromises()
  expect(h.requests.filter(r => r.path.startsWith('/api/playback'))).toHaveLength(0)
  await h.router.push('/'); await flushPromises()
  const heart = h.wrapper.get('[data-favorite-toggle]')
  expect(heart.attributes('aria-pressed')).toBe('false')
  await heart.trigger('click'); await flushPromises()
  expect(h.wrapper.get('[data-favorite-toggle]').attributes('aria-pressed')).toBe('true')
  expect(h.requests.filter(r => r.path.startsWith('/api/playback'))).toHaveLength(0)
  h.wrapper.unmount()
})
it('membership_late_response_is_rejected_and_metadata_failure_keeps_cancel_in_menu', async () => {
  const late = deferred<Response>(); let reads = 0
  const h = await libraryPage('/library/favorites', (path) => {
    if (path === '/api/favorites/members') return ++reads === 1 ? late.promise : Promise.resolve(Response.json({ song_ids: ['c'] }))
    if (path === '/api/library/songs/c') return Promise.resolve(Response.json({}, { status: 500 }))
    return undefined
  })
  const state = playerState(); state.sequence++; state.revisions.playlist++
  h.store.invalidate({ type: 'invalidate', protocol_version: 1, epoch: state.epoch, sequence: state.sequence, domains: ['playlist'], revisions: state.revisions }, 1)
  await flushPromises(); late.resolve(Response.json({ song_ids: ['a'] })); await flushPromises()
  expect(h.wrapper.find('[data-favorite-display="a"]').exists()).toBe(false)
  expect(h.wrapper.find('[data-favorite-display="c"]').exists()).toBe(true)
  expect(h.wrapper.find('[data-favorite-toggle]').exists()).toBe(false)
  expect(h.wrapper.get('[data-testid="operation-status"]').text()).toContain('c')
  document.body.appendChild(h.wrapper.element)
  const opener = h.wrapper.get('.song-row > button')
  await opener.trigger('click'); await flushPromises()
  expect(document.activeElement).toBe(h.wrapper.get('[data-favorite-toggle="c"]').element)
  await h.wrapper.get('.song-menu').trigger('keydown', { key: 'Escape' }); await flushPromises()
  expect(document.activeElement).toBe(opener.element)
  await opener.trigger('click'); await flushPromises()
  expect(h.wrapper.get('[data-favorite-toggle="c"]').attributes('disabled')).toBeUndefined()
  h.wrapper.unmount()
})

it('real_server_membership_fixture_decodes_full_order_and_rejects_duplicates', async () => {
  const { parsePlaylistResource } = await import('../../src/services/resourceWire')
  const { default: fixture } = await import('../fixtures/favorites.json')
  expect(parsePlaylistResource(fixture, '/api/favorites/members')).toEqual({ song_ids: ['c', 'b', 'a'] })
  expect(() => parsePlaylistResource({ song_ids: ['a', 'a'] }, '/api/favorites/members')).toThrow()
  expect(() => parsePlaylistResource({ song_ids: [''] }, '/api/favorites/members')).toThrow()
})
it('player_retained_handoff_identity_cannot_be_favorite_mutation_target', async () => {
  const h = await page('', '/')
  const { fixture } = await import('../support/player')
  const { default: stateFixture } = await import('../fixtures/wire.json')
  // An in-flight Player action retains presentation while its new state is unknown.
  const late = deferred<Response>()
  const original = h.api.send
  h.api.send = ((intent: Parameters<typeof original>[0], decode: Parameters<typeof original>[1]) => intent.path === '/api/playback/resume' ? late.promise.then(async response => decode(await response.json())) : original(intent, decode)) as typeof original
  await h.wrapper.get('button[aria-label="继续播放"]').trigger('click')
  const unknown = playerState(); unknown.sequence++
  Object.assign(unknown.playback_observation, stateFixture.empty_snapshot.playback_observation)
  h.store.acceptRefresh(unknown, 1); await flushPromises()
  expect(h.wrapper.get('[data-testid="actual-identity"]').text()).toContain('Song A')
  expect(h.wrapper.get('[data-favorite-toggle]').attributes('disabled')).toBeDefined()
  await h.wrapper.get('[data-favorite-toggle]').trigger('click'); await flushPromises()
  expect(h.requests.filter(r => r.path.startsWith('/api/favorites/') && r.init?.method !== 'GET')).toHaveLength(0)
  late.resolve(Response.json(fixture.playback_receipt)); await flushPromises()
  h.wrapper.unmount()
})
