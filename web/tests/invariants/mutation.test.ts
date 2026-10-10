import { expect, test } from 'vitest'
import fixture from '../fixtures/wire.json'
import { createApiClient } from '../../src/services/api'
import { parsePlaybackState, parseRealtimeFrame } from '../../src/services/wire'
import { deferred, transport } from '../support/transport'

const decode = parsePlaybackState

test('same key retry preserves immutable canonical payload after an unknown outcome', async () => {
  const network = transport(new TypeError('timeout'), Response.json(fixture.playback_receipt))
  const api = createApiClient({ fetch: network.fetch, origin: 'https://music.example:8443' })
  const payload = { target: { token: 'opaque', queue_item_id: 'item-a' }, seconds: 38 }
  const intent = api.createIntent('POST', '/api/playback/seek', payload)
  payload.target.token = 'changed'
  await expect(api.send(intent, decode)).rejects.toMatchObject({ kind: 'network' })
  expect(network.requests).toHaveLength(1)
  expect(await api.send(intent, decode)).toEqual(fixture.playback_receipt)
  expect(network.requests.map(r => r.init?.body)).toEqual([
    '{"seconds":38,"target":{"queue_item_id":"item-a","token":"opaque"}}',
    '{"seconds":38,"target":{"queue_item_id":"item-a","token":"opaque"}}',
  ])
  expect(network.requests.map(r => new Headers(r.init?.headers).get('Idempotency-Key'))).toEqual([intent.key, intent.key])
  expect(Object.isFrozen(intent)).toBe(true)
  expect(Object.isFrozen(intent.payload)).toBe(true)
  expect(Object.isFrozen((intent.payload as typeof payload).target)).toBe(true)
  expect(api.createIntent('POST', '/api/playback/seek', payload).key).not.toBe(intent.key)
})

test('204 mutation confirms receipt without guessing state or decoding empty JSON', async () => {
  const network = transport(new Response(null, { status: 204 }))
  const api = createApiClient({ fetch: network.fetch, origin: 'http://music.example' })
  const intent = api.createIntent('DELETE', '/api/playback/queue/item-b', undefined)
  expect(await api.send(intent, value => value)).toBeUndefined()
  expect(network.requests[0]?.init?.body).toBeUndefined()
})

test('typed conflict preserves last confirmed facts and does not resend', async () => {
  const network = transport(Response.json(fixture.error, { status: 409 }))
  const api = createApiClient({ fetch: network.fetch, origin: 'http://music.example' })
  const intent = api.createIntent('POST', '/api/playback/resume', { target: { queue_item_id: 'old', token: 'old' } })
  await expect(api.send(intent, decode)).rejects.toMatchObject({ status: 409, code: 'PLAYBACK_TARGET_CONFLICT' })
  expect(network.requests).toHaveLength(1)
})

test.each([NaN, Infinity, { seconds: undefined }, new Date(), { value: () => 1 }])('invalid JSON intent is rejected instead of silently changing payload: %s', payload => {
  const api = createApiClient({ fetch, origin: 'https://music.example' })
  expect(() => api.createIntent('POST', '/api/playback/seek', payload as any)).toThrow()
})

test('invalidation cannot settle a pending HTTP receipt', async () => {
  const ack = deferred<Response>()
  const network = transport(ack.promise)
  const api = createApiClient({ fetch: network.fetch, origin: 'http://music.example' })
  const intent = api.createIntent('POST', '/api/playback/pause', undefined)
  let settled = false
  const pending = api.send(intent, decode).then(value => { settled = true; return value })
  expect(parseRealtimeFrame(fixture.invalidate_frame).type).toBe('invalidate')
  await Promise.resolve()
  expect(settled).toBe(false)
  ack.resolve(Response.json(fixture.playback_receipt))
  expect(await pending).toEqual(fixture.playback_receipt)
  expect(network.requests).toHaveLength(1)
})
