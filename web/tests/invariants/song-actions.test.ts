import { expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { libraryPage, wire } from '../support/library'
import { deferred } from '../support/transport'

const writes = (h: Awaited<ReturnType<typeof libraryPage>>) => h.requests.filter(r => r.init?.method !== 'GET')
async function openSongs(h: Awaited<ReturnType<typeof libraryPage>>) {
  await h.wrapper.get('[data-library-kind="songs"]').trigger('click'); await flushPromises()
}
it('ordinary_play_now_is_one_atomic_intent', async () => {
  const reply = deferred<Response>()
  const h = await libraryPage('/library', (path, init) => init?.method === 'POST' ? reply.promise : undefined)
  await openSongs(h)
  await h.wrapper.get('[data-song-id="a"] .song-open').trigger('click')
  expect(h.wrapper.get('.song-menu').text()).toContain(wire.songs.items[0]!.title)
  await h.wrapper.get('[data-song-action="now"]').trigger('click'); await flushPromises()
  expect(writes(h)).toHaveLength(1)
  expect(writes(h)[0]!.path).toBe('/api/playback/songs/a/play')
  expect(writes(h)[0]!.init?.body).toBeUndefined()
  expect(h.store.snapshot!.queue.items.map(i => i.queue_item_id)).toEqual(['item-a', 'item-b'])
  await h.router.push('/settings'); await flushPromises()
  reply.resolve(Response.json({ queue_item_id: 'new', song_id: 'a', position: 0, source: 'MANUAL', playback_context_id: 'ctx' })); await flushPromises()
  expect(h.tasks.entries.value[0]!.state).toBe('confirmed')
  expect(h.realtime.refresh).toHaveBeenCalledTimes(1)
  expect(h.store.snapshot!.queue.items.map(i => i.queue_item_id)).toEqual(['item-a', 'item-b'])
  expect(writes(h)).toHaveLength(1)
  h.wrapper.unmount()
})
it('next_and_add_create_song_intents_unavailable_and_offline_do_not_write', async () => {
  const h = await libraryPage('/library', (path, init) => init?.method === 'POST' ? Promise.resolve(Response.json({ queue_item_id: 'new', song_id: 'a', position: 1, source: 'MANUAL', playback_context_id: null })) : undefined)
  await openSongs(h)
  for (const action of ['next', 'add']) {
    await h.wrapper.get('[data-song-id="a"] .song-open').trigger('click')
    await h.wrapper.get(`[data-song-action="${action}"]`).trigger('click'); await flushPromises()
  }
  expect(writes(h).map(r => r.path)).toEqual(['/api/playback/songs/a/play-next', '/api/playback/songs/a/queue'])
  expect(new Set(writes(h).map(r => new Headers(r.init?.headers).get('Idempotency-Key'))).size).toBe(2)
  await h.wrapper.get('[data-song-id="c"] .song-open').trigger('click')
  expect(h.wrapper.get('[data-song-action="now"]').attributes('disabled')).toBeDefined()
  expect(h.wrapper.get('.song-menu').text()).toContain('MISSING')
  expect(h.wrapper.find('[data-close-song]').exists()).toBe(false)
  await h.wrapper.get('.song-menu-backdrop').trigger('click')
  expect(h.wrapper.find('.song-menu').exists()).toBe(false)
  h.store.markDisconnected(); await flushPromises()
  await h.wrapper.get('[data-song-id="a"] .song-open').trigger('click')
  expect(h.wrapper.get('[data-song-action="next"]').attributes('disabled')).toBeDefined()
  expect(writes(h)).toHaveLength(2)
  h.wrapper.unmount()
})
it('unknown_keeps_original_key_across_routes_and_confirmed_read_failure_only_reads', async () => {
  let attempt = 0, failRead = true
  const h = await libraryPage('/library', (path, init) => {
    if (init?.method === 'POST') {
      if (++attempt === 1) return Promise.reject(new TypeError('lost ACK'))
      return Promise.resolve(Response.json({ queue_item_id: 'new', song_id: 'a', position: 0, source: 'MANUAL', playback_context_id: null }))
    }
    if (path === '/api/state' && failRead) return Promise.reject(new Error('read failed'))
  })
  await openSongs(h); await h.wrapper.get('[data-song-id="a"] .song-open').trigger('click')
  await h.wrapper.get('[data-song-action="now"]').trigger('click'); await flushPromises()
  await h.router.push('/settings'); await flushPromises()
  expect(h.tasks.entries.value[0]!.state).toBe('unknown')
  await h.tasks.entries.value[0]!.retry!(); await flushPromises()
  expect(new Headers(writes(h)[0]!.init?.headers).get('Idempotency-Key')).toBe(new Headers(writes(h)[1]!.init?.headers).get('Idempotency-Key'))
  expect(h.tasks.entries.value[0]!.readFailed).toBe(true)
  failRead = false; await h.tasks.entries.value[0]!.read(); await flushPromises()
  expect(writes(h)).toHaveLength(2); expect(h.tasks.entries.value[0]!.readFailed).toBe(false)
  h.wrapper.unmount()
})
it('unavailable_reason_uses_top_notice_and_menu_draft_dies_on_navigation', async () => {
  const h = await libraryPage()
  await openSongs(h); await h.wrapper.get('[data-song-id="c"] .song-open').trigger('click')
  await h.wrapper.get('.status-toggle').trigger('click')
  expect(h.wrapper.get('#playback-status-details').text()).toContain('MISSING')
  expect(writes(h)).toHaveLength(0)
  await h.router.push('/settings'); await flushPromises()
  expect(h.wrapper.find('.song-menu').exists()).toBe(false)
  h.wrapper.unmount()
})
it('queue_target_dispatch_and_favorite_slot_are_independent', async () => {
  const { createSongActions } = await import('../../src/components/library/songActions')
  const { default: SongRow } = await import('../../src/components/library/SongRow.vue')
  const { h: node } = await import('vue')
  const h = await libraryPage('/settings', (path, init) => init?.method === 'POST'
    ? Promise.resolve(Response.json({ queue_item_id: 'item-a', song_id: 'song-a', position: 0, source: 'MANUAL', playback_context_id: null })) : undefined,
    node(SongRow, { song: (await import('../support/player')).playerState().current_song! }, { favorite: () => node('button', { 'data-favorite-test': '' }, '☆') }))
  await h.wrapper.get('[data-favorite-test]').trigger('click'); await flushPromises()
  expect(h.wrapper.find('.song-menu').exists()).toBe(false); expect(writes(h)).toHaveLength(0)
  const actions = createSongActions(h.store, { api: h.api, refresh: h.realtime.refresh }, h.tasks, () => false)
  await actions.playNow({ song_id: 'song-a', queue_item_id: 'item-a' }, 'Queue occurrence'); await flushPromises()
  expect(writes(h).map(r => r.path)).toEqual(['/api/playback/queue/items/item-a/play'])
  h.wrapper.unmount()
})
it('valid_but_wrong_song_receipt_stays_unknown_and_cannot_change_canonical', async () => {
  const h = await libraryPage('/library', (path, init) => init?.method === 'POST'
    ? Promise.resolve(Response.json({ queue_item_id: 'wrong', song_id: 'other', position: 0, source: 'MANUAL', playback_context_id: null })) : undefined)
  await openSongs(h); await h.wrapper.get('[data-song-id="a"] .song-open').trigger('click')
  await h.wrapper.get('[data-song-action="now"]').trigger('click'); await flushPromises()
  expect(h.tasks.entries.value[0]!.state).toBe('unknown')
  expect(h.store.snapshot!.current_song!.song_id).toBe('song-a')
  expect(h.realtime.refresh).not.toHaveBeenCalled()
  h.wrapper.unmount()
})
