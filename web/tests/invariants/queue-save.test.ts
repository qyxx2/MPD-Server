import { expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { shellPageWithSongReads as shellPage } from '../support/shell'
import { playerState } from '../support/player'
import { deferred } from '../support/transport'
const playlist = { playlist_id: 'saved', name: '手机保存', created_at: '2026-10-11T00:00:00Z', updated_at: '2026-10-11T00:00:00Z', is_system: false, song_ids: ['song-b', 'hidden-song'] }
async function form(h: Awaited<ReturnType<typeof shellPage>>, name = '手机保存') {
  await h.router.push('/queue'); await flushPromises()
  await h.wrapper.get('[data-queue-save]').trigger('click')
  await h.wrapper.get('input[aria-label="Playlist 名称"]').setValue(name)
}
it('save_submits_only_name_reads_authoritative_playlist_list_without_committing_visible_rows', async () => {
  const s = playerState(), response = deferred<Response>()
  s.queue.items.push({ ...s.queue.items[1]!, queue_item_id: 'hidden-occurrence', song_id: 'hidden-song', position: 2 })
  const h = await shellPage(response.promise, Response.json(s), Response.json({ items: [playlist], count: 1 }))
  h.store.acceptRefresh(s, 1); await form(h)
  const baseline = h.store.snapshot
  await h.wrapper.get('[data-save-form]').trigger('submit')
  expect(h.network.requests[0]?.url).toContain('/queue/save-as-playlist')
  expect(JSON.parse(h.network.requests[0]!.init!.body as string)).toEqual({ name: '手机保存' })
  expect(h.store.snapshot).toBe(baseline)
  response.resolve(Response.json(playlist)); await flushPromises()
  expect(h.network.requests.map(r => new URL(r.url).pathname)).toEqual(['/api/playback/queue/save-as-playlist', '/api/state', '/api/playlists'])
  expect(h.tasks.entries.value[0]?.state).toBe('confirmed')
  expect(h.wrapper.find('[data-save-form]').exists()).toBe(false)
  expect(h.wrapper.get('.status-toggle').attributes('aria-label')).toBe('查看最近活动')
  expect(h.wrapper.text()).toContain('已同步')
  h.wrapper.unmount()
})
it('duplicate_rejection_keeps_name_and_queue_and_leaving_discards_unsent_draft', async () => {
  const s = playerState(), h = await shellPage(Response.json({ error: { code: 'PLAYBACK_REQUEST_INVALID', message: 'Queue Up Next contains duplicate songs' } }, { status: 400 }), Response.json(s), Response.json({ items: [], count: 0 }))
  await form(h); const baseline = h.store.snapshot
  await h.wrapper.get('[data-save-form]').trigger('submit'); await flushPromises()
  expect(h.tasks.entries.value[0]?.state).toBe('failed')
  expect(h.wrapper.get('input').element.value).toBe('手机保存')
  expect(h.store.snapshot).toBe(baseline)
  expect(h.tasks.entries.value[0]?.retry).toBeUndefined()
  await h.router.push('/library'); await h.router.push('/queue'); await flushPromises()
  expect(h.wrapper.find('[data-save-form]').exists()).toBe(false)
  await h.wrapper.get('[data-queue-save]').trigger('click')
  expect(h.wrapper.get('input').element.value).toBe('')
  h.wrapper.unmount()
})
it('unknown_save_survives_route_and_retries_original_name_key_once', async () => {
  const s = playerState(), h = await shellPage(new Error('lost'), Response.json(playlist), Response.json(s), Response.json({ items: [playlist], count: 1 }))
  await form(h); await h.wrapper.get('[data-save-form]').trigger('submit'); await flushPromises()
  const original = h.network.requests[0]!
  await h.router.push('/library'); await flushPromises()
  await h.tasks.retry(h.tasks.entries.value[0]!.intent.key); await flushPromises()
  expect(h.network.requests[1]?.init).toEqual(original.init)
  expect(h.tasks.entries.value[0]?.state).toBe('confirmed')
  h.wrapper.unmount()
})
it('confirmed_save_list_read_failure_recovers_only_by_read_and_empty_offline_never_sends', async () => {
  const s = playerState(), h = await shellPage(Response.json(s), Response.json(playlist), Response.json(s), new Error('list lost'), Response.json(s), Response.json({ items: [playlist], count: 1 }))
  await form(h, ' ')
  await h.wrapper.get('[data-save-form]').trigger('submit'); expect(h.network.requests).toHaveLength(0)
  await h.wrapper.get('input').setValue('手机保存'); h.store.markDisconnected(); await flushPromises()
  await h.wrapper.get('[data-save-form]').trigger('submit'); expect(h.network.requests).toHaveLength(0)
  h.store.beginConnection(2); h.store.acceptInitial(s, 2); await flushPromises()
  await h.wrapper.get('[data-save-form]').trigger('submit'); await flushPromises()
  expect(h.tasks.entries.value[0]?.readFailed).toBe(true)
  await h.tasks.entries.value[0]!.read(); await flushPromises()
  expect(h.network.requests.filter(r => r.init?.method === 'POST')).toHaveLength(1)
  expect(h.tasks.entries.value[0]?.readFailed).toBe(false)
  h.wrapper.unmount()
})
it('real_playlist_wire_and_malformed_receipts_fail_closed', async () => {
  const { parsePlaylist, parsePlaylistList } = await import('../../src/services/resourceWire')
  const fixture = (await import('../fixtures/wire.json')).default
  expect(parsePlaylist(fixture.playlist_resource).song_ids).toEqual(['song-b', 'hidden-song'])
  expect(parsePlaylistList(fixture.playlist_list_resource).items[0]?.playlist_id).toBe('playlist-wire')
  expect(() => parsePlaylist({ ...playlist, song_ids: ['song-b', null] })).toThrow()
  expect(() => parsePlaylistList({ items: [playlist], count: -1 })).toThrow()
  const h = await shellPage(Response.json({ playlist_id: 'partial' }))
  await form(h); await h.wrapper.get('[data-save-form]').trigger('submit'); await flushPromises()
  expect(h.tasks.entries.value[0]?.state).toBe('unknown')
  expect(h.wrapper.get('input').element.value).toBe('手机保存')
  expect(h.network.requests).toHaveLength(1)
  h.wrapper.unmount()
})
it('same_page_unknown_save_recovery_closes_original_form_without_second_intent', async () => {
  const s = playerState(), h = await shellPage(new Error('lost'), Response.json(playlist), Response.json(s), Response.json({ items: [playlist], count: 1 }))
  await form(h); await h.wrapper.get('[data-save-form]').trigger('submit'); await flushPromises()
  expect(h.wrapper.find('[data-save-form]').exists()).toBe(true)
  await h.tasks.retry(h.tasks.entries.value[0]!.intent.key); await flushPromises()
  expect(h.wrapper.find('[data-save-form]').exists()).toBe(false)
  await h.wrapper.get('[data-queue-save]').trigger('click')
  expect(h.wrapper.get('input').element.value).toBe('')
  expect(h.network.requests.filter(r => r.init?.method === 'POST')).toHaveLength(2)
  expect(h.network.requests[1]?.init?.headers).toEqual(h.network.requests[0]?.init?.headers)
  h.wrapper.unmount()
})
