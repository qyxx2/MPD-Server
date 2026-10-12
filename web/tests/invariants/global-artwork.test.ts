import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { shellPage } from '../support/shell'
import { playerState } from '../support/player'
import { deferred } from '../support/transport'
afterEach(() => vi.unstubAllGlobals())
const artwork = { artwork_id: 'art-a', source: 'EMBEDDED' as const, picture_index: 0, mime_type: 'image/png', width: null, height: null, content_sha256: 'hash-a' }
it('confirmed_identity_decode_and_route_lifetime', async () => {
  const decodeA = deferred<void>()
  const decode = vi.fn(() => decodeA.promise)
  vi.stubGlobal('Image', class { src = ''; decode = decode })
  let number = 0
  vi.stubGlobal('URL', class extends URL { static createObjectURL() { return `blob:image-${++number}` }; static revokeObjectURL() {} })
  const fetchImage = vi.fn(async () => new Response('image'))
  vi.stubGlobal('fetch', fetchImage)
  const h = await shellPage()
  const a = playerState(); a.sequence++; a.current_song!.artwork = artwork
  h.store.acceptRefresh(a, 1); await flushPromises()
  // Fetch success is insufficient: decoded identity must be accepted first.
  expect(h.wrapper.find('img').exists()).toBe(false)
  for (const path of ['/queue', '/library', '/settings', '/']) { await h.router.push(path); await flushPromises() }
  expect(fetchImage).toHaveBeenCalledTimes(1)
  const b = structuredClone(a); b.sequence++; b.current_song!.song_id = 'b'; b.current_song!.file_uri = 'b.flac'
  b.playback_observation.control_target!.token = 'b-token'
  decode.mockImplementationOnce(async () => {})
  h.store.acceptRefresh(b, 1); await flushPromises()
  expect(h.wrapper.get('.app-background img').attributes('src')).toBe('blob:image-2')
  expect(h.wrapper.get('.artwork-stage img').attributes('src')).toBe('blob:image-2')
  decodeA.resolve(); await flushPromises()
  expect(h.wrapper.get('.app-background img').attributes('src')).toBe('blob:image-2')
  h.store.markDisconnected(); await flushPromises()
  expect(h.wrapper.get('.app-background img').attributes('src')).toBe('blob:image-2')
  h.store.beginConnection(2); const invalid = structuredClone(b); invalid.sequence++
  Object.assign(invalid.playback_observation, { sync_status: 'UNBOUND', control_target: null, bound_queue_item_id: null, matches_current: false })
  h.store.acceptInitial(invalid, 2); await flushPromises()
  expect(h.wrapper.find('.app-background img').exists()).toBe(false)
  expect(fetchImage).toHaveBeenCalledTimes(2)
  h.wrapper.unmount()
})
it.each([404, 503, 'decode'] as const)('missing_or_failed_resource_uses_default_without_claiming_confirmation: %s', async status => {
  vi.stubGlobal('fetch', async () => new Response('image', { status: typeof status === 'number' ? status : 200 }))
  vi.stubGlobal('Image', class { src = ''; async decode() { throw new Error('bad image') } })
  vi.stubGlobal('URL', class extends URL { static createObjectURL() { return 'blob:bad' }; static revokeObjectURL() {} })
  const h = await shellPage()
  const s = playerState(); s.sequence++; s.current_song!.artwork = artwork
  h.store.acceptRefresh(s, 1); await flushPromises()
  expect(h.wrapper.find('.app-background img').exists()).toBe(false)
  expect(h.wrapper.get('[data-testid="artwork-placeholder"]').attributes('aria-label')).toBe(status === 404 ? '无封面' : '封面读取失败')
  expect(h.wrapper.get('[data-testid="operation-status"]').text()).toBe(status === 404 ? '' : '封面读取失败')
  h.wrapper.unmount()
})
it('handoff_can_retain_foreground_but_cannot_promote_a_late_decode_to_background', async () => {
  const image = deferred<void>(), action = deferred<Response>()
  vi.stubGlobal('fetch', async () => new Response('image'))
  vi.stubGlobal('Image', class { src = ''; decode() { return image.promise } })
  vi.stubGlobal('URL', class extends URL { static createObjectURL() { return 'blob:a' }; static revokeObjectURL() {} })
  const h = await shellPage(action.promise)
  const s = playerState(); s.sequence++; s.current_song!.artwork = artwork
  h.store.acceptRefresh(s, 1); await flushPromises()
  await h.wrapper.get('button[aria-label="继续播放"]').trigger('click')
  const unknown = structuredClone(s); unknown.sequence++
  Object.assign(unknown.playback_observation, { actual_state: null, actual_current: null, freshness: 'unknown', actual_freshness: 'unknown', matches_current: null, bound_queue_item_id: null, control_target: null, sync_status: 'UNBOUND', position_seconds: null, duration_seconds: null })
  h.store.acceptRefresh(unknown, 1); image.resolve(); await flushPromises()
  expect(h.wrapper.get('.artwork-stage img').attributes('src')).toBe('blob:a')
  expect(h.wrapper.find('.app-background img').exists()).toBe(false)
  action.reject(new Error('unknown')); await flushPromises(); h.wrapper.unmount()
})
