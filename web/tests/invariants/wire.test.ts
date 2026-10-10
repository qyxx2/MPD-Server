import type { RestOutputSnapshot } from '../../src/types/api'
import { expect, test } from 'vitest'
import fixture from '../fixtures/wire.json'
import { createApiClient } from '../../src/services/api'
import { parseSnapshot, parseRealtimeFrame, normalizeOutput, WireError } from '../../src/services/wire'
import { transport } from '../support/transport'

test('REST and WS decode the actual backend fixture without inventing null values', async () => {
  const network = transport(Response.json(fixture.snapshot))
  const api = createApiClient({ fetch: network.fetch, origin: 'https://music.example' })
  const state = await api.get('/api/state', parseSnapshot)
  const frame = parseRealtimeFrame(fixture.snapshot_frame)
  expect(frame.type).toBe('snapshot')
  if (frame.type !== 'snapshot') throw new Error('wrong frame')
  expect(frame.state).toEqual(state)
  expect(state.playback_observation.duration_seconds).toBeNull()
  expect(state.current_song?.duration).toBeNull()
  expect(state.queue.items.map(item => item.queue_item_id)).toEqual(['item-a', 'item-b'])
  expect(parseSnapshot(fixture.empty_snapshot).playback).toBeNull()
})

test('old server missing target and additive actual fields remains unconfirmed', () => {
  const legacy = structuredClone(fixture.snapshot) as Record<string, any>
  for (const field of ['control_target', 'actual_current', 'actual_freshness', 'bound_queue_item_id', 'sync_status']) delete legacy.playback_observation[field]
  const state = parseSnapshot(legacy)
  expect(state.playback_observation).toMatchObject({ control_target: null, actual_current: null, actual_freshness: 'unknown', bound_queue_item_id: null, sync_status: 'UNBOUND' })
  expect(legacy.playback_observation).not.toHaveProperty('control_target')
})

test('Output REST aliases explicitly map into realtime without losing request failure or confirmed facts', () => {
  const normalized = normalizeOutput(fixture.rest_output as RestOutputSnapshot)
  expect(normalized).toEqual(fixture.snapshot.output)
  expect(normalized.states[0]).toMatchObject({ status: 'ACTIVE', sample_rate: 96000, bit_depth: 24, target_client_id: null })
  expect(normalized.last_request).toMatchObject({ status: 'SWITCH_FAILED', enabled: false, error_code: 'OUTPUT_FAILED' })
  expect(normalized.states[1]?.stream_url).toBeNull()
})

test.each([
  ['partial snapshot', {}],
  ['unknown version', { ...fixture.snapshot_frame, protocol_version: 2 }],
  ['unknown frame', { ...fixture.snapshot_frame, type: 'patch' }],
  ['epoch mismatch', { ...fixture.snapshot_frame, epoch: 'other' }],
  ['sequence mismatch', { ...fixture.snapshot_frame, sequence: 99 }],
  ['invalid JSON', '{'],
])('malformed WS frame fails closed: %s', (_label, value) => {
  expect(() => parseRealtimeFrame(value)).toThrow(WireError)
})

test.each([
  ['unknown transport state', (s: any) => { s.playback.state = 'BUFFERING' }],
  ['unknown freshness', (s: any) => { s.playback_observation.freshness = 'probably' }],
  ['unknown queue source', (s: any) => { s.queue.items[0].source = 'EXTERNAL' }],
  ['negative sequence', (s: any) => { s.sequence = -1 }],
  ['missing mandatory output', (s: any) => { delete s.output }],
  ['invalid nullable number', (s: any) => { s.playback_observation.position_seconds = '37' }],
  ['nonfinite position', (s: any) => { s.playback_observation.position_seconds = Infinity }],
  ['invalid target', (s: any) => { s.playback_observation.control_target.token = '' }],
])('malformed snapshot rejected: %s', (_label, change) => {
  const state = structuredClone(fixture.snapshot)
  change(state)
  expect(() => parseSnapshot(state)).toThrow(WireError)
})

test('live invalidate validates domains and revision counters without becoming a state payload', () => {
  expect(parseRealtimeFrame(JSON.stringify(fixture.invalidate_frame))).toEqual(fixture.invalidate_frame)
  expect(() => parseRealtimeFrame({ ...fixture.invalidate_frame, domains: ['future-domain'] })).toThrow(WireError)
  expect(() => parseRealtimeFrame({ ...fixture.invalidate_frame, revisions: { library: null, playlist: 5 } })).toThrow(WireError)
})

test.each([
  ['actual MPD entry identity', (s: any) => { s.playback_observation.actual_current.entry_id = 1.5 }],
  ['queue occurrence position', (s: any) => { s.queue.items[0].position = 0.5 }],
  ['Song sample rate', (s: any) => { s.current_song.sample_rate_hz = 44100.5 }],
  ['Output bit depth', (s: any) => { s.output.states[0].bit_depth = 24.5 }],
])('declared integer wire fields reject fractional values: %s', (_label, change) => {
  const state = structuredClone(fixture.snapshot)
  change(state)
  expect(() => parseSnapshot(state)).toThrow(WireError)
})

test('integer decoder keeps negative Played positions and large nanosecond timestamps', () => {
  const state = structuredClone(fixture.snapshot) as any
  state.queue.items[0].position = -1
  state.current_song.file_mtime_ns = 1791532800000000000
  expect(parseSnapshot(state).queue.items[0]?.position).toBe(-1)
  expect(parseSnapshot(state).current_song?.file_mtime_ns).toBe(1791532800000000000)
})
