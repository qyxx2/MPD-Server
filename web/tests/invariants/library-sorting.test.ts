import { expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { libraryPage, wire } from '../support/library'

it('library navigation opens all songs and selects its tab', async () => {
  const h = await libraryPage('/library?kind=albums')
  await h.wrapper.get('nav a[href="/library"]').trigger('click'); await flushPromises()
  expect(h.wrapper.get('[data-library-kind="songs"]').attributes('aria-pressed')).toBe('true')
  expect(h.wrapper.findAll('[data-song-id]')).toHaveLength(3)
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
