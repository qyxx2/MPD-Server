import { expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { libraryPage } from '../support/library'
import { deferred } from '../support/transport'
import { playerState } from '../support/player'
import wire from '../fixtures/search.json'

function searchResponse(path: string) {
  const url = new URL(path, 'http://localhost')
  if (url.pathname === '/api/library/search/results') {
    const q = url.searchParams.get('q') ?? ''
    return Promise.resolve(Response.json(wire.results[q as keyof typeof wire.results] ?? wire.results['不存在']))
  }
  if (url.pathname === '/api/library/songs/a' || url.pathname === '/api/library/songs/b')
    return Promise.resolve(Response.json(wire.songs[url.pathname.endsWith('/a') ? 'a' : 'b']))
}
const ids = (h: Awaited<ReturnType<typeof libraryPage>>) => h.wrapper.findAll('[data-song-id]').map(row => row.attributes('data-song-id'))

it('category_icons_are_above_one_unique_list_in_first_server_occurrence_order', async () => {
  const groups = [...wire.results['长专辑'].groups, ...wire.results['专辑艺术家'].groups, ...wire.results['Rock'].groups, ...wire.results['2024'].groups, ...wire.results['Live'].groups, { kind: 'tags', source_id: 'empty', name: '空标签', song_ids: [] }]
  const h = await libraryPage('/library/search?q=multi', path => path === '/api/library/search/results?q=multi'
    ? Promise.resolve(Response.json({ groups, song_ids: ['c'] })) : path === '/api/library/songs/c' ? Promise.resolve(Response.json({ ...wire.songs.b, song_id: 'c' })) : searchResponse(path))
  expect(h.wrapper.find('[data-search-categories]').exists()).toBe(true)
  expect(h.wrapper.findAll('[data-search-category]').map(row => row.text())).toEqual(['长专辑', '专辑艺术家', 'Rock', '2024', 'Live', '空标签'])
  expect(h.wrapper.findAll('[data-search-category] svg path')).toHaveLength(6)
  expect(new Set(h.wrapper.findAll('[data-search-category] svg path').map(icon => icon.attributes('d'))).size).toBe(5)
  expect(h.wrapper.findAll('[data-search-group], .search-group-heading')).toHaveLength(0)
  expect(h.wrapper.findAll('.song-list')).toHaveLength(1)
  expect(ids(h)).toEqual(['b', 'a', 'c'])
  const top = h.wrapper.get('[data-search-categories]').element
  expect(Boolean(top.compareDocumentPosition(h.wrapper.get('.song-list').element) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true)
  expect(h.wrapper.findAll('.song-menu')).toHaveLength(0)
  expect(h.requests.every(r => r.init?.method === 'GET')).toBe(true)
  h.wrapper.unmount()
})

it('category_opens_only_its_collection_and_returns_to_unchanged_search', async () => {
  const groups = [
    { kind: 'albums', source_id: 'album/one', name: '专辑', song_ids: ['b', 'a'] },
    { kind: 'artists', source_id: 'artist/one', name: '艺术家', song_ids: ['a'] },
    { kind: 'tags', source_id: 'tag/one', name: '标签', song_ids: ['b'] },
  ]
  const h = await libraryPage('/library/search?q=multi', path => {
    if (path === '/api/library/search/results?q=multi') return Promise.resolve(Response.json({ groups, song_ids: [] }))
    const collection = groups.find(group => path === `/api/library/${group.kind}/${encodeURIComponent(group.source_id)}/songs`)
    if (collection) return Promise.resolve(Response.json({ items: collection.song_ids.map(id => wire.songs[id as 'a' | 'b']), count: collection.song_ids.length }))
    return searchResponse(path)
  })
  for (const [index, kind, id, expected] of [
    [0, 'albums', 'album/one', ['b', 'a']],
    [1, 'artists', 'artist/one', ['a']],
    [2, 'tags', 'tag/one', ['b']],
  ] as const) {
    expect(ids(h)).toEqual(['b', 'a'])
    await h.wrapper.findAll('[data-search-category]')[index]!.trigger('click'); await flushPromises()
    expect(h.router.currentRoute.value.path).toBe(`/library/${kind}/${encodeURIComponent(id)}`)
    expect(ids(h)).toEqual(expected)
    expect(h.wrapper.get('.library-back').text()).toContain('搜索')
    await h.wrapper.get('.song-open').trigger('click')
    expect(h.wrapper.findAll('[data-song-action]')).toHaveLength(3)
    await h.wrapper.get('.library-back').trigger('click'); await flushPromises()
    expect(h.router.currentRoute.value.fullPath).toBe('/library/search?q=multi')
    expect(ids(h)).toEqual(['b', 'a'])
  }
  expect(h.requests.every(r => r.init?.method === 'GET')).toBe(true)
  h.wrapper.unmount()
})

it('six_fields_empty_and_latest_query_only', async () => {
  const h = await libraryPage('/library/search', searchResponse)
  expect(h.wrapper.find('input[type="search"]').exists()).toBe(true)
  expect(ids(h)).toEqual([])
  expect(h.requests.some(r => r.path.startsWith('/api/library/search/results'))).toBe(false)
  for (const q of ['长标题', '长名', '长专辑', '专辑艺术家', 'Rock', '2024', 'Live']) {
    await h.wrapper.get('input').setValue(q); await flushPromises()
    expect(h.router.currentRoute.value.query.q).toBe(q)
    expect(ids(h)).toEqual(q === '长专辑' ? ['b', 'a'] : ['a', 'b'])
  }
  await h.wrapper.get('input').setValue('不存在'); await flushPromises()
  expect(ids(h)).toEqual([]); expect(h.wrapper.text()).toContain('没有匹配')
  await h.wrapper.get('input').setValue('   '); await flushPromises()
  expect(ids(h)).toEqual([])
  expect(h.requests.every(r => r.init?.method === 'GET')).toBe(true)
  expect(h.wrapper.find('[data-play-all]').exists()).toBe(false)
  h.wrapper.unmount()
  const late = deferred<Response>()
  const race = await libraryPage('/library/search?q=A', path => path === '/api/library/search/results?q=A' ? late.promise : path === '/api/library/search/results?q=B' ? Promise.resolve(Response.json({ groups: [], song_ids: ['b'] })) : searchResponse(path))
  await race.wrapper.get('input').setValue('B'); await flushPromises()
  expect(ids(race)).toEqual(['b'])
  late.resolve(Response.json({ groups: [], song_ids: ['a'] })); await flushPromises()
  expect(ids(race)).toEqual(['b'])
  await race.wrapper.get('input').setValue(''); await flushPromises()
  expect(ids(race)).toEqual([])
  race.wrapper.unmount()
})

it('route_return_and_reload_reread_query_and_share_song_actions', async () => {
  let reads = 0
  const h = await libraryPage('/library/search?q=Rock', (path, init) => {
    if (path === '/api/library/search/results?q=Rock') reads++
    if (init?.method === 'POST') return Promise.resolve(Response.json(playerState().queue.items[0]))
    return searchResponse(path)
  })
  expect(ids(h)).toEqual(['a', 'b'])
  await h.wrapper.get('[data-song-id="a"] .song-open').trigger('click')
  expect(h.requests.filter(r => r.init?.method === 'POST')).toHaveLength(0)
  await h.wrapper.get('[data-song-action="now"]').trigger('click'); await flushPromises()
  expect(h.requests.find(r => r.init?.method === 'POST')?.path).toBe('/api/playback/songs/a/play')
  await h.router.push('/library'); await flushPromises(); await h.router.back(); await flushPromises()
  expect(h.wrapper.get('input').element.value).toBe('Rock')
  expect(ids(h)).toEqual(['a', 'b']); expect(reads).toBeGreaterThan(1)
  h.wrapper.unmount()
  const reload = await libraryPage('/library/search?q=Rock', searchResponse)
  expect(reload.wrapper.get('input').element.value).toBe('Rock'); expect(ids(reload)).toEqual(['a', 'b'])
  reload.wrapper.unmount()
})

it('revision_and_epoch_reject_late_collection_and_song_dtos', async () => {
  const late = deferred<Response>(); let reads = 0
  const h = await libraryPage('/library/search?q=Rock', path => path === '/api/library/search/results?q=Rock'
    ? ++reads === 1 ? late.promise : Promise.resolve(Response.json({ groups: [], song_ids: ['b'] })) : searchResponse(path))
  const state = playerState(); state.sequence++; state.revisions.library++
  h.store.invalidate({ type: 'invalidate', protocol_version: 1, epoch: state.epoch, sequence: state.sequence, domains: ['library'], revisions: state.revisions }, 1)
  await flushPromises(); late.resolve(Response.json({ groups: [], song_ids: ['a'] })); await flushPromises()
  expect(ids(h)).toEqual(['b'])
  h.wrapper.unmount()
  const oldSong = deferred<Response>(); let songReads = 0
  const epoch = await libraryPage('/library/search?q=Rock', path => path === '/api/library/songs/a'
    ? ++songReads === 1 ? oldSong.promise : Promise.resolve(Response.json({ ...wire.songs.a, title: '新 epoch 标题' })) : searchResponse(path))
  epoch.store.beginConnection(2); const next = playerState(); next.epoch = 'new-epoch'; epoch.store.acceptInitial(next, 2)
  await flushPromises(); oldSong.resolve(Response.json({ ...wire.songs.a, title: '旧 epoch 标题' })); await flushPromises()
  expect(epoch.wrapper.text()).toContain('新 epoch 标题'); expect(epoch.wrapper.text()).not.toContain('旧 epoch 标题')
  expect(ids(epoch)).toEqual(['a', 'b']); epoch.wrapper.unmount()
})

it('read_failure_is_top_only_and_rest_does_not_restore_write_permission', async () => {
  let failure = true
  const h = await libraryPage('/library/search?q=Rock', path => path === '/api/library/search/results?q=Rock' && failure
    ? Promise.resolve(Response.json({ error: { code: 'READ_FAILED', message: 'search read failed' } }, { status: 500 })) : searchResponse(path))
  expect(ids(h)).toEqual([])
  expect(h.wrapper.get('.library-content').text()).not.toContain('search read failed')
  await h.wrapper.get('.status-toggle').trigger('click')
  expect(h.wrapper.get('#playback-status-details').text()).toContain('search read failed')
  failure = false
  h.store.markDisconnected(); await flushPromises()
  await h.wrapper.get('input').setValue('长名'); await flushPromises()
  expect(ids(h)).toEqual(['a', 'b'])
  await h.wrapper.get('[data-song-id="a"] .song-open').trigger('click')
  expect(h.wrapper.get('[data-song-action="now"]').attributes('disabled')).toBeDefined()
  expect(h.store.writable).toBe(false)
  expect(h.requests.every(r => r.init?.method === 'GET')).toBe(true)
  h.wrapper.unmount()
})
