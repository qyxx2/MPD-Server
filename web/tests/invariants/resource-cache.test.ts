import { expect, it } from 'vitest'
import fixture from '../fixtures/wire.json'
import { deferred, transport } from '../support/transport'
import { createApiClient } from '../../src/services/api'
import { createPlayerStore, type ResourceMarker } from '../../src/stores/player'
import { createResourceCache } from '../../src/stores/resourceCache'
import { createLibraryStore } from '../../src/stores/library'
import { createPlaylistsStore } from '../../src/stores/playlists'
import { parseSnapshot } from '../../src/services/wire'

const marker = (library = 1, playlist = 1, epoch = 'one'): ResourceMarker => ({ epoch, sequence: 1, revisions: { library, playlist }, generation: 1, trusted: true })
const decode = (value: unknown) => {
  if (typeof value !== 'object' || value === null || !('name' in value) || typeof value.name !== 'string') throw new Error('invalid resource')
  return { name: value.name }
}
it('playlist data depends on both playlist and library watermarks, before snapshot refresh', async () => {
  const old = deferred<Response>(); const newer = deferred<Response>()
  const network = transport(Response.json({ name: 'confirmed' }), old.promise, newer.promise)
  const api = createApiClient({ fetch: network.fetch, origin: 'http://music.local' })
  const player = createPlayerStore(); player.beginConnection(1)
  player.acceptInitial(parseSnapshot(fixture.snapshot), 1)
  const cache = createPlaylistsStore({ api, player, decode })
  await cache.read('/api/favorites')
  player.invalidate({ type: 'invalidate', protocol_version: 1, epoch: fixture.snapshot.epoch, sequence: 13, domains: ['playlist'], revisions: { library: 3, playlist: 6 } }, 1)
  expect(cache.entry('/api/favorites').fresh).toBe(false)
  const read = cache.read('/api/favorites')
  player.invalidate({ type: 'invalidate', protocol_version: 1, epoch: fixture.snapshot.epoch, sequence: 14, domains: ['library'], revisions: { library: 4, playlist: 6 } }, 1)
  expect(player.snapshot?.sequence).toBe(12)
  old.resolve(Response.json({ name: 'old metadata' }))
  await tick()
  expect(cache.entry('/api/favorites').data).toEqual({ name: 'confirmed' })
  expect(cache.entry('/api/favorites').fresh).toBe(false)
  newer.resolve(Response.json({ name: 'current metadata' })); await read
  expect(cache.entry('/api/favorites').data).toEqual({ name: 'current metadata' })
  expect(cache.entry('/api/favorites').fresh).toBe(true)
  cache.stop()
})
const tick = async () => { for (let i = 0; i < 20; i++) await Promise.resolve() }
it('new epoch rejects pending resource response and resets revision comparison', async () => {
  const old = deferred<{ name: string }>(); const current = deferred<{ name: string }>()
  const loads = [old, current]
  const cache = createResourceCache({ dependencies: ['library'], load: () => loads.shift()!.promise })
  cache.invalidate(marker(100, 100))
  const reading = cache.read('song')
  cache.invalidate(marker(1, 1, 'two'))
  old.resolve({ name: 'old epoch' }); await tick()
  expect(cache.entry('song').data).toBeNull()
  current.resolve({ name: 'new epoch' }); await reading
  expect(cache.entry('song').data).toEqual({ name: 'new epoch' })
})
it('query generation and key isolate late search responses; same-key replacement wins', async () => {
  const old = deferred<string>(); const current = deferred<string>()
  const loads = [old, current]
  const cache = createResourceCache({ dependencies: ['library'], load: (key: string) => key === 'other' ? Promise.resolve('other query') : loads.shift()!.promise })
  cache.invalidate(marker())
  const first = cache.read('query')
  await cache.read('other')
  cache.invalidate({ ...marker(), generation: 2 })
  const second = cache.read('query')
  current.resolve('new generation'); await second
  old.resolve('late generation'); expect(await first).toBe('new generation')
  expect(cache.entry('query').data).toBe('new generation')
  expect(cache.entry('other').data).toBe('other query')
})
it('failed resource read retains stale data and error; explicit read retries and coalesces', async () => {
  let count = 0
  const next = deferred<string>()
  const cache = createResourceCache({ dependencies: ['library'], load: async () => {
    count++; if (count === 1) return 'last confirmed'; if (count === 2) throw new Error('read failed'); return await next.promise
  } })
  cache.invalidate(marker())
  await cache.read('song'); cache.invalidate(marker(2))
  await expect(cache.read('song')).rejects.toThrow('read failed')
  expect(cache.entry('song')).toMatchObject({ data: 'last confirmed', fresh: false, loading: false })
  expect(cache.entry('song').error).not.toBeNull()
  const first = cache.read('song'); const second = cache.read('song')
  expect(count).toBe(3)
  next.resolve('new confirmed'); await Promise.all([first, second])
  expect(cache.entry('song')).toMatchObject({ data: 'new confirmed', fresh: true, loading: false, error: null })
})
it('library ignores playlist-only changes; disconnected resources remain read-only stale', async () => {
  const network = transport(Response.json({ name: 'song' }), Response.json({ name: 'read-only song' }))
  const api = createApiClient({ fetch: network.fetch, origin: 'http://music.local' })
  const player = createPlayerStore(); player.beginConnection(1); player.acceptInitial(parseSnapshot(fixture.snapshot), 1)
  const cache = createLibraryStore({ api, player, decode })
  await cache.read('/api/library/songs')
  player.invalidate({ type: 'invalidate', protocol_version: 1, epoch: fixture.snapshot.epoch, sequence: 13, domains: ['playlist'], revisions: { library: 3, playlist: 6 } }, 1)
  expect(cache.entry('/api/library/songs').fresh).toBe(true)
  player.markDisconnected()
  expect(cache.entry('/api/library/songs').fresh).toBe(false)
  await cache.read('/api/library/songs')
  expect(cache.entry('/api/library/songs').data).toEqual({ name: 'read-only song' })
  expect(cache.entry('/api/library/songs').fresh).toBe(false)
  expect(player.writable).toBe(false)
  cache.stop()
})

