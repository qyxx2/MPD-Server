import { createPlayerActions } from '../../src/components/player/playerActions'
import { expect, it, vi } from 'vitest'
import { playerPage, playerState, fixture, flushPromises } from '../support/player'
import { deferred } from '../support/transport'
import { parseSnapshot } from '../../src/services/wire'
it('resume uses target receipt without changing canonical position or occurrence; pending locks competing controls', async () => {
  const receipt = deferred<Response>()
  const h = playerPage(receipt.promise, Response.json(playerState()))
  expect(h.wrapper.find('button[aria-label="继续播放"]').exists()).toBe(true)
  await h.wrapper.get('button[aria-label="继续播放"]').trigger('click')
  await h.wrapper.get('button[aria-label="继续播放"]').trigger('click')
  expect(h.network.requests).toHaveLength(1)
  expect(h.wrapper.find('button[aria-label="停止播放"]').exists()).toBe(false)
  expect(h.wrapper.get('input').attributes('disabled')).toBeDefined()
  receipt.resolve(Response.json({ ...fixture.playback_receipt, state: 'PLAYING' }))
  await flushPromises()
  expect(h.store.snapshot?.playback?.state).toBe('PAUSED')
  expect(h.store.snapshot?.playback_observation.position_seconds).toBe(37)
  expect(JSON.parse(h.network.requests[0]!.init!.body as string)).toEqual({ target: fixture.snapshot.playback_observation.control_target })
  h.wrapper.unmount()
})
it('STOPPED main button never selects a song and degraded transport is read-only', async () => {
  const h = playerPage()
  const stopped = playerState(); stopped.sequence++; stopped.playback!.state = 'STOPPED'; stopped.playback_observation.actual_state = 'stopped'
  h.store.acceptRefresh(parseSnapshot(stopped), 1); await flushPromises()
  const main = h.wrapper.get('button[data-testid="primary-playback"]')
  expect(main.attributes('disabled')).toBeDefined()
  await main.trigger('click'); expect(h.network.requests).toHaveLength(0)
  h.store.markDisconnected(); await flushPromises()
  expect(h.wrapper.get('button[aria-label="下一首"]').attributes('disabled')).toBeDefined()
  h.wrapper.unmount()
})
it('timeout explicit retry keeps original key and payload; a fresh intent gets a new key', async () => {
  const h = playerPage(new Error('timeout'), Response.json(fixture.playback_receipt), Response.json(playerState()), Response.json(fixture.playback_receipt), Response.json(playerState()))
  await h.wrapper.get('button[aria-label="继续播放"]').trigger('click'); await flushPromises()
  expect(h.wrapper.text()).toContain('结果未知')
  await h.wrapper.get('button[aria-label="重试原操作"]').trigger('click'); await flushPromises()
  expect(h.network.requests[1]!.init!.headers).toEqual(h.network.requests[0]!.init!.headers)
  expect(h.network.requests[1]!.init!.body).toEqual(h.network.requests[0]!.init!.body)
  await h.wrapper.get('button[aria-label="继续播放"]').trigger('click'); await flushPromises()
  expect(h.network.requests[3]!.init!.headers).not.toEqual(h.network.requests[0]!.init!.headers)
  h.wrapper.unmount()
})
it('HTTP success followed by read failure remains confirmed, supports read retry and never repeats mutation', async () => {
  const h = playerPage(Response.json(fixture.playback_receipt), new Error('read unavailable'), Response.json(playerState()))
  await h.wrapper.get('button[aria-label="继续播放"]').trigger('click'); await flushPromises()
  expect(h.wrapper.text()).toContain('操作已确认')
  expect(h.wrapper.text()).toContain('状态未同步')
  expect(h.wrapper.find('button[aria-label="重试原操作"]').exists()).toBe(false)
  await h.wrapper.get('button[aria-label="重新读取状态"]').trigger('click'); await flushPromises()
  expect(h.network.requests.filter(r => r.init?.method === 'POST')).toHaveLength(1)
  h.wrapper.unmount()
})
it('fresh PLAYING uses pause; next and previous use visible candidates; unknown binding disables visible transport', async () => {
  const h = playerPage(Response.json(fixture.playback_receipt), Response.json(playerState()))
  const s = playerState(); s.sequence++; s.playback_observation.actual_state = 'playing'
  h.store.acceptRefresh(parseSnapshot(s), 1); await flushPromises()
  expect(h.wrapper.get('button[aria-label="下一首"]').attributes('disabled')).toBeUndefined()
  expect(h.wrapper.get('button[aria-label="上一首"]').attributes('disabled')).toBeDefined()
  await h.wrapper.get('button[aria-label="暂停播放"]').trigger('click'); await flushPromises()
  expect(h.network.requests.filter(r => r.init?.method === 'POST')[0]!.url).toBe('http://localhost/api/playback/pause')
  s.sequence++; s.playback_observation.sync_status = 'UNBOUND'; s.playback_observation.control_target = null
  h.store.acceptRefresh(parseSnapshot(s), 1); await flushPromises()
  expect(h.wrapper.get('button[data-testid="primary-playback"]').attributes('disabled')).toBeDefined()
  expect(h.wrapper.find('button[aria-label="停止播放"]').exists()).toBe(false)
  h.wrapper.unmount()
})
it('disconnection retires retained Stop action ownership; a late failure cannot attach retry to a new connection', async () => {
  const receipt = deferred<Response>()
  const h = playerPage(receipt.promise)
  const actions = createPlayerActions(h.store, { api: h.api, refresh: h.realtime.refresh })
  const pending = actions.act('stop')
  h.store.markDisconnected(); h.store.beginConnection(2); h.store.acceptInitial(parseSnapshot(playerState()), 2); await flushPromises()
  receipt.reject(new Error('old timeout')); await pending; await flushPromises()
  expect(actions.ui.unknown).toBe(false)
  expect(actions.ui.stopPending).toBe(false)
  actions.dispose()
  expect(h.wrapper.find('button[aria-label="重试原操作"]').exists()).toBe(false)
  expect(h.wrapper.find('button[aria-label="停止播放"]').exists()).toBe(false)
  h.wrapper.unmount()
})

