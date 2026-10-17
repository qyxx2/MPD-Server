import { expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { libraryPage, wire } from '../support/library'
import { playerState } from '../support/player'
import { deferred } from '../support/transport'

it('album_header_separates_navigation_and_metadata_with_cover_fallback', async () => {
  const h = await libraryPage('/library?kind=albums')
  expect(h.wrapper.findAll('[data-library-kind]')[0]!.attributes('data-library-kind')).toBe('songs')
  await h.wrapper.get('[data-collection-id]').trigger('click'); await flushPromises()
  expect(h.wrapper.get('.library-back').find('svg').exists()).toBe(true)
  expect(h.wrapper.get('.album-summary').find('.library-back').exists()).toBe(false)
  expect(h.wrapper.get('.album-summary h2').text()).toBe('长专辑')
  expect(h.wrapper.get('.album-summary').text()).toContain('专辑艺术家')
  expect(h.wrapper.get('.album-summary').text()).toContain('2024')
  expect(h.wrapper.find('.album-cover-placeholder').exists()).toBe(true)
  h.wrapper.unmount()
})
it('album_cover_uses_member_artwork_and_recovers_from_failure_on_navigation', async () => {
  const artwork = { artwork_id: 'cover-b', source: 'EMBEDDED', picture_index: 0, mime_type: 'image/jpeg', width: null, height: null, content_sha256: null }
  let currentArtwork = artwork
  const h = await libraryPage('/library/albums/album-wire', path => path.endsWith('/songs')
    ? Promise.resolve(Response.json({ ...wire.album_songs, items: wire.album_songs.items.map(song => ({ ...song, artwork: currentArtwork })) })) : undefined)
  const originalSrc = h.wrapper.get('.album-cover img').attributes('src')
  const previousImage = h.wrapper.get('.album-cover img')
  expect(originalSrc).toMatch(/^\/api\/library\/songs\/b\/artwork(?:\?|$)/)
  currentArtwork = { ...artwork, artwork_id: 'replacement-cover' }
  const state = playerState(); state.sequence++; state.revisions.library++
  h.store.invalidate({ type: 'invalidate', protocol_version: 1, epoch: state.epoch, sequence: state.sequence, domains: ['library'], revisions: state.revisions }, 1)
  await flushPromises()
  expect(h.wrapper.get('.album-cover img').attributes('src')).not.toBe(originalSrc)
  await previousImage.trigger('error'); await flushPromises()
  expect(h.wrapper.find('.album-cover img').exists()).toBe(true)
  await h.wrapper.get('.album-cover img').trigger('error'); await flushPromises()
  expect(h.wrapper.find('.album-cover-placeholder').exists()).toBe(true)
  expect(h.wrapper.get('[data-testid="operation-status"]').text()).toContain('封面读取失败')
  await h.router.push('/library/albums/other'); await flushPromises()
  expect(h.wrapper.find('.album-cover img').exists()).toBe(true)
  expect(h.wrapper.get('[data-testid="operation-status"]').text()).not.toContain('封面读取失败')
  expect(h.requests.every(request => request.init?.method === 'GET')).toBe(true)
  h.wrapper.unmount()
})

it('category_identity_and_server_collection_play', async () => {
  const h = await libraryPage('/library', (path, init) => init?.method === 'POST' ? Promise.resolve(Response.json(playerState().playback)) : undefined)
  for (const [kind, source, id] of [
    ['albums', 'ALBUM', wire.albums.items[0]!.album_id], ['artists', 'ARTIST', wire.artists.items[0]!.artist_id],
    ['genres', 'GENRE', wire.genres.items[0]!.genre_id], ['years', 'YEAR', wire.years.items[0]!.source_id], ['tags', 'TAG', wire.tags.items[0]!.tag_id],
  ]) {
    await h.router.push('/library'); await flushPromises()
    await h.wrapper.get(`[data-library-kind="${kind}"]`).trigger('click'); await flushPromises()
    await h.wrapper.get('[data-collection-id]').trigger('click'); await flushPromises()
    expect(h.router.currentRoute.value.path).toBe(`/library/${kind}/${encodeURIComponent(id!)}`)
    expect(h.wrapper.findAll('[data-song-id]').map(row => row.attributes('data-song-id'))).toEqual(['b', 'a'])
    for (const randomize of [false, true]) {
      await h.wrapper.get(randomize ? '[data-shuffle-all]' : '[data-play-all]').trigger('click'); await flushPromises()
      const write = h.requests.filter(r => r.init?.method === 'POST').at(-1)!
      expect(write.path).toBe('/api/playback/collections/play')
      expect(JSON.parse(String(write.init?.body))).toEqual({ source_type: source, source_id: id, randomize })
    }
  }
  const count = h.requests.filter(r => r.init?.method === 'POST').length
  await h.router.push('/library'); await flushPromises(); await h.wrapper.get('[data-library-kind="songs"]').trigger('click'); await flushPromises()
  expect(h.wrapper.findAll('[data-song-id]')).toHaveLength(3)
  await h.wrapper.get('[data-play-all]').trigger('click'); await flushPromises()
  expect(JSON.parse(String(h.requests.filter(r => r.init?.method === 'POST').at(-1)!.init?.body))).toEqual({ source_type: 'LIBRARY', sort_by: 'title', sort_order: 'asc', randomize: false })
  expect(h.requests.filter(r => r.init?.method === 'POST')).toHaveLength(count + 1)
  h.wrapper.unmount()
})
it('empty_collection_never_plays_and_read_errors_are_only_top_notices', async () => {
  const h = await libraryPage('/library/albums/empty', (path) => path.endsWith('/empty/songs') ? Promise.resolve(Response.json({ items: [], count: 0 })) : undefined)
  expect(h.wrapper.text()).toContain('暂无歌曲')
  expect(h.wrapper.get('[data-play-all]').attributes('disabled')).toBeDefined()
  await h.wrapper.get('[data-play-all]').trigger('click'); await flushPromises()
  expect(h.requests.every(r => r.init?.method === 'GET')).toBe(true)
  h.wrapper.unmount()
  const error = await libraryPage('/library/albums/broken', (path) => path.endsWith('/broken/songs') ? Promise.resolve(Response.json({ error: { code: 'READ_FAILED', message: 'read resource failed' } }, { status: 500 })) : undefined)
  expect(error.wrapper.find('.library-content')?.text()).not.toContain('read resource failed')
  await error.wrapper.get('.status-toggle').trigger('click')
  expect(error.wrapper.get('#playback-status-details').text()).toContain('read resource failed')
  error.wrapper.unmount()
})
it('revision_and_route_changes_reject_late_resources_without_resetting_shell', async () => {
  const late = deferred<Response>(); let reads = 0
  const h = await libraryPage('/library/albums/album-wire', path => {
    if (path.endsWith('/album-wire/songs')) return ++reads === 1 ? late.promise : Promise.resolve(Response.json({ ...wire.album_songs, items: wire.album_songs.items.map(s => ({ ...s, title: '新标题' })) }))
  })
  const state = playerState(); state.sequence++; state.revisions.library++
  h.store.invalidate({ type: 'invalidate', protocol_version: 1, epoch: state.epoch, sequence: state.sequence, domains: ['library'], revisions: state.revisions }, 1)
  await flushPromises(); late.resolve(Response.json(wire.album_songs)); await flushPromises()
  expect(h.wrapper.text()).toContain('新标题'); expect(h.wrapper.text()).not.toContain('长标题 / b')
  await h.router.push('/library/genres/other'); await flushPromises()
  expect(h.realtime.start).toHaveBeenCalledTimes(1); expect(h.realtime.stop).not.toHaveBeenCalled()
  expect(h.requests.filter(r => r.init?.method === 'POST')).toHaveLength(0)
  h.wrapper.unmount()
})
it('actual_backend_category_and_collection_dtos_fail_closed', async () => {
  const { parseCategoryList, parseCollection, parseSongList } = await import('../../src/services/resourceWire')
  for (const kind of ['albums', 'artists', 'genres', 'years', 'tags'] as const) {
    const categories = parseCategoryList(wire[kind], kind)
    expect(categories.count).toBe(wire[kind].count)
    expect(categories.items[0]!.song_count).toBe(2)
    expect(() => parseCategoryList({ ...wire[kind], items: [{ ...wire[kind].items[0], song_count: '2' }] }, kind)).toThrow()
    expect(() => parseCategoryList({ ...wire[kind], items: [{ ...wire[kind].items[0], album_id: null, artist_id: null, genre_id: null, source_id: null, tag_id: null }] }, kind)).toThrow()
  }
  expect(parseCollection(wire.collection)).toMatchObject({ source_type: 'ALBUM', source_id: 'album-wire', song_ids: ['b', 'a'], unavailable_song_ids: ['c'] })
  expect(parseSongList(wire.songs).items[2]!.availability_status).toBe('MISSING')
  expect(() => parseCollection({ ...wire.collection, source_id: null })).toThrow()
})
it('shuffle_unknown_retry_retains_source_and_payload_without_rebuilding_order', async () => {
  let attempts = 0
  const h = await libraryPage('/library/albums/album-wire', (path, init) => init?.method === 'POST'
    ? ++attempts === 1 ? Promise.reject(new TypeError('lost ACK')) : Promise.resolve(Response.json(playerState().playback)) : undefined)
  await h.wrapper.get('[data-shuffle-all]').trigger('click'); await flushPromises()
  expect(h.wrapper.get('[data-play-all]').attributes('disabled')).toBeDefined()
  const ids = h.wrapper.findAll('[data-song-id]').map(row => row.attributes('data-song-id'))
  await h.router.push('/settings'); await flushPromises()
  await h.tasks.entries.value[0]!.retry!(); await flushPromises()
  const writes = h.requests.filter(r => r.init?.method === 'POST')
  expect(writes).toHaveLength(2); expect(writes[0]!.init?.body).toBe(writes[1]!.init?.body)
  expect(JSON.parse(String(writes[0]!.init?.body))).toEqual({ source_type: 'ALBUM', source_id: 'album-wire', randomize: true })
  expect(new Headers(writes[0]!.init?.headers).get('Idempotency-Key')).toBe(new Headers(writes[1]!.init?.headers).get('Idempotency-Key'))
  await h.router.push('/library/albums/album-wire'); await flushPromises()
  expect(h.wrapper.findAll('[data-song-id]').map(row => row.attributes('data-song-id'))).toEqual(ids)
  expect(h.requests.filter(r => r.path === '/api/library/collections')).toHaveLength(0)
  h.wrapper.unmount()
})
