import { expect, test } from 'vitest'
import { createApiClient } from '../../src/services/api'

test('same-origin HTTPS uses wss without changing host', () => {
  const api = createApiClient({ fetch, origin: 'https://music.example:8443/player' })
  expect(api.realtimeUrl).toBe('wss://music.example:8443/api/realtime')
})

import { transport } from '../support/transport'

const decode = (value: unknown) => value as { confirmed: boolean }

test('HTTP uses ws and GET stays same-origin without an idempotency key', async () => {
  const network = transport(Response.json({ confirmed: true }))
  const api = createApiClient({ fetch: network.fetch, origin: 'http://192.168.1.4:5173/view' })
  expect(api.realtimeUrl).toBe('ws://192.168.1.4:5173/api/realtime')
  expect(await api.get('/api/state', decode)).toEqual({ confirmed: true })
  expect(network.requests).toEqual([{ url: 'http://192.168.1.4:5173/api/state', init: { method: 'GET', cache: 'no-store', redirect: 'error' } }])
})

test('204 does not parse empty JSON and decodes undefined', async () => {
  const network = transport(new Response(null, { status: 204 }))
  const api = createApiClient({ fetch: network.fetch, origin: 'https://music.example' })
  expect(await api.get('/api/state', value => value === undefined ? 'empty' : 'wrong')).toBe('empty')
})

test('typed HTTP error preserves status code and details', async () => {
  const network = transport(Response.json({ error: { code: 'PLAYBACK_TARGET_CONFLICT', message: 'Changed', details: { current: 'b' } } }, { status: 409 }))
  const api = createApiClient({ fetch: network.fetch, origin: 'http://music.example' })
  await expect(api.get('/api/state', decode)).rejects.toMatchObject({ name: 'ApiError', kind: 'http', status: 409, code: 'PLAYBACK_TARGET_CONFLICT', details: { current: 'b' } })
})

test('network failure is unknown and never automatically retries', async () => {
  const network = transport(new TypeError('Connection lost'))
  const api = createApiClient({ fetch: network.fetch, origin: 'http://music.example' })
  await expect(api.get('/api/state', decode)).rejects.toMatchObject({ kind: 'network', code: 'NETWORK_UNKNOWN', status: null })
  expect(network.requests).toHaveLength(1)
})

test('cross-origin and non-API paths are rejected before network access', async () => {
  const network = transport(Response.json({ confirmed: true }))
  const api = createApiClient({ fetch: network.fetch, origin: 'http://music.example' })
  for (const path of ['https://other.example/api/state', '//other.example/api/state', '/outside', '/api/../outside']) {
    await expect(api.get(path, decode)).rejects.toThrow()
  }
  expect(network.requests).toHaveLength(0)
})

test('malformed success JSON is a protocol error rather than a confirmed receipt', async () => {
  const network = transport(new Response('{', { status: 200 }))
  const api = createApiClient({ fetch: network.fetch, origin: 'http://music.example' })
  await expect(api.get('/api/state', decode)).rejects.toMatchObject({ kind: 'wire', code: 'INVALID_RESPONSE', status: 200 })
})

test('body transport loss remains unknown after response headers', async () => {
  const response = new Response('{}')
  response.json = async () => { throw new TypeError('body connection lost') }
  const network = transport(response)
  const api = createApiClient({ fetch: network.fetch, origin: 'http://music.example' })
  await expect(api.get('/api/state', decode)).rejects.toMatchObject({ kind: 'network', code: 'NETWORK_UNKNOWN' })
})
