import { createPlayerActions } from '../../src/components/player/playerActions'
import { expect, it } from 'vitest'
import { playerPage, playerState, flushPromises, fixture } from '../support/player'
import { parseSnapshot } from '../../src/services/wire'
import { deferred } from '../support/transport'
it('submitted seek stays at the finger position through pending, old observation and temporary unknown until authoritative convergence', async () => {
  const receipt = deferred<Response>()
  const old = playerState(); old.sequence++
  const h = playerPage(receipt.promise, Response.json(old))
  const slider = h.wrapper.get('input')
  await slider.trigger('pointerdown'); await slider.setValue('80'); await slider.trigger('pointerup')
  expect(slider.element).toHaveProperty('value', '80')
  expect(h.wrapper.get('[data-testid="progress"]').text()).toContain('待确认位置 1:20')
  expect(h.store.snapshot?.playback_observation.position_seconds).toBe(37)
  expect(slider.attributes('disabled')).toBeDefined()
  await slider.trigger('blur'); await slider.trigger('pointerup')
  expect(h.network.requests.filter(r => r.init?.method === 'POST')).toHaveLength(1)
  receipt.resolve(Response.json({ ...fixture.playback_receipt, position_seconds: 80, updated_at: '2026-10-09T08:00:02Z' }))
  await flushPromises()
  expect(slider.element).toHaveProperty('value', '80')
  const unknown = playerState(); unknown.sequence += 2
  Object.assign(unknown.playback_observation, fixture.empty_snapshot.playback_observation)
  h.store.acceptRefresh(parseSnapshot(unknown), 1); await flushPromises()
  expect(slider.element).toHaveProperty('value', '80')
  expect(h.store.snapshot?.playback_observation.position_seconds).toBeNull()
  const fresh = playerState(); fresh.sequence += 3
  fresh.playback_observation.observed_at = '2026-10-09T08:00:03Z'; fresh.playback_observation.position_seconds = 82
  h.store.acceptRefresh(parseSnapshot(fresh), 1); await flushPromises()
  expect(slider.element).toHaveProperty('value', '82')
  expect(h.wrapper.get('[data-testid="progress"]').text()).toContain('观察位置 1:22')
  h.wrapper.unmount()
})

it('submitted seek is revoked by disconnect and cannot be resurrected by a late receipt', async () => {
  const receipt = deferred<Response>()
  const h = playerPage(receipt.promise, Response.json(playerState()))
  const slider = h.wrapper.get('input')
  await slider.trigger('pointerdown'); await slider.setValue('80'); await slider.trigger('pointerup')
  expect(slider.element).toHaveProperty('value', '80')
  h.store.markDisconnected(); await flushPromises()
  expect(h.wrapper.get('[data-testid="progress"]').text()).not.toContain('待确认位置')
  receipt.resolve(Response.json({ ...fixture.playback_receipt, position_seconds: 80, updated_at: '2026-10-09T08:00:02Z' }))
  await flushPromises()
  expect(h.wrapper.get('[data-testid="progress"]').text()).not.toContain('待确认位置')
  expect(slider.attributes('disabled')).toBeDefined()
  h.wrapper.unmount()
})

it('seek transport failure clears the proposal and an explicit retry restores it with the original key', async () => {
  const receipt = deferred<Response>()
  const h = playerPage(new Error('timeout'), receipt.promise, Response.json(playerState()))
  const slider = h.wrapper.get('input')
  await slider.trigger('pointerdown'); await slider.setValue('80'); await slider.trigger('pointerup'); await flushPromises()
  expect(slider.element).toHaveProperty('value', '37')
  expect(h.wrapper.text()).toContain('结果未知')
  await h.wrapper.get('button[aria-label="重试原操作"]').trigger('click')
  expect(slider.element).toHaveProperty('value', '80')
  expect(h.wrapper.get('[data-testid="progress"]').text()).toContain('待确认位置')
  const posts = h.network.requests.filter(r => r.init?.method === 'POST')
  expect(posts).toHaveLength(2)
  expect(new Headers(posts[0]!.init?.headers).get('Idempotency-Key')).toBe(new Headers(posts[1]!.init?.headers).get('Idempotency-Key'))
  receipt.resolve(Response.json({ ...fixture.playback_receipt, updated_at: '2026-10-09T08:00:02Z' })); await flushPromises()
  expect(slider.element).toHaveProperty('value', '80')
  h.wrapper.unmount()
})

