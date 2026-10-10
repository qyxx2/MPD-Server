import { expect, it } from 'vitest'
import { createPlayerStore } from '../../src/stores/player'
import { parseSnapshot } from '../../src/services/wire'
import { FakeClock } from '../support/transport'
import { playerState } from '../support/player'
// The independent values below catch wall-clock mixing, renewed lifetime and domain writes.
it('display clock uses timed read age and stops at six seconds without modifying canonical', async () => {
  const module = await import('../../src/components/player/playerClock').catch(() => null)
  expect(module?.createPlayerClock).toBeTypeOf('function')
  const store = createPlayerStore(), time = new FakeClock()
  const s = playerState(); s.playback_observation.actual_state = 'playing'; s.playback!.state = 'PLAYING'
  store.beginConnection(1); store.acceptInitial(parseSnapshot(s), 1)
  const clock = module!.createPlayerClock(store, time.now)
  expect(clock.position()).toBe(37) // Untimed initial frame never starts extrapolation.
  store.acceptRefresh(parseSnapshot(s), 1, { receivedAt: time.now(), roundTripMs: 500 })
  time.advance(2000); expect(clock.position()).toBe(39)
  time.advance(10000); expect(clock.position()).toBe(42.5)
  expect(store.snapshot?.playback_observation.position_seconds).toBe(37)
  clock.dispose()
})
it('duplicate samples and same sequence reads do not renew sample life or replace canonical', async () => {
  const module = await import('../../src/components/player/playerClock').catch(() => null)
  expect(module?.createPlayerClock).toBeTypeOf('function')
  const store = createPlayerStore(), time = new FakeClock(), s = playerState()
  s.playback_observation.actual_state = 'playing'
  store.beginConnection(1); store.acceptInitial(parseSnapshot(s), 1)
  const clock = module!.createPlayerClock(store, time.now)
  store.acceptRefresh(parseSnapshot(s), 1, { receivedAt: 0, roundTripMs: 0 })
  time.advance(5000); expect(clock.position()).toBe(42)
  const repeated = playerState(); repeated.playback_observation.actual_state = 'playing'; repeated.captured_at = '2026-10-09T08:00:05Z'; repeated.playback_observation.observed_at = repeated.captured_at; repeated.playback_observation.position_seconds = 99
  store.acceptRefresh(parseSnapshot(repeated), 1, { receivedAt: 5000, roundTripMs: 0 })
  time.advance(3000); expect(clock.position()).toBe(43)
  expect(store.snapshot?.playback_observation.position_seconds).toBe(37)
  clock.dispose()
})
it('pause stale disconnect and background stop extrapolation; return requires a timed read and never adds hidden time', async () => {
  const module = await import('../../src/components/player/playerClock').catch(() => null)
  expect(module?.createPlayerClock).toBeTypeOf('function')
  const store = createPlayerStore(), time = new FakeClock(), s = playerState()
  s.playback_observation.actual_state = 'playing'
  store.beginConnection(1); store.acceptInitial(parseSnapshot(s), 1)
  const clock = module!.createPlayerClock(store, time.now)
  store.acceptRefresh(parseSnapshot(s), 1, { receivedAt: 0, roundTripMs: 0 })
  time.advance(1000); expect(clock.position()).toBe(38)
  clock.setVisible(false); const frozen = clock.position(); time.advance(20000); expect(clock.position()).toBe(frozen)
  clock.setVisible(true); time.advance(1000); expect(clock.position()).toBe(37)
  const paused = playerState(); paused.sequence++; paused.playback_observation.observed_at = '2026-10-09T08:00:22Z'; paused.captured_at = paused.playback_observation.observed_at
  store.acceptRefresh(parseSnapshot(paused), 1, { receivedAt: time.now(), roundTripMs: 0 }); time.advance(2000); expect(clock.position()).toBe(37)
  const stale = playerState(); stale.sequence += 2; stale.playback_observation.freshness = 'stale'
  store.acceptRefresh(parseSnapshot(stale), 1); expect(clock.position()).toBe(null)
  store.markDisconnected(); expect(clock.position()).toBe(null)
  clock.dispose()
})
it('duration end sends no next; repeated URI occurrence and epoch calibrate independently; invalid age fails closed', async () => {
  const module = await import('../../src/components/player/playerClock').catch(() => null)
  expect(module?.createPlayerClock).toBeTypeOf('function')
  const store = createPlayerStore(), time = new FakeClock(), s = playerState()
  s.playback_observation.actual_state = 'playing'; s.playback_observation.duration_seconds = 38
  store.beginConnection(1); store.acceptInitial(parseSnapshot(s), 1)
  const clock = module!.createPlayerClock(store, time.now)
  store.acceptRefresh(parseSnapshot(s), 1, { receivedAt: 0, roundTripMs: 0 }); time.advance(2000); expect(clock.position()).toBe(38)
  expect(store.snapshot?.queue.items).toHaveLength(2); expect(store.snapshot?.history.active_event).toEqual(s.history.active_event)
  const changed = playerState(); changed.sequence++; changed.playback_observation.control_target!.queue_item_id = 'item-b'; changed.playback_observation.bound_queue_item_id = 'item-b'; changed.playback_observation.actual_state = 'playing'; changed.playback_observation.position_seconds = 10
  store.acceptRefresh(parseSnapshot(changed), 1); expect(clock.position()).toBe(10)
  const epoch = playerState(); epoch.epoch = 'new'; epoch.playback_observation.actual_state = 'playing'; epoch.captured_at = '2026-10-09T07:59:59Z'
  store.beginConnection(2); store.acceptInitial(parseSnapshot(epoch), 2)
  store.acceptRefresh(parseSnapshot(epoch), 2, { receivedAt: time.now(), roundTripMs: 0 }); time.advance(1000); expect(clock.position()).toBe(37)
  clock.dispose()
})
it('foreground same playing sample reanchors without adding hidden time or renewing expiry', async () => {
  const { createPlayerClock } = await import('../../src/components/player/playerClock')
  const store = createPlayerStore(), time = new FakeClock(), s = playerState()
  s.playback_observation.actual_state = 'playing'
  store.beginConnection(1); store.acceptInitial(parseSnapshot(s), 1)
  const clock = createPlayerClock(store, time.now)
  store.acceptRefresh(parseSnapshot(s), 1, { receivedAt: 0, roundTripMs: 0 })
  time.advance(1000); expect(clock.position()).toBe(38)
  clock.setVisible(false); time.advance(2000); clock.setVisible(true)
  const currentRead = playerState(); currentRead.captured_at = '2026-10-09T08:00:03Z'
  store.acceptRefresh(parseSnapshot(currentRead), 1, { receivedAt: 3000, roundTripMs: 0 })
  expect(clock.position()).toBe(37)
  time.advance(1000); expect(clock.position()).toBe(38)
  time.advance(10000); expect(clock.position()).toBe(40) // original deadline t=6s, anchor t=3s
  const repeated = playerState(); repeated.captured_at = '2026-10-09T08:00:14Z'
  store.acceptRefresh(parseSnapshot(repeated), 1, { receivedAt: time.now(), roundTripMs: 0 })
  expect(clock.position()).toBe(40)
  clock.dispose()
})
it('GET started before foreground return cannot reopen extrapolation', async () => {
  const { createPlayerClock } = await import('../../src/components/player/playerClock')
  const store = createPlayerStore(), time = new FakeClock(), s = playerState()
  s.playback_observation.actual_state = 'playing'
  store.beginConnection(1); store.acceptInitial(parseSnapshot(s), 1)
  const clock = createPlayerClock(store, time.now)
  store.acceptRefresh(parseSnapshot(s), 1, { receivedAt: 0, roundTripMs: 0 })
  clock.setVisible(false); time.advance(2000); clock.setVisible(true)
  store.acceptRefresh(parseSnapshot(s), 1, { receivedAt: 2000, roundTripMs: 1500 })
  time.advance(1000); expect(clock.position()).toBe(37)
  clock.dispose()
})
it('real realtime HTTP measurement calibrates clock through same-sequence store metadata', async () => {
  const { createRealtimeClient } = await import('../../src/services/realtime')
  const { createApiClient } = await import('../../src/services/api')
  const { createPlayerClock } = await import('../../src/components/player/playerClock')
  const { transport, deferred } = await import('../support/transport')
  const store = createPlayerStore(), time = new FakeClock(), s = playerState()
  s.playback_observation.actual_state = 'playing'
  const response = deferred<Response>(), network = transport(response.promise)
  const listeners = new Map<string, (event: {data?:unknown}) => void>()
  const socket = { addEventListener(name:string, fn:(event:{data?:unknown}) => void) { listeners.set(name, fn) }, removeEventListener(name:string) { listeners.delete(name) }, close() {} }
  const realtime = createRealtimeClient({ api: createApiClient({ origin:'http://localhost', fetch:network.fetch }), store, socketFactory:() => socket, now:time.now, clock:{setTimeout,clearTimeout,random:() => 0} })
  const display = createPlayerClock(store, time.now)
  realtime.start(); listeners.get('message')!({ data: JSON.stringify({ type:'snapshot', protocol_version:1, epoch:s.epoch, sequence:s.sequence, state:s }) })
  const reading = realtime.refresh(); await Promise.resolve(); time.advance(1000); response.resolve(Response.json(s)); await reading
  expect(display.position()).toBe(37)
  time.advance(2000); expect(display.position()).toBe(39)
  time.advance(10000); expect(display.position()).toBe(42)
  expect(store.snapshot?.playback_observation.position_seconds).toBe(37)
  expect(network.requests.map(r=>r.init?.method)).toEqual(['GET'])
  realtime.stop(); display.dispose()
})