it('explicit force invalidation retains data and requires a new read', async () => {
  let loads = 0
  const cache = createResourceCache({ dependencies: ['library'], load: async () => ++loads })
  cache.invalidate(marker()); await cache.read('one'); await cache.read('one')
  expect(loads).toBe(1)
  cache.invalidate(marker(), { force: true })
  expect(cache.entry('one')).toMatchObject({ data: 1, fresh: false })
  await cache.read('one'); expect(loads).toBe(2)
})
it('a late failed resource request cannot replace the new generation error or data', async () => {
  const old = deferred<string>(); const next = deferred<string>()
  const loads = [old, next]
  const cache = createResourceCache({ dependencies: ['library'], load: () => loads.shift()!.promise })
  cache.invalidate(marker())
  const first = cache.read('query'); cache.invalidate(marker(2))
  const current = cache.read('query')
  next.resolve('new'); await current
  old.reject(new Error('obsolete')); expect(await first).toBe('new')
  expect(cache.entry('query').error).toBeNull()
})
it('resource entries are reactive and readonly; stop releases dependency watch', async () => {
  const network = transport(Response.json({ name: 'confirmed' }))
  const api = createApiClient({ fetch: network.fetch, origin: 'http://music.local' })
  const player = createPlayerStore(); player.beginConnection(1); player.acceptInitial(parseSnapshot(fixture.snapshot), 1)
  const cache = createLibraryStore({ api, player, decode })
  const entry = cache.entry('/api/library/songs')
  await cache.read('/api/library/songs')
  expect(entry.fresh).toBe(true)
  expect(Object.isFrozen(entry.data)).toBe(true)
  cache.stop(); player.markDisconnected()
  expect(entry.fresh).toBe(true)
})

it('playlist-only snapshot refresh does not invalidate library cache', async () => {
  const network = transport(Response.json({ name: 'song' }))
  const api = createApiClient({ fetch: network.fetch, origin: 'http://music.local' })
  const player = createPlayerStore(); player.beginConnection(1); player.acceptInitial(parseSnapshot(fixture.snapshot), 1)
  const cache = createLibraryStore({ api, player, decode })
  await cache.read('/api/library/songs')
  player.invalidate({ type: 'invalidate', protocol_version: 1, epoch: fixture.snapshot.epoch, sequence: 13, domains: ['playlist'], revisions: { library: 3, playlist: 6 } }, 1)
  player.acceptRefresh(parseSnapshot({ ...fixture.snapshot, sequence: 13, revisions: { library: 3, playlist: 6 } }), 1)
  expect(cache.entry('/api/library/songs').fresh).toBe(true)
  expect(network.requests).toHaveLength(1)
  cache.stop()
})

it('synchronous loader failure clears flight so the next explicit read retries', async () => {
  let calls = 0
  const cache = createResourceCache<string>({ dependencies: ['library'], load: () => {
    calls++
    if (calls === 1) throw new Error('sync transport failure')
    return Promise.resolve('recovered')
  } })
  cache.invalidate(marker())
  await expect(cache.read('song')).rejects.toThrow('sync transport failure')
  expect(cache.entry('song').loading).toBe(false)
  await expect(cache.read('song')).resolves.toBe('recovered')
  expect(calls).toBe(2)
  expect(cache.entry('song').error).toBeNull()
})

it('resource read begun after invalidation survives its covering snapshot', async () => {
  const pending = deferred<Response>()
  const network = transport(pending.promise)
  const api = createApiClient({ fetch: network.fetch, origin: 'http://music.local' })
  const player = createPlayerStore(); player.beginConnection(1); player.acceptInitial(parseSnapshot(fixture.snapshot), 1)
  const cache = createLibraryStore({ api, player, decode })
  const updated = parseSnapshot({ ...fixture.snapshot, sequence: 13, revisions: { library: 4, playlist: 5 } })
  player.invalidate({ type: 'invalidate', protocol_version: 1, epoch: updated.epoch, sequence: 13, domains: ['library'], revisions: updated.revisions }, 1)
  const reading = cache.read('/api/library/songs')
  player.acceptRefresh(updated, 1)
  pending.resolve(Response.json({ name: 'current library' }))
  await expect(reading).resolves.toEqual({ name: 'current library' })
  expect(network.requests).toHaveLength(1)
  expect(cache.entry('/api/library/songs').fresh).toBe(true)
  cache.stop()
})