it('product transport has only previous, pause/resume and next, without a Stop control or request', async () => {
  const h = playerPage(Response.json(fixture.playback_receipt), Response.json(playerState()))
  expect(h.wrapper.get('.transport-row').findAll('button').map(button => button.attributes('aria-label'))).toEqual(['上一首', '继续播放', '下一首'])
  await h.wrapper.get('button[aria-label="继续播放"]').trigger('click'); await flushPromises()
  expect(h.network.requests.filter(request => request.init?.method === 'POST').map(request => request.url)).toEqual(['http://localhost/api/playback/resume'])
  h.wrapper.unmount()
})

// Removing the presentation handoff (or using it for capabilities) breaks these real store→UI invariants.
function unknownHandoff() {
  const s = playerState(); s.sequence++
  Object.assign(s.playback_observation, fixture.empty_snapshot.playback_observation)
  return s
}
it('same-identity action handoff keeps labelled media and frozen progress while canonical unknown disables all controls', async () => {
  const receipt = deferred<Response>()
  const h = playerPage(receipt.promise, Response.json(unknownHandoff()))
  await h.wrapper.get('button[aria-label="继续播放"]').trigger('click')
  h.store.acceptRefresh(parseSnapshot(unknownHandoff()), 1); await flushPromises()
  expect(h.store.snapshot?.playback_observation.actual_state).toBeNull()
  expect(h.store.snapshot?.playback_observation.control_target).toBeNull()
  expect(h.wrapper.get('[data-testid="actual-identity"]').text()).toContain('长标题 / Song A')
  expect(h.wrapper.get('[data-testid="operation-status"]').text()).toContain('上次确认')
  expect(h.wrapper.get('[data-testid="progress"]').text()).toContain('观察位置 0:37')
  for (const button of h.wrapper.findAll('.transport-row button')) {
    expect(button.attributes('disabled')).toBeDefined(); await button.trigger('click')
  }
  expect(h.wrapper.get('input').attributes('disabled')).toBeDefined()
  expect(h.network.requests).toHaveLength(1)
  receipt.resolve(Response.json(fixture.playback_receipt)); await flushPromises()
  expect(h.wrapper.get('[data-testid="operation-status"]').text()).toContain('上次确认')
  const fresh = playerState(); fresh.sequence += 2; fresh.playback_observation.actual_state = 'playing'; fresh.playback_observation.position_seconds = 39
  h.store.acceptRefresh(parseSnapshot(fresh), 1); await flushPromises()
  expect(h.wrapper.get('[data-testid="actual-identity"]').text()).not.toContain('上次确认')
  expect(h.wrapper.get('[data-testid="progress"]').text()).toContain('观察位置 0:39')
  expect(h.wrapper.get('button[aria-label="暂停播放"]').attributes('disabled')).toBeUndefined()
  h.wrapper.unmount()
})
it.each(['occurrence', 'epoch', 'generation', 'song', 'context', 'library', 'stale', 'error', 'drift'] as const)('handoff revokes old media on %s rather than matching only URI', async boundary => {
  const receipt = deferred<Response>(); const h = playerPage(receipt.promise)
  await h.wrapper.get('button[aria-label="继续播放"]').trigger('click')
  h.store.acceptRefresh(parseSnapshot(unknownHandoff()), 1); await flushPromises()
  expect(h.wrapper.get('[data-testid="operation-status"]').text()).toContain('上次确认')
  const next = unknownHandoff(); next.sequence++
  if (boundary === 'occurrence') next.queue.items[0]!.queue_item_id = 'new-occurrence-same-uri'
  if (boundary === 'song') { next.current_song!.song_id = 'different-song'; next.playback!.song_id = 'different-song' }
  if (boundary === 'context') next.playback!.playback_context_id = 'different-context'
  if (boundary === 'library') next.revisions.library++
  if (boundary === 'stale') next.playback_observation.actual_freshness = 'stale'
  if (boundary === 'error') { next.playback_observation.error_code = 'PLAYER_UNAVAILABLE'; next.playback_observation.error_message = 'Unavailable' }
  if (boundary === 'drift') next.playback_observation.sync_status = 'EXTERNAL_DRIFT'
  if (boundary === 'epoch') { next.epoch = 'new-epoch'; h.store.beginConnection(2); h.store.acceptInitial(parseSnapshot(next), 2) }
  else if (boundary === 'generation') { h.store.markDisconnected(); h.store.beginConnection(2); h.store.acceptInitial(parseSnapshot(next), 2) }
  else h.store.acceptRefresh(parseSnapshot(next), 1)
  await flushPromises()
  expect(h.wrapper.get('[data-testid="actual-identity"]').text()).not.toContain('长标题 / Song A')
  expect(h.wrapper.get('[data-testid="progress"]').text()).not.toContain('0:37')
  receipt.reject(new Error('old timeout')); await flushPromises()
  expect(h.wrapper.text()).not.toContain('操作已确认')
  h.wrapper.unmount()
})
it('transport and seek indicate pending via stable disabled controls and accessibility without inserting text', async () => {
  for (const action of ['resume', 'seek'] as const) {
    const receipt = deferred<Response>(); const h = playerPage(receipt.promise, Response.json(playerState()))
    const area = h.wrapper.get('[data-testid="operation-status"]').element
    if (action === 'resume') await h.wrapper.get('button[aria-label="继续播放"]').trigger('click')
    else { const slider = h.wrapper.get('input'); await slider.trigger('pointerdown'); await slider.setValue('80'); await slider.trigger('pointerup') }
    expect(h.wrapper.get('[data-testid="operation-status"]').element).toBe(area)
    expect(h.wrapper.get('[data-testid="operation-status"]').text()).toBe('')
    expect(h.wrapper.get('.playback-controls').attributes('aria-busy')).toBe('true')
    expect(h.wrapper.get('[data-testid="primary-playback"]').attributes('disabled')).toBeDefined()
    expect(h.wrapper.get('[data-testid="progress"]').text()).not.toContain('正在提交')
    receipt.resolve(Response.json(fixture.playback_receipt)); await flushPromises()
    expect(h.wrapper.get('[data-testid="operation-status"]').element).toBe(area)
    h.wrapper.unmount()
  }
})
it('failed action never manufactures confirmation or keeps the handoff masking an unknown result', async () => {
  const receipt = deferred<Response>(); const h = playerPage(receipt.promise)
  await h.wrapper.get('button[aria-label="继续播放"]').trigger('click')
  h.store.acceptRefresh(parseSnapshot(unknownHandoff()), 1); await flushPromises()
  expect(h.wrapper.text()).toContain('上次确认')
  receipt.reject(new Error('timeout')); await flushPromises()
  expect(h.wrapper.get('[data-testid="operation-status"]').text()).toContain('结果未知')
  expect(h.wrapper.get('[data-testid="actual-identity"]').text()).not.toContain('长标题 / Song A')
  expect(h.wrapper.text()).not.toContain('操作已确认')
  expect(h.store.snapshot?.playback_observation.control_target).toBeNull()
  h.wrapper.unmount()
})