it('stale observation revokes a submitted seek proposal even if an old target is still present', async () => {
  const h = playerPage(Response.json({ ...fixture.playback_receipt, updated_at: '2026-10-09T08:00:02Z' }), Response.json(playerState()))
  const slider = h.wrapper.get('input')
  await slider.trigger('pointerdown'); await slider.setValue('80'); await slider.trigger('pointerup'); await flushPromises()
  const stale = playerState(); stale.sequence++
  stale.playback_observation.freshness = 'stale'; stale.playback_observation.actual_freshness = 'stale'
  h.store.acceptRefresh(parseSnapshot(stale), 1); await flushPromises()
  expect(h.wrapper.get('[data-testid="progress"]').text()).not.toContain('待确认位置')
  expect(slider.attributes('disabled')).toBeDefined()
  h.wrapper.unmount()
})

it('a business scope change during unknown retires the proposal before a late seek receipt', async () => {
  const receipt = deferred<Response>()
  const h = playerPage(receipt.promise, Response.json(playerState()))
  const slider = h.wrapper.get('input')
  await slider.trigger('pointerdown'); await slider.setValue('80'); await slider.trigger('pointerup')
  const unknown = playerState(); unknown.sequence++
  Object.assign(unknown.playback_observation, fixture.empty_snapshot.playback_observation)
  h.store.acceptRefresh(parseSnapshot(unknown), 1); await flushPromises()
  expect(slider.element).toHaveProperty('value', '80')
  unknown.sequence++; unknown.playback!.song_id = 'other-song'; unknown.current_song!.song_id = 'other-song'
  h.store.acceptRefresh(parseSnapshot(unknown), 1); await flushPromises()
  expect(h.wrapper.get('[data-testid="progress"]').text()).not.toContain('待确认位置')
  receipt.resolve(Response.json({ ...fixture.playback_receipt, updated_at: '2026-10-09T08:00:02Z' })); await flushPromises()
  expect(h.wrapper.get('[data-testid="progress"]').text()).not.toContain('待确认位置')
  h.wrapper.unmount()
})

it('a stale explicit retry does not revive its captured seek preview', async () => {
  const receipt = deferred<Response>()
  const h = playerPage(new Error('timeout'), receipt.promise, Response.json(playerState()))
  const slider = h.wrapper.get('input')
  await slider.trigger('pointerdown'); await slider.setValue('80'); await slider.trigger('pointerup'); await flushPromises()
  const stale = playerState(); stale.sequence++
  stale.playback_observation.freshness = 'stale'; stale.playback_observation.actual_freshness = 'stale'
  h.store.acceptRefresh(parseSnapshot(stale), 1); await flushPromises()
  await h.wrapper.get('button[aria-label="重试原操作"]').trigger('click')
  expect(h.wrapper.get('[data-testid="progress"]').text()).not.toContain('待确认位置')
  receipt.resolve(Response.json({ ...fixture.playback_receipt, updated_at: '2026-10-09T08:00:02Z' })); await flushPromises()
  h.wrapper.unmount()
})

