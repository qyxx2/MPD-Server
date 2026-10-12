import { afterEach, expect, it } from 'vitest'
import type { VueWrapper } from '@vue/test-utils'
import { libraryPage } from '../support/library'
import { fixture, playerState, flushPromises, playerPage } from '../support/player'
import { transport, deferred } from '../support/transport'
import info from '../fixtures/settings.json'
let wrapper: VueWrapper
async function panel(...responses: Parameters<typeof transport>) {
  const network = transport(...responses)
  const h = await libraryPage('/settings', (path, init) => {
    if (path === '/api/system/mpd') return Promise.resolve(Response.json(info))
    if (path === '/api/system/mpd/connection') return Promise.resolve(Response.json({ active: { host: 'mpd', port: 6600 }, saved: null, restart_required: false }))
    if (init?.method === 'PUT' || path === '/api/state') return network.fetch(`http://localhost${path}`, init)
  })
  wrapper = h.wrapper; return { ...h, network }
}
afterEach(() => wrapper?.unmount())
it('failed Output receipt preserves observed fact and reports typed failure only at the top', async () => {
  const reply = deferred<Response>(), h = await panel(reply.promise, Response.json(playerState()))
  await wrapper.get('[data-output-switch]').trigger('click')
  expect(wrapper.get('[data-testid="confirmed-output"]').text()).toContain('已启用')
  expect(wrapper.get('[data-output-switch]').attributes('disabled')).toBeDefined()
  reply.resolve(Response.json({ error: { code: 'OUTPUT_CONFIRMATION_FAILED', message: '无法确认', details: null } }, { status: 502 })); await flushPromises()
  expect(wrapper.get('[data-testid="confirmed-output"]').text()).toContain('已启用')
  expect(wrapper.get('.status-details').text()).toContain('OUTPUT_CONFIRMATION_FAILED')
  expect(wrapper.get('[aria-label="音频输出"]').text()).not.toContain('OUTPUT_CONFIRMATION_FAILED')
  expect(h.store.snapshot!.queue).toEqual(playerState().queue)
  expect(JSON.parse(h.network.requests[0]!.init!.body as string)).toEqual({ enabled: false, mode: 'NAS_DAC' })
})
it('REST aliases never install an old receipt over newer WS confirmed facts', async () => {
  const reply = deferred<Response>(), h = await panel(reply.promise, Response.json(playerState()))
  await wrapper.get('[data-output-switch]').trigger('click')
  const newer = playerState(); newer.sequence++; newer.output.states[0]!.status = 'INACTIVE'; newer.output.states[0]!.sample_rate = null
  h.store.acceptRefresh(newer, 1); await flushPromises()
  reply.resolve(Response.json(fixture.rest_output)); await flushPromises()
  expect(wrapper.get('[data-testid="confirmed-output"]').text()).toContain('未启用')
  expect(wrapper.get('[data-testid="confirmed-output"]').text()).not.toContain('96 kHz')
  expect(h.store.snapshot!.sequence).toBe(newer.sequence)
  expect(wrapper.find('audio').exists()).toBe(false)
})
it('late receipt across a new epoch retires recovery and never automatically retries', async () => {
  const reply = deferred<Response>(), h = await panel(reply.promise)
  await wrapper.get('[data-output-switch]').trigger('click')
  h.store.markDisconnected(); h.store.beginConnection(2)
  const s = playerState(); s.epoch = 'next'; s.output.states[0]!.status = 'INACTIVE'
  h.store.acceptInitial(s, 2); await flushPromises()
  reply.resolve(Response.json(fixture.rest_output)); await flushPromises()
  expect(wrapper.get('[data-testid="confirmed-output"]').text()).toContain('未启用')
  const task = h.tasks.entries.value.find(r => r.intent.path === '/api/system/output')!
  expect(task.state).toBe('retired'); expect(task.retry).toBeUndefined()
  expect(h.network.requests).toHaveLength(1)
})
it('unknown stale unavailable and PREPARING cannot control or borrow source metadata', async () => {
  const h = await panel()
  const s = playerState(); s.sequence++; s.current_song!.sample_rate_hz = 192000
  Object.assign(s.output.states[0]!, { sample_rate: null, bit_depth: null, format: null, channels: null })
  s.output_observation.freshness = 'unknown'; s.output_observation.observed_at = null
  h.store.acceptRefresh(s, 1); await flushPromises()
  expect(wrapper.get('[data-testid="confirmed-output"]').text()).toContain('尚未确认')
  expect(wrapper.get('[data-output-switch]').attributes('disabled')).toBeDefined()
  s.sequence++; s.output_observation.freshness = 'stale'; s.output_observation.observed_at = s.captured_at
  h.store.acceptRefresh(s, 1); await flushPromises(); expect(wrapper.text()).toContain('已过期')
  s.sequence++; s.output_observation.freshness = 'fresh'; s.output.states[0]!.status = 'UNAVAILABLE'
  h.store.acceptRefresh(s, 1); await flushPromises(); expect(wrapper.get('[data-output-switch]').attributes('disabled')).toBeDefined()
  s.sequence++; s.output.states[0]!.status = 'ACTIVE'; s.output.last_request = { mode: 'NAS_DAC', enabled: true, status: 'PREPARING', error_code: null, error_message: null, updated_at: s.captured_at }
  h.store.acceptRefresh(s, 1); await flushPromises()
  expect(wrapper.get('[data-output-switch]').attributes('disabled')).toBeDefined()
  expect(wrapper.get('.status-details').text()).toContain('准备中')
  expect(wrapper.text()).not.toContain('192 kHz'); expect(h.network.requests).toHaveLength(0)
})
it.each(['PREPARING', 'SWITCH_FAILED'] as const)('new canonical %s remains separate from the local successful receipt', async status => {
  const reply = deferred<Response>(), h = await panel(reply.promise, Response.json(playerState()))
  await wrapper.get('[data-output-switch]').trigger('click')
  const newer = playerState(); newer.sequence++
  newer.output.last_request = { mode: 'NAS_DAC', enabled: false, status, updated_at: newer.captured_at, error_code: status === 'SWITCH_FAILED' ? 'OUTPUT_CONFIRMATION_FAILED' : null, error_message: null }
  h.store.acceptRefresh(newer, 1); await flushPromises()
  reply.resolve(Response.json(fixture.rest_output)); await flushPromises()
  expect(h.tasks.entries.value.find(r => r.intent.path === '/api/system/output')!.state).toBe('confirmed')
  expect(wrapper.get('.status-details').text()).toContain(status === 'PREPARING' ? '准备中' : 'OUTPUT_CONFIRMATION_FAILED')
  expect(wrapper.get('[data-testid="confirmed-output"]').text()).toContain('已启用')
})
it('product Player keeps only DAC confirmed summary and has no output controls', async () => {
  const h = playerPage(); wrapper = h.wrapper
  const s = playerState(); s.sequence++; Object.assign(s.output.states[0]!, { sample_rate: null, bit_depth: null, format: null, channels: null })
  h.store.acceptRefresh(s, 1); await flushPromises()
  expect(wrapper.find('[aria-label="音频输出"]').exists()).toBe(false)
  expect(wrapper.find('[data-output-switch]').exists()).toBe(false)
  expect(wrapper.get('[data-testid="output-fact"]').text()).toContain('已启用')
  expect(wrapper.get('[data-testid="output-fact"]').attributes('title')).toContain('参数未知')
  s.sequence++; s.output.states[0]!.status = 'INACTIVE'; h.store.acceptRefresh(s, 1); await flushPromises()
  expect(wrapper.get('[data-testid="output-fact"]').text()).toContain('未启用')
  expect(h.network.requests).toHaveLength(0)
})