it('handoff progress stays frozen and expires without renewing on repeated unknown samples', async () => {
  vi.useFakeTimers()
  const receipt = deferred<Response>(); const h = playerPage(receipt.promise)
  await h.wrapper.get('button[aria-label="继续播放"]').trigger('click')
  h.store.acceptRefresh(parseSnapshot(unknownHandoff()), 1)
  await vi.advanceTimersByTimeAsync(1500)
  expect(h.wrapper.get('[data-testid="progress"]').text()).toContain('观察位置 0:37')
  const repeated = unknownHandoff(); repeated.sequence++
  h.store.acceptRefresh(parseSnapshot(repeated), 1)
  await vi.advanceTimersByTimeAsync(4501)
  expect(h.wrapper.get('[data-testid="actual-identity"]').text()).not.toContain('长标题 / Song A')
  expect(h.wrapper.get('[data-testid="progress"]').text()).toContain('未知')
  receipt.reject(new Error('timeout')); await vi.advanceTimersByTimeAsync(0)
  h.wrapper.unmount()
})
it('an old confirmed action cannot retain media through a later unrelated unknown observation', async () => {
  const h = playerPage(Response.json(fixture.playback_receipt), Response.json(playerState()))
  await h.wrapper.get('button[aria-label="继续播放"]').trigger('click'); await flushPromises()
  h.store.acceptRefresh(parseSnapshot(unknownHandoff()), 1); await flushPromises()
  expect(h.wrapper.get('[data-testid="actual-identity"]').text()).not.toContain('长标题 / Song A')
  expect(h.wrapper.get('[data-testid="progress"]').text()).not.toContain('0:37')
  h.wrapper.unmount()
})

