import { expect, it, vi } from 'vitest'
import { playerPage, playerState, flushPromises } from '../support/player'

it('unavailable playback adds only an app bar notice and clears it when current is confirmed', async () => {
  const h = playerPage()
  const before = h.wrapper.get('.transport-row').html()
  const s = playerState(); s.sequence++
  Object.assign(s.playback_observation, { actual_state: 'stopped', sync_status: 'UNCONFIRMED_STOP',
    matches_current: null, bound_queue_item_id: null, control_target: null, position_seconds: null, duration_seconds: null })
  h.store.acceptRefresh(s, 1); await flushPromises()
  expect(h.wrapper.get('.playback-controls').find('p').exists()).toBe(false)
  expect(h.wrapper.find('.player-content [data-testid="last-business"]').exists()).toBe(false)
  expect(h.wrapper.get('.page-header [data-testid="operation-status"]').text()).toContain('需明确选曲后播放')
  await h.wrapper.get('.status-toggle').trigger('click')
  expect(h.wrapper.get('.status-details').text()).toContain('外部停止尚未确认')
  expect(h.wrapper.get('.status-details').text()).toContain('最后业务歌曲')
  const normal = playerState(); normal.sequence = s.sequence + 1
  h.store.acceptRefresh(normal, 1); await flushPromises()
  expect(h.wrapper.find('.status-toggle').exists()).toBe(false)
  expect(h.wrapper.get('.transport-row').html()).toBe(before)
  h.wrapper.unmount()
})

it('concurrent read, file and lyric notices share one header detail without inserting content rows', async () => {
  const h = playerPage(), s = playerState(); s.sequence++
  Object.assign(s.current_song!, { availability_status: 'MISSING', lyrics: 'fallback正文', lyrics_format: 'text', lyrics_status: 'read_error' })
  h.store.acceptRefresh(s, 1); h.store.markReadError(new Error('read failed'))
  await h.wrapper.get('button[aria-label="显示歌词"]').trigger('click')
  expect(h.wrapper.find('.player-content .warning').exists()).toBe(false)
  expect(h.wrapper.find('.lyrics-status p').exists()).toBe(false)
  expect(h.wrapper.findAll('.status-toggle')).toHaveLength(1)
  await h.wrapper.get('.status-toggle').trigger('click')
  expect(h.wrapper.get('.status-details').text()).toContain('文件缺失')
  expect(h.wrapper.get('.status-details').text()).toContain('状态读取异常')
  expect(h.wrapper.get('.status-details').text()).toContain('歌词读取失败')
  expect(h.wrapper.get('.lyrics-content').text()).toContain('fallback正文')
  expect(h.wrapper.find('button[aria-label="重新读取状态"]').exists()).toBe(true)
  const normal = playerState(); normal.sequence = s.sequence + 1
  Object.assign(normal.current_song!, { lyrics: '[00:37]正常歌词', lyrics_format: 'lrc', lyrics_status: 'available' })
  h.store.acceptRefresh(normal, 1); await flushPromises()
  expect(h.wrapper.find('.status-toggle').exists()).toBe(false)
  expect(h.wrapper.get('.lyrics-content').text()).toContain('正常歌词')
  h.wrapper.unmount()
})

it.each([
  [null, null, 'missing', '无歌词'],
  ['普通正文', 'text', 'available', '普通文本 · 不同步'],
  ['[坏标签]正文', 'lrc', 'available', '无法同步 · 普通文本'],
] as const)('lyric explanation stays in the app bar for %s', async (lyrics, lyrics_format, lyrics_status, message) => {
  const h = playerPage(), s = playerState(); s.sequence++
  Object.assign(s.current_song!, { lyrics, lyrics_format, lyrics_status })
  h.store.acceptRefresh(s, 1)
  await h.wrapper.get('button[aria-label="显示歌词"]').trigger('click')
  expect(h.wrapper.get('.lyrics-stage').text()).not.toContain(message)
  expect(h.wrapper.get('.page-header [data-testid="operation-status"]').text()).toContain(message)
  await h.wrapper.get('button[aria-label="显示封面"]').trigger('click')
  expect(h.wrapper.find('.status-toggle').exists()).toBe(false)
  h.wrapper.unmount()
})

it('artwork failure is a header notice with a silent placeholder and retires on a new resource', async () => {
  vi.stubGlobal('fetch', async () => new Response('', { status: 503 }))
  const h = playerPage(), s = playerState(); s.sequence++
  s.current_song!.artwork = { artwork_id: 'art', source: 'EMBEDDED', picture_index: 0, mime_type: 'image/png', width: null, height: null, content_sha256: 'hash' }
  h.store.acceptRefresh(s, 1); await flushPromises()
  expect(h.wrapper.get('[data-testid="artwork-placeholder"]').text()).not.toContain('封面读取失败')
  expect(h.wrapper.get('.page-header [data-testid="operation-status"]').text()).toContain('封面读取失败')
  const normal = playerState(); normal.sequence = s.sequence + 1
  h.store.acceptRefresh(normal, 1); await flushPromises()
  expect(h.wrapper.find('.status-toggle').exists()).toBe(false)
  h.wrapper.unmount(); vi.unstubAllGlobals()
})

it('an unknown operation does not hide a separate canonical diagnostic or send another mutation', async () => {
  const h = playerPage(Promise.reject(new Error('timeout')))
  await h.wrapper.get('button[aria-label="继续播放"]').trigger('click'); await flushPromises()
  const s = playerState(); s.sequence++
  Object.assign(s.playback_observation, { sync_status: 'NO_CANDIDATES' })
  h.store.acceptRefresh(s, 1); await flushPromises()
  expect(h.wrapper.get('.page-header [data-testid="operation-status"]').text()).toContain('结果未知')
  expect(h.wrapper.get('.page-header [data-testid="operation-status"]').text()).toContain('无候选歌曲')
  await h.wrapper.get('.status-toggle').trigger('click')
  expect(h.wrapper.get('.status-details').text()).toContain('结果未知')
  expect(h.wrapper.get('.status-details').text()).toContain('无候选歌曲')
  expect(h.network.requests).toHaveLength(1)
  h.wrapper.unmount()
})

it('late image error and load events cannot replace or clear the current artwork notice', async () => {
  let image = 0
  vi.stubGlobal('URL', class extends URL { static createObjectURL() { return `blob:image-${++image}` }; static revokeObjectURL() {} })
  vi.stubGlobal('fetch', async () => new Response('image'))
  const h = playerPage(), s = playerState(); s.sequence++
  s.current_song!.artwork = { artwork_id: 'art', source: 'EMBEDDED', picture_index: 0, mime_type: 'image/png', width: null, height: null, content_sha256: 'old' }
  h.store.acceptRefresh(s, 1); await flushPromises()
  const old = h.wrapper.get('img'); await old.trigger('load')
  const next = structuredClone(s); next.sequence++; next.revisions.library++
  next.current_song!.artwork!.content_sha256 = 'new'
  h.store.acceptRefresh(next, 1); await flushPromises()
  const current = h.wrapper.get('img'); await current.trigger('load')
  await old.trigger('error')
  expect(h.wrapper.get('img').attributes('src')).toBe('blob:image-2')
  expect(h.wrapper.find('.status-toggle').exists()).toBe(false)
  await current.trigger('error'); await old.trigger('load')
  expect(h.wrapper.get('.page-header [data-testid="operation-status"]').text()).toContain('封面读取失败')
  h.wrapper.unmount(); vi.unstubAllGlobals()
})
