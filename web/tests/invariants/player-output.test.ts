import type { RestOutputSnapshot } from '../../src/types/api'
import { afterEach, expect, it } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import OutputPanel from '../../src/components/player/OutputPanel.vue'
import { playerKey } from '../../src/components/player/playerFacts'
import { playerRuntimeKey } from '../../src/components/player/playerActions'
import { createApiClient } from '../../src/services/api'
import { createPlayerStore } from '../../src/stores/player'
import { parseSnapshot } from '../../src/services/wire'
import { fixture, playerState, flushPromises } from '../support/player'
import { transport, deferred } from '../support/transport'
let wrapper: VueWrapper
function panel(...responses: Parameters<typeof transport>) {
  const network = transport(...responses), store = createPlayerStore()
  store.beginConnection(1); store.acceptInitial(playerState(), 1)
  const api = createApiClient({ origin: 'http://localhost', fetch: network.fetch })
  const refresh = async () => { store.acceptRefresh(await api.get('/api/state', parseSnapshot), 1) }
  wrapper = mount(OutputPanel, { global: { provide: { [playerKey as symbol]: store, [playerRuntimeKey as symbol]: { api, refresh } } } })
  return { store, network }
}
afterEach(() => wrapper?.unmount())
it('failed Output receipt preserves the observed fact and reports typed failure separately', async () => {
  const response = deferred<Response>(), s = playerState(); s.sequence++
  const h = panel(response.promise, Response.json(s))
  await wrapper.get('button[aria-label="停用 NAS DAC"]').trigger('click')
  expect(wrapper.get('[data-testid="confirmed-output"]').text()).toContain('已启用')
  expect(wrapper.get('[data-testid="output-request"]').text()).toContain('正在停用')
  expect(wrapper.get('button[aria-label="启用 NAS DAC"]').attributes('disabled')).toBeDefined()
  response.resolve(Response.json({ error: { code: 'OUTPUT_CONFIRMATION_FAILED', message: '无法确认', details: null } }, { status: 502 }))
  await flushPromises()
  expect(wrapper.get('[data-testid="confirmed-output"]').text()).toContain('已启用')
  expect(wrapper.get('[data-testid="output-request"]').text()).toContain('OUTPUT_CONFIRMATION_FAILED')
  expect(h.store.snapshot!.output.states[0]!.status).toBe('ACTIVE')
  expect(h.store.snapshot!.queue).toEqual(s.queue); expect(h.store.snapshot!.playback).toEqual(s.playback)
  expect(h.network.requests[0]!.url).toBe('http://localhost/api/system/output')
  expect(h.network.requests[0]!.init!.method).toBe('PUT')
  expect(JSON.parse(h.network.requests[0]!.init!.body as string)).toEqual({ enabled: false, mode: 'NAS_DAC' })
})
it('REST aliases and WS snake_case interleave without an old receipt overwriting a newer confirmed fact', async () => {
  const response = deferred<Response>(), h = panel(response.promise, Response.json(playerState()))
  await wrapper.get('button[aria-label="停用 NAS DAC"]').trigger('click')
  const newer = playerState(); newer.sequence++; newer.output.states[0]!.status = 'INACTIVE'; newer.output.states[0]!.sample_rate = null
  h.store.acceptRefresh(newer, 1); await flushPromises()
  response.resolve(Response.json(fixture.rest_output)); await flushPromises()
  expect(wrapper.get('[data-testid="confirmed-output"]').text()).toContain('未启用')
  expect(wrapper.get('[data-testid="confirmed-output"]').text()).not.toContain('96 kHz')
  expect(h.store.snapshot!.sequence).toBe(newer.sequence)
  expect(wrapper.find('audio').exists()).toBe(false)
  expect(wrapper.text()).toContain('CLIENT_STREAM'); expect(wrapper.text()).toContain('尚未支持')
})
it('late receipt across reconnect is retired; no automatic retry and output controls stay read-only', async () => {
  const response = deferred<Response>(), h = panel(response.promise)
  await wrapper.get('button[aria-label="停用 NAS DAC"]').trigger('click')
  h.store.markDisconnected(); await flushPromises()
  expect(wrapper.get('button[aria-label="启用 NAS DAC"]').attributes('disabled')).toBeDefined()
  h.store.beginConnection(2)
  const s = playerState(); s.epoch = 'next'; s.output.states[0]!.status = 'INACTIVE'
  h.store.acceptInitial(s, 2); await flushPromises()
  response.resolve(Response.json(fixture.rest_output)); await flushPromises()
  expect(wrapper.get('[data-testid="confirmed-output"]').text()).toContain('未启用')
  expect(wrapper.get('[data-testid="output-request"]').text()).not.toContain('成功')
  expect(h.network.requests).toHaveLength(1)
})
it('timeout retry reuses the captured intent and does not speculate output; fresh read converges success', async () => {
  const s = playerState(); s.sequence++; s.output.states[0]!.status = 'INACTIVE'
  const h = panel(new Error('timeout'), Response.json(playerState()), Response.json(fixture.rest_output), Response.json(s))
  await wrapper.get('button[aria-label="停用 NAS DAC"]').trigger('click'); await flushPromises()
  expect(wrapper.get('[data-testid="confirmed-output"]').text()).toContain('已启用')
  expect(wrapper.get('[data-testid="output-request"]').text()).toContain('结果未知')
  await wrapper.get('button[aria-label="重试输出请求"]').trigger('click'); await flushPromises()
  const writes = h.network.requests.filter(r => r.init?.method === 'PUT')
  expect(writes).toHaveLength(2)
  expect(writes[0]!.init!.headers).toEqual(writes[1]!.init!.headers)
  expect(writes[0]!.init!.body).toBe(writes[1]!.init!.body)
  expect(wrapper.get('[data-testid="confirmed-output"]').text()).toContain('未启用')
})
it('unknown stale unavailable and PREPARING states cannot control; source metadata never fills output parameters', async () => {
  const h = panel()
  const s = playerState(); s.sequence++; s.current_song!.sample_rate_hz = 192000; s.output.states[0]!.sample_rate = null; s.output.states[0]!.bit_depth = null; s.output.states[0]!.format = null; s.output.states[0]!.channels = null
  s.output_observation.freshness = 'unknown'; s.output_observation.observed_at = null
  h.store.acceptRefresh(s, 1); await flushPromises()
  expect(wrapper.get('[data-testid="confirmed-output"]').text()).toContain('尚未确认')
  expect(wrapper.get('button[aria-label="启用 NAS DAC"]').attributes('disabled')).toBeDefined()
  s.sequence++; s.output_observation.freshness = 'stale'; s.output_observation.observed_at = s.captured_at
  h.store.acceptRefresh(s, 1); await flushPromises(); expect(wrapper.text()).toContain('已过期')
  s.sequence++; s.output_observation.freshness = 'fresh'; s.output.states[0]!.status = 'UNAVAILABLE'
  h.store.acceptRefresh(s, 1); await flushPromises(); expect(wrapper.text()).toContain('不可用')
  s.sequence++; s.output.states[0]!.status = 'ACTIVE'
  s.output.last_request = { mode: 'NAS_DAC', enabled: true, status: 'PREPARING', error_code: null, error_message: null, updated_at: s.captured_at }
  h.store.acceptRefresh(s, 1); await flushPromises(); expect(wrapper.get('button[aria-label="停用 NAS DAC"]').attributes('disabled')).toBeDefined()
  expect(wrapper.text()).not.toContain('192 kHz'); expect(wrapper.text()).toContain('参数未知'); expect(h.network.requests).toHaveLength(0)
})
it('product Player shows DAC facts above progress without an output card or mutation controls', async () => {
  const { playerPage } = await import('../support/player')
  const h = playerPage(); wrapper = h.wrapper
  const s = playerState(); s.sequence++
  Object.assign(s.output.states[0]!, { sample_rate: null, bit_depth: null, format: null, channels: null })
  h.store.acceptRefresh(s, 1); await flushPromises()
  expect(wrapper.find('[aria-label="音频输出"]').exists()).toBe(false)
  expect(wrapper.find('button[aria-label="停用 NAS DAC"]').exists()).toBe(false)
  expect(wrapper.text()).not.toContain('CLIENT_STREAM')
  expect(wrapper.get('[data-testid="output-fact"]').text()).toContain('已启用')
  expect(wrapper.get('[data-testid="output-fact"]').attributes('title')).toContain('参数未知')
  s.sequence++; s.output.states[0]!.status = 'INACTIVE'
  h.store.acceptRefresh(s, 1); await flushPromises()
  expect(wrapper.get('[data-testid="output-fact"]').text()).toContain('未启用')
  for (const button of wrapper.findAll('button')) expect(button.attributes('aria-label') || button.text()).toBeTruthy()
  expect(h.network.requests).toHaveLength(0)
})
it('successful HTTP with failed authoritative read keeps the old fact and gives separate read feedback', async () => {
  const receipt: RestOutputSnapshot = structuredClone(fixture.rest_output) as RestOutputSnapshot
  receipt.last_request!.status = 'SUCCEEDED'; receipt.last_request!.errorCode = null; receipt.last_request!.errorMessage = null
  const h = panel(Response.json(receipt), new Error('read failed'))
  await wrapper.get('button[aria-label="停用 NAS DAC"]').trigger('click'); await flushPromises()
  expect(wrapper.get('[data-testid="confirmed-output"]').text()).toContain('已启用')
  expect(wrapper.get('[data-testid="output-request"]').text()).toContain('已确认')
  expect(wrapper.text()).toContain('状态读取失败')
  expect(h.network.requests.filter(r => r.init?.method === 'PUT')).toHaveLength(1)
})
it.each(['PREPARING', 'SWITCH_FAILED'] as const)('a newer authoritative %s remains visible after a local successful receipt', async status => {
  const receipt: RestOutputSnapshot = structuredClone(fixture.rest_output) as RestOutputSnapshot
  Object.assign(receipt.last_request!, { status: 'SUCCEEDED', errorCode: null, errorMessage: null })
  const h = panel(Response.json(receipt), Response.json(playerState()))
  await wrapper.get('button[aria-label="停用 NAS DAC"]').trigger('click'); await flushPromises()
  const newer = playerState(); newer.sequence++
  newer.output.last_request = { mode: 'NAS_DAC', enabled: false, status, updated_at: '2026-10-09T08:00:10Z', error_code: status === 'SWITCH_FAILED' ? 'OUTPUT_CONFIRMATION_FAILED' : null, error_message: status === 'SWITCH_FAILED' ? '无法确认其它请求' : null }
  const { parseRealtimeFrame } = await import('../../src/services/wire')
  const frame = parseRealtimeFrame(JSON.stringify({ type: 'snapshot', protocol_version: 1, epoch: newer.epoch, sequence: newer.sequence, state: newer }))
  if (frame.type !== 'snapshot') throw new Error('snapshot required')
  h.store.acceptRefresh(frame.state, 1); await flushPromises()
  expect(wrapper.text()).toContain(status === 'PREPARING' ? '准备中' : 'OUTPUT_CONFIRMATION_FAILED')
  expect(wrapper.get('[data-testid="confirmed-output"]').text()).toContain('已启用')
  expect(wrapper.get('[data-testid="output-request"]').text()).toContain('已确认')
  if (status === 'PREPARING') expect(wrapper.get('button[aria-label="停用 NAS DAC"]').attributes('disabled')).toBeDefined()
})
