import { expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { libraryPage, wire } from '../support/library'
import playlistWire from '../fixtures/playlists.json'
import { playerState } from '../support/player'
import { deferred } from '../support/transport'
const initial = () => structuredClone(playlistWire.detail)
async function page(path = '/library/playlists/p', mode = '') {
  let playlist = initial(), exists = true, attempts = 0
  const late = deferred<Response>()
  const h = await libraryPage(path, (path, init) => {
    const method = init?.method ?? 'GET'
    if (!path.startsWith('/api/playlists')) return undefined
    if (method !== 'GET') {
      if (mode === 'unknown' && ++attempts === 1) return Promise.reject(new TypeError('lost ACK'))
      if (mode === 'pending') return late.promise
      const body = init?.body ? JSON.parse(String(init.body)) : {}
      if (method === 'POST' && path.endsWith('/songs')) return Promise.resolve(Response.json({ error: { code: 'DUPLICATE_PLAYLIST_SONG', message: 'duplicate' } }, { status: 409 }))
      if (method === 'PATCH') playlist = { ...playlist, name: body.name }
      if (method === 'PUT') playlist = { ...playlist, song_ids: body.ordered_song_ids }
      if (method === 'DELETE' && path.endsWith('/songs/c')) playlist = { ...playlist, song_ids: playlist.song_ids.filter(id => id !== 'c') }
      else if (method === 'DELETE') exists = false
      if (method === 'POST' && path === '/api/playlists') { playlist = { ...playlist, name: body.name, song_ids: [] }; exists = true }
      return Promise.resolve(method === 'DELETE' ? new Response(null, { status: 204 }) : Response.json(playlist))
    }
    if (path === '/api/playlists') return Promise.resolve(Response.json({ items: exists ? [playlist] : [], count: exists ? 1 : 0 }))
    if (path.endsWith('/songs')) return Promise.resolve(Response.json({ items: playlist.song_ids.map(id => wire.songs.items.find(s => s.song_id === id)), count: playlist.song_ids.length }))
    return Promise.resolve(Response.json(mode === 'system' ? { ...playlist, is_system: true } : playlist))
  })
  return { ...h, late, setMembers(ids: string[]) { playlist = { ...playlist, song_ids: ids } } }
}
it('full_membership_includes_unavailable_and_duplicate_is_rejected', async () => {
  const h = await page()
  expect(h.wrapper.findAll('[data-playlist-member]').map(r => r.attributes('data-playlist-member'))).toEqual(['b', 'c', 'a'])
  expect(h.wrapper.text()).toContain('MISSING')
  await h.wrapper.get('[data-song-id="b"] .song-open').trigger('click'); await flushPromises()
  expect(h.requests.filter(r => r.init?.method === 'POST')).toHaveLength(0)
  await h.wrapper.get('.song-menu').trigger('keydown', { key: 'Escape' })
  await h.wrapper.get('[data-add-songs]').trigger('click'); await flushPromises()
  await h.wrapper.get('[data-add-song="b"]').trigger('click'); await flushPromises()
  expect(h.wrapper.findAll('[data-playlist-member]')).toHaveLength(3)
  expect(h.wrapper.get('[data-testid="operation-status"]').text()).toContain('DUPLICATE_PLAYLIST_SONG')
  h.wrapper.unmount()
})
it('draft_and_confirmed_mutation_have_distinct_lifetimes', async () => {
  const h = await page()
  document.body.appendChild(h.wrapper.element)
  await h.wrapper.get('[data-reorder="c"]').trigger('pointerdown', { pointerId: 1, clientY: 70, button: 0 })
  await h.wrapper.get('[data-playlist-member="b"]').trigger('pointermove', { pointerId: 1, clientY: 0 })
  await h.wrapper.get('[data-playlist-member="b"]').trigger('pointerup', { pointerId: 1, clientY: 0 }); await flushPromises()
  const write = h.requests.find(r => r.init?.method === 'PUT')!
  expect(JSON.parse(String(write.init?.body))).toEqual({ ordered_song_ids: ['c', 'b', 'a'] })
  expect(h.wrapper.findAll('[data-playlist-member]').map(r => r.attributes('data-playlist-member'))).toEqual(['c', 'b', 'a'])
  await h.wrapper.get('[data-remove-song="c"]').trigger('click'); await flushPromises()
  expect(h.wrapper.findAll('[data-playlist-member]').map(r => r.attributes('data-playlist-member'))).toEqual(['b', 'a'])
  await h.wrapper.get('[data-rename]').trigger('click'); await h.wrapper.get('[data-playlist-name]').setValue('丢弃草稿')
  await h.router.push('/settings'); await flushPromises(); await h.router.push('/library/playlists/p'); await flushPromises()
  expect(h.wrapper.find('[data-playlist-name]').exists()).toBe(false)
  await h.wrapper.get('[data-reorder="a"]').trigger('pointerdown', { pointerId: 2, clientY: 70, button: 0 })
  const state = playerState(); state.sequence++; state.revisions.playlist++
  h.store.invalidate({ type: 'invalidate', protocol_version: 1, epoch: state.epoch, sequence: state.sequence, domains: ['playlist'], revisions: state.revisions }, 1)
  await flushPromises()
  await h.wrapper.get('[data-playlist-member="b"]').trigger('pointerup', { pointerId: 2, clientY: 0 }); await flushPromises()
  expect(h.requests.filter(r => r.init?.method === 'PUT')).toHaveLength(1)
  h.wrapper.unmount()
})
it('system_protection_and_empty_playlist_crud', async () => {
  const system = await page('/library/playlists/p', 'system')
  expect(system.wrapper.find('[data-rename]').exists()).toBe(false); expect(system.wrapper.find('[data-delete-playlist]').exists()).toBe(false)
  system.wrapper.unmount()
  const h = await page('/library/playlists')
  await h.wrapper.get('[data-create-playlist]').trigger('click'); await h.wrapper.get('[data-playlist-name]').setValue('新建长名称')
  await h.wrapper.get('[data-submit-name]').trigger('submit'); await flushPromises()
  expect(h.wrapper.text()).toContain('新建长名称')
  await h.wrapper.get('[data-playlist-id="p"]').trigger('click'); await flushPromises()
  expect(h.wrapper.text()).toContain('暂无歌曲')
  await h.wrapper.get('[data-rename]').trigger('click'); await h.wrapper.get('[data-playlist-name]').setValue('已改名')
  await h.wrapper.get('[data-submit-name]').trigger('submit'); await flushPromises()
  expect(h.wrapper.text()).toContain('已改名')
  await h.wrapper.get('[data-delete-playlist]').trigger('click'); await h.wrapper.get('[data-confirm-delete]').trigger('click'); await flushPromises()
  expect(h.router.currentRoute.value.path).toBe('/library/playlists'); expect(h.wrapper.text()).toContain('暂无歌单')
  h.wrapper.unmount()
})
it('unknown_original_intent_survives_route_and_disconnect_without_optimistic_membership', async () => {
  const h = await page('/library/playlists/p', 'unknown')
  await h.wrapper.get('[data-remove-song="c"]').trigger('click'); await flushPromises()
  expect(h.wrapper.findAll('[data-playlist-member]')).toHaveLength(3)
  await h.router.push('/settings'); await flushPromises()
  h.store.markDisconnected(1); await h.tasks.entries.value[0]!.retry!(); await flushPromises()
  expect(h.requests.filter(r => r.init?.method === 'DELETE')).toHaveLength(1)
  h.store.beginConnection(2); h.store.acceptInitial(playerState(), 2)
  await h.tasks.entries.value[0]!.retry!(); await flushPromises()
  const writes = h.requests.filter(r => r.init?.method === 'DELETE')
  expect(writes).toHaveLength(2)
  expect(new Headers(writes[0]!.init?.headers).get('Idempotency-Key')).toBe(new Headers(writes[1]!.init?.headers).get('Idempotency-Key'))
  await h.router.push('/library/playlists/p'); await flushPromises()
  expect(h.wrapper.findAll('[data-playlist-member]').map(r => r.attributes('data-playlist-member'))).toEqual(['b', 'a'])
  h.wrapper.unmount()
})
it('revision_rejects_late_members_and_204_read_failure_only_recovers_by_read', async () => {
  const late = deferred<Response>(); let reads = 0, failRead = false
  const p = initial()
  const h = await libraryPage('/library/playlists/p', (path, init) => {
    if (!path.startsWith('/api/playlists')) return undefined
    if (init?.method === 'DELETE') { failRead = true; return Promise.resolve(new Response(null, { status: 204 })) }
    if (path === '/api/playlists') return Promise.resolve(failRead ? Response.json({ error: { code: 'READ_FAILED', message: 'read failed' } }, { status: 500 }) : Response.json({ items: [p], count: 1 }))
    if (path.endsWith('/songs')) return ++reads === 1 ? late.promise : Promise.resolve(Response.json({ items: wire.songs.items.map(s => ({ ...s, title: '最新 ' + s.title })).sort((a, b) => p.song_ids.indexOf(a.song_id!) - p.song_ids.indexOf(b.song_id!)), count: 3 }))
    return Promise.resolve(Response.json(p))
  })
  const state = playerState(); state.sequence++; state.revisions.library++
  h.store.invalidate({ type: 'invalidate', protocol_version: 1, epoch: state.epoch, sequence: state.sequence, domains: ['library'], revisions: state.revisions }, 1)
  await flushPromises(); late.resolve(Response.json({ items: p.song_ids.map(id => wire.songs.items.find(s => s.song_id === id)), count: 3 })); await flushPromises()
  expect(h.wrapper.findAll('[data-song-id]')[0]!.text()).toContain('最新')
  await h.wrapper.get('[data-remove-song="c"]').trigger('click'); await flushPromises()
  const record = h.tasks.entries.value[0]!
  expect(record.state).toBe('confirmed'); expect(record.readFailed).toBe(true); expect(record.retry).toBeUndefined()
  failRead = false; await record.read(); await flushPromises()
  expect(h.requests.filter(r => r.init?.method === 'DELETE')).toHaveLength(1)
  expect(h.tasks.entries.value[0]!.readFailed).toBe(false)
  h.wrapper.unmount()
})
it('reorder_conflict_preserves_server_members_and_route_or_invalid_drop_cancels_draft', async () => {
  const p = initial()
  let conflict = false
  const h = await libraryPage('/library/playlists/p', (path, init) => {
    if (!path.startsWith('/api/playlists')) return undefined
    if (init?.method === 'PUT') { conflict = true; return Promise.resolve(Response.json({ error: { code: 'PLAYLIST_REORDER_MEMBER_MISMATCH', message: 'members changed' } }, { status: 409 })) }
    const actual = conflict ? { ...p, song_ids: ['b', 'c'] } : p
    if (path.endsWith('/songs')) return Promise.resolve(Response.json({ items: actual.song_ids.map(id => wire.songs.items.find(s => s.song_id === id)), count: actual.song_ids.length }))
    return Promise.resolve(Response.json(path === '/api/playlists' ? { items: [actual], count: 1 } : actual))
  })
  document.body.appendChild(h.wrapper.element)
  await h.wrapper.get('[data-reorder="c"]').trigger('pointerdown', { pointerId: 1, button: 0 })
  await h.wrapper.get('[data-playlist-member="b"]').trigger('pointerup', { pointerId: 1, clientY: 0 }); await flushPromises()
  expect(h.wrapper.findAll('[data-playlist-member]').map(r => r.attributes('data-playlist-member'))).toEqual(['b', 'c'])
  expect(h.wrapper.get('[data-testid="operation-status"]').text()).toContain('PLAYLIST_REORDER_MEMBER_MISMATCH')
  await h.wrapper.get('[data-reorder="c"]').trigger('pointerdown', { pointerId: 2, button: 0 })
  await h.router.push('/settings'); await flushPromises()
  window.dispatchEvent(new Event('pointerup')); await flushPromises()
  expect(h.requests.filter(r => r.init?.method === 'PUT')).toHaveLength(1)
  await h.router.push('/library/playlists/p'); await flushPromises()
  await h.wrapper.get('[data-reorder="c"]').trigger('pointerdown', { pointerId: 3, button: 0 })
  await h.wrapper.get('[data-playlist-member="b"]').trigger('pointermove', { pointerId: 3, clientY: 0 })
  window.dispatchEvent(Object.assign(new Event('pointerup'), { pointerId: 3, clientY: 0, clientX: 0 })); await flushPromises()
  expect(h.requests.filter(r => r.init?.method === 'PUT')).toHaveLength(1)
  h.wrapper.unmount()
})
it('pending_add_is_never_optimistic_and_epoch_retires_its_receipt', async () => {
  const h = await page('/library/playlists/p', 'pending')
  await h.wrapper.get('[data-add-songs]').trigger('click'); await flushPromises()
  await h.wrapper.get('[data-add-song="c"]').trigger('click'); await flushPromises()
  expect(h.wrapper.findAll('[data-playlist-member]')).toHaveLength(3)
  expect(h.wrapper.get('[data-remove-song="b"]').attributes('disabled')).toBeDefined()
  await h.router.push('/settings'); await flushPromises()
  const next = playerState(); next.epoch = 'new-epoch'; h.store.beginConnection(2); h.store.acceptInitial(next, 2)
  h.late.resolve(Response.json({ ...initial(), name: '旧回执名称' })); await flushPromises()
  expect(h.tasks.entries.value[0]!.state).toBe('retired'); expect(h.tasks.entries.value[0]!.retry).toBeUndefined()
  await h.router.push('/library/playlists/p'); await flushPromises()
  expect(h.wrapper.text()).not.toContain('旧回执名称')
  expect(h.requests.filter(r => r.init?.method === 'POST')).toHaveLength(1)
  h.wrapper.unmount()
})
it('real_playlist_dto_decoding_requires_identity_and_full_unique_members', async () => {
  const { parsePlaylistResource } = await import('../../src/services/resourceWire')
  const detail = parsePlaylistResource(playlistWire.detail, '/api/playlists/p')
  expect(detail).toMatchObject({ playlist_id: 'p', song_ids: ['b', 'c', 'a'] })
  const songs = parsePlaylistResource(playlistWire.songs, '/api/playlists/p/songs')
  expect(songs).toMatchObject({ count: 3, items: [{ song_id: 'b' }, { song_id: 'c', availability_status: 'MISSING' }, { song_id: 'a' }] })
  expect(() => parsePlaylistResource(playlistWire.detail, '/api/playlists/wrong')).toThrow()
  expect(() => parsePlaylistResource({ ...playlistWire.detail, song_ids: ['b', 'b'] }, '/api/playlists/p')).toThrow()
  expect(() => parsePlaylistResource({ ...playlistWire.songs, count: 2 }, '/api/playlists/p/songs')).toThrow()
})
it('returning_drag_to_original_row_is_noop', async () => {
  const h = await page(); document.body.appendChild(h.wrapper.element)
  await h.wrapper.get('[data-reorder="c"]').trigger('pointerdown', { pointerId: 1, button: 0 })
  await h.wrapper.get('[data-playlist-member="b"]').trigger('pointermove', { pointerId: 1, clientY: 0 })
  await h.wrapper.get('[data-playlist-member="c"]').trigger('pointerup', { pointerId: 1, clientY: 0 }); await flushPromises()
  expect(h.requests.filter(r => r.init?.method === 'PUT')).toHaveLength(0)
  expect(h.wrapper.findAll('[data-playlist-member]').map(r => r.attributes('data-playlist-member'))).toEqual(['b', 'c', 'a'])
  h.wrapper.unmount()
})
