import { expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { libraryPage, wire } from '../support/library'
import { playerState } from '../support/player'

it('play all sends the selected sort while shuffle keeps its existing source', async () => {
  const h = await libraryPage('/library', (_path, init) => init?.method === 'POST'
    ? Promise.resolve(Response.json(playerState().playback)) : undefined)
  for (const [field, order] of [['title', 'asc'], ['title', 'desc'], ['modified_at', 'asc'], ['modified_at', 'desc']]) {
    await h.wrapper.get('select[aria-label="排序方式"]').setValue(`${field}:${order}`)
    await flushPromises()
    await h.wrapper.get('[data-play-all]').trigger('click'); await flushPromises()
    const write = h.requests.filter(r => r.init?.method === 'POST').at(-1)!
    expect(write.path).toBe('/api/playback/collections/play')
    expect(JSON.parse(String(write.init?.body))).toEqual({ source_type: 'LIBRARY', sort_by: field, sort_order: order, randomize: false })
  }
  await h.wrapper.get('[data-shuffle-all]').trigger('click'); await flushPromises()
  expect(JSON.parse(String(h.requests.filter(r => r.init?.method === 'POST').at(-1)!.init?.body))).toEqual({ source_type: 'LIBRARY', randomize: true })
  h.wrapper.unmount()
})

it('library navigation opens all songs and selects its tab', async () => {
  const h = await libraryPage('/library?kind=albums')
  await h.wrapper.get('nav a[href="/library"]').trigger('click'); await flushPromises()
  expect(h.wrapper.get('[data-library-kind="songs"]').attributes('aria-pressed')).toBe('true')
  expect(h.wrapper.findAll('[data-song-id]')).toHaveLength(3)
  h.wrapper.unmount()
})

it('retry keeps the original sort after the sort selection changes', async () => {
  let attempts = 0
  const h = await libraryPage('/library', (_path, init) => init?.method === 'POST'
    ? ++attempts === 1 ? Promise.reject(new TypeError('lost ACK')) : Promise.resolve(Response.json(playerState().playback)) : undefined)
  const select = h.wrapper.get('select[aria-label="排序方式"]')
  await select.setValue('modified_at:desc'); await flushPromises()
  await h.wrapper.get('[data-play-all]').trigger('click'); await flushPromises()
  await select.setValue('title:asc'); await flushPromises()
  await h.tasks.entries.value[0]!.retry!(); await flushPromises()
  const writes = h.requests.filter(r => r.init?.method === 'POST')
  expect(writes).toHaveLength(2)
  expect(JSON.parse(String(writes[1]!.init?.body))).toEqual({ source_type: 'LIBRARY', sort_by: 'modified_at', sort_order: 'desc', randomize: false })
  expect(writes[1]!.init?.body).toBe(writes[0]!.init?.body)
  expect(new Headers(writes[1]!.init?.headers).get('Idempotency-Key')).toBe(new Headers(writes[0]!.init?.headers).get('Idempotency-Key'))
  h.wrapper.unmount()
})

it('all four sort choices read the full sorted resource without playback mutations', async () => {
  const h = await libraryPage('/library', path => path.startsWith('/api/library/songs?')
    ? Promise.resolve(Response.json({ ...wire.songs, items: [...wire.songs.items].reverse() })) : undefined)
  const select = h.wrapper.get('.collection-actions select[aria-label="排序方式"]')
  expect(select.findAll('option')).toHaveLength(4)
  expect(select.text()).toContain('修改时间'); expect(select.text()).toContain('名称/标题')
  for (const field of ['modified_at', 'title']) {
    for (const order of ['asc', 'desc']) {
      await select.setValue(`${field}:${order}`); await flushPromises()
      expect(h.requests.some(r => r.path === `/api/library/songs?sort_by=${field}&sort_order=${order}`)).toBe(true)
      expect(h.wrapper.findAll('[data-song-id]').map(r => r.attributes('data-song-id'))).toEqual(['c', 'b', 'a'])
    }
  }
  expect(h.requests.every(r => r.init?.method === 'GET')).toBe(true)
  h.wrapper.unmount()
})