it('song identity has no independent paused or playing status row', async () => {
  const h = playerPage()
  expect(h.wrapper.get('[data-testid="actual-identity"]').find('.eyebrow').exists()).toBe(false)
  expect(h.wrapper.get('[data-testid="actual-identity"]').text()).not.toContain('已暂停')
  const playing = playerState(); playing.sequence++; playing.playback_observation.actual_state = 'playing'
  h.store.acceptRefresh(parseSnapshot(playing), 1); await flushPromises()
  expect(h.wrapper.get('[data-testid="actual-identity"]').text()).not.toContain('正在播放')
  h.wrapper.unmount()
})
it('same-song snapshot handoff keeps identity, source, readout labels and playing icon stable with one local notice', async () => {
  const receipt = deferred<Response>(); const h = playerPage(receipt.promise)
  const playing = playerState(); playing.sequence++; playing.playback_observation.actual_state = 'playing'
  h.store.acceptRefresh(parseSnapshot(playing), 1); await flushPromises()
  const identity = h.wrapper.get('[data-testid="actual-identity"]').html()
  const metadata = h.wrapper.get('[data-testid="source-metadata"]').html()
  const progress = h.wrapper.get('.progress-readout').text()
  expect(h.wrapper.get('[data-testid="primary-playback"]').text()).toBe('Ⅱ')
  await h.wrapper.get('button[aria-label="暂停播放"]').trigger('click')
  const unknown = unknownHandoff(); unknown.sequence++
  h.store.acceptRefresh(parseSnapshot(unknown), 1); await flushPromises()
  expect(h.wrapper.get('[data-testid="actual-identity"]').html()).toBe(identity)
  expect(h.wrapper.get('[data-testid="source-metadata"]').html()).toBe(metadata)
  expect(h.wrapper.get('.progress-readout').text()).toBe(progress)
  expect(h.wrapper.get('[data-testid="primary-playback"]').text()).toBe('Ⅱ')
  expect(h.wrapper.get('[data-testid="primary-playback"]').attributes('disabled')).toBeDefined()
  expect(h.wrapper.findAll('.page-header [data-testid="operation-status"]')).toHaveLength(1)
  expect(h.wrapper.findAll('.player-content [data-testid="operation-status"]')).toHaveLength(0)
  expect(h.wrapper.get('[data-testid="operation-status"]').text()).toContain('上次确认')
  expect(h.store.snapshot?.playback_observation.actual_state).toBeNull()
  receipt.reject(new Error('timeout')); await flushPromises()
  expect(h.wrapper.get('[data-testid="operation-status"]').text()).toContain('结果未知')
  h.wrapper.unmount()
})
it.each([
  ['UNCONFIRMED_STOP', '外部停止尚未确认'],
  ['SYNC_FAILED', '播放同步失败'],
  ['EXTERNAL_DRIFT', '实际播放与业务状态不一致'],
  ['UNBOUND', '实际播放未绑定'],
] as const)('stopped actual preserves %s in the single feedback region without changing business or canonical confirmation', async (sync_status, diagnostic) => {
  const h = playerPage()
  const stopped = playerState(); stopped.sequence++
  Object.assign(stopped.playback_observation, { actual_state: 'stopped', actual_freshness: 'fresh', freshness: 'unknown', sync_status,
    bound_queue_item_id: null, control_target: null, matches_current: null, position_seconds: null, duration_seconds: null })
  h.store.acceptRefresh(parseSnapshot(stopped), 1); await flushPromises()
  expect(h.wrapper.get('[data-testid="operation-status"]').text()).toContain(diagnostic)
  expect(h.wrapper.get('[data-testid="actual-identity"]').find('.eyebrow').exists()).toBe(false)
  expect(h.wrapper.get('[data-testid="last-business"]').text()).toContain('长标题 / Song A')
  expect(h.wrapper.get('[data-testid="primary-playback"]').attributes('disabled')).toBeDefined()
  expect(h.store.snapshot?.playback?.state).toBe('PAUSED')
  expect(h.store.snapshot?.playback_observation.sync_status).toBe(sync_status)
  expect(h.network.requests).toHaveLength(0)
  h.wrapper.unmount()
})

it('playback feedback stays in the app bar and opens recovery details without adding a transport row', async () => {
  const receipt = deferred<Response>(), h = playerPage(receipt.promise)
  const header = h.wrapper.get('.page-header')
  const status = header.get('[data-testid="operation-status"]').element
  expect(h.wrapper.find('.playback-controls [data-testid="operation-status"]').exists()).toBe(false)
  await h.wrapper.get('button[aria-label="继续播放"]').trigger('click')
  expect(header.find('.status-spinner').exists()).toBe(true)
  expect(header.get('[data-testid="operation-status"]').element).toBe(status)
  receipt.reject(new Error('timeout')); await flushPromises()
  expect(header.find('.status-spinner').exists()).toBe(false)
  await header.get('button[aria-label="查看播放操作异常"]').trigger('click')
  expect(header.get('.status-details').isVisible()).toBe(true)
  expect(header.get('.status-details').text()).toContain('结果未知')
  expect(header.find('button[aria-label="重试原操作"]').exists()).toBe(true)
  expect(h.wrapper.find('.playback-controls .recovery-row').exists()).toBe(false)
  h.wrapper.unmount()
})