it('an abnormal unknown observation cannot retain a pending seek proposal', async () => {
  const receipt = deferred<Response>()
  const h = playerPage(receipt.promise, Response.json(playerState()))
  const slider = h.wrapper.get('input')
  await slider.trigger('pointerdown'); await slider.setValue('80'); await slider.trigger('pointerup')
  const unknown = playerState(); unknown.sequence++
  Object.assign(unknown.playback_observation, fixture.empty_snapshot.playback_observation)
  h.store.acceptRefresh(parseSnapshot(unknown), 1); await flushPromises()
  unknown.sequence++
  Object.assign(unknown.playback_observation, { sync_status: 'EXTERNAL_DRIFT', reconciliation_required: true, error_code: 'PLAYER_UNAVAILABLE' })
  h.store.acceptRefresh(parseSnapshot(unknown), 1); await flushPromises()
  expect(h.wrapper.get('[data-testid="progress"]').text()).not.toContain('待确认位置')
  receipt.resolve(Response.json(fixture.playback_receipt)); await flushPromises()
  expect(h.wrapper.get('[data-testid="progress"]').text()).not.toContain('待确认位置')
  h.wrapper.unmount()
})
it('seek release sends one intent and rejects a changed target', async () => {
  const conflict = Response.json(fixture.error, { status: 409 })
  const h = playerPage(conflict, Response.json(playerState()))
  const before = JSON.stringify(h.store.snapshot)
  const slider = h.wrapper.find('input[type="range"]')
  expect(slider.exists()).toBe(true)
  await slider.trigger('pointerdown', { pointerId: 1 })
  await slider.setValue('60'); await slider.setValue('75')
  expect(h.network.requests).toHaveLength(0)
  await slider.trigger('pointerup', { pointerId: 1 }); await flushPromises()
  expect(h.network.requests.filter(r => r.init?.method === 'POST')).toHaveLength(1)
  expect(JSON.parse(h.network.requests[0]!.init!.body as string)).toEqual({ seconds: 75, target: fixture.snapshot.playback_observation.control_target })
  expect(JSON.stringify(h.store.snapshot)).toBe(before)
  expect(h.wrapper.text()).toContain('PLAYBACK_TARGET_CONFLICT')
  expect(slider.element).toHaveProperty('value', '37')
  await slider.trigger('pointerdown', { pointerId: 1 }); await slider.setValue('90')
  const changed = playerState(); changed.sequence++; changed.playback_observation.control_target!.token = 'new'
  h.store.acceptRefresh(parseSnapshot(changed), 1)
  await slider.trigger('pointerup', { pointerId: 1 }); await flushPromises()
  expect(h.network.requests.filter(r => r.init?.method === 'POST')).toHaveLength(1)
  h.wrapper.unmount()
})
it('confirmed seek waits for server observation time; read failure never asks for a new mutation', async () => {
  const old = playerState(); old.sequence++
  const h = playerPage(Response.json({ ...fixture.playback_receipt, position_seconds: 80, updated_at: '2026-10-09T08:00:02Z' }), new Error('read failed'))
  const slider = h.wrapper.get('input')
  await slider.trigger('pointerdown'); await slider.setValue('80'); await slider.trigger('pointerup'); await flushPromises()
  expect(h.wrapper.text()).toContain('操作已确认')
  expect(h.wrapper.text()).toContain('正在同步')
  expect(h.store.snapshot?.playback_observation.position_seconds).toBe(37)
  expect(slider.element).toHaveProperty('value', '80')
  h.store.acceptRefresh(parseSnapshot(old), 1); await flushPromises()
  expect(h.wrapper.text()).toContain('正在同步')
  const fresh = playerState(); fresh.sequence += 2; fresh.playback_observation.observed_at = '2026-10-09T08:00:03Z'; fresh.playback_observation.position_seconds = 80
  h.store.acceptRefresh(parseSnapshot(fresh), 1); await flushPromises()
  expect(h.wrapper.text()).not.toContain('正在同步')
  expect(slider.element).toHaveProperty('value', '80')
  h.wrapper.unmount()
})
it('keyboard keyup and blur commit once; Escape and pointercancel cancel; unknown duration disables seek', async () => {
  const h = playerPage(Response.json(fixture.playback_receipt), Response.json(playerState()))
  const slider = h.wrapper.get('input')
  await slider.trigger('keydown', { key: 'ArrowRight' }); await slider.setValue('50')
  expect(h.network.requests).toHaveLength(0)
  await slider.trigger('keyup', { key: 'ArrowRight' }); await slider.trigger('blur'); await flushPromises()
  expect(h.network.requests.filter(r => r.init?.method === 'POST')).toHaveLength(1)
  await slider.trigger('keydown', { key: 'ArrowRight' }); await slider.setValue('60'); await slider.trigger('keydown', { key: 'Escape' }); await slider.trigger('blur')
  await slider.trigger('pointerdown'); await slider.setValue('70'); await slider.trigger('pointercancel'); await slider.trigger('pointerup'); await flushPromises()
  expect(h.network.requests.filter(r => r.init?.method === 'POST')).toHaveLength(1)
  const unknown = playerState(); unknown.sequence++; unknown.playback_observation.duration_seconds = null
  h.store.acceptRefresh(parseSnapshot(unknown), 1); await flushPromises()
  expect(slider.attributes('disabled')).toBeDefined()
  h.wrapper.unmount()
})
it('retained Stop action supersedes seek waiting without cancelling the server request; late seek receipt cannot resurrect it', async () => {
  const seek = deferred<Response>()
  const h = playerPage(seek.promise, Response.json({ ...fixture.playback_receipt, state: 'STOPPED' }), Response.json(playerState()), Response.json(playerState()))
  const actions = createPlayerActions(h.store, { api: h.api, refresh: h.realtime.refresh })
  actions.beginSeek(); actions.preview(80); const pending = actions.releaseSeek()
  await actions.act('stop'); await flushPromises()
  seek.resolve(Response.json({ ...fixture.playback_receipt, updated_at: '2026-10-09T08:00:02Z' })); await pending; await flushPromises()
  expect(h.network.requests.filter(r => r.init?.method === 'POST').map(r => r.url)).toEqual(['http://localhost/api/playback/seek', 'http://localhost/api/playback/stop'])
  expect(actions.ui.syncing).toBe(false)
  actions.dispose()
  h.wrapper.unmount()
})
it('same URI new occurrence revokes a confirmed seek wait and cannot receive the old draft', async () => {
  const h = playerPage(Response.json({ ...fixture.playback_receipt, updated_at: '2026-10-09T08:00:02Z' }), Response.json(playerState()))
  const slider = h.wrapper.get('input')
  await slider.trigger('pointerdown'); await slider.setValue('80'); await slider.trigger('pointerup'); await flushPromises()
  expect(h.wrapper.text()).toContain('正在同步')
  const changed = playerState(); changed.sequence++; changed.playback_observation.control_target!.queue_item_id = 'item-b'; changed.playback_observation.control_target!.token = 'second-occurrence'; changed.playback_observation.bound_queue_item_id = 'item-b'; changed.playback_observation.position_seconds = 4
  h.store.acceptRefresh(parseSnapshot(changed), 1); await flushPromises()
  expect(h.wrapper.text()).not.toContain('正在同步')
  expect(slider.element).toHaveProperty('value', '4')
  h.wrapper.unmount()
})
it('successful seek retains sync feedback during backend observation invalidation until a fresh matching sample', async () => {
  const unobserved = playerState(); unobserved.sequence++
  Object.assign(unobserved.playback_observation, fixture.empty_snapshot.playback_observation)
  const h = playerPage(Response.json({ ...fixture.playback_receipt, position_seconds: 80, updated_at: '2026-10-09T08:00:02Z' }), Response.json(unobserved))
  const slider = h.wrapper.get('input')
  await slider.trigger('pointerdown'); await slider.setValue('80'); await slider.trigger('pointerup'); await flushPromises()
  expect(h.wrapper.text()).toContain('操作已确认')
  expect(h.wrapper.text()).toContain('正在同步')
  expect(h.wrapper.get('button[data-testid="primary-playback"]').attributes('disabled')).toBeDefined()
  expect(h.wrapper.get('button[aria-label="下一首"]').attributes('disabled')).toBeDefined()
  const fresh = playerState(); fresh.sequence += 2; fresh.playback_observation.observed_at = '2026-10-09T08:00:03Z'; fresh.playback_observation.position_seconds = 80
  h.store.acceptRefresh(parseSnapshot(fresh), 1); await flushPromises()
  expect(h.wrapper.text()).not.toContain('正在同步')
  expect(slider.element).toHaveProperty('value','80')
  h.wrapper.unmount()
})
