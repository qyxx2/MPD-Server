import { expect, it } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory } from 'vue-router'
import golden from '../fixtures/library-sync.json'
import { createApiClient } from '../../src/services/api'
import { createRealtimeClient, type RealtimeSocket } from '../../src/services/realtime'
import { parseSnapshot, parseRealtimeFrame } from '../../src/services/wire'
import { createPlayerStore } from '../../src/stores/player'
import { createPlayerRouter } from '../../src/router'
import AppShell from '../../src/components/layout/AppShell.vue'

class Socket implements RealtimeSocket {
  listeners = new Map<string, Set<(event: { data?: unknown }) => void>>()
  addEventListener(type: string, listener: (event: { data?: unknown }) => void) {
    const set = this.listeners.get(type) ?? new Set(); set.add(listener); this.listeners.set(type, set)
  }
  removeEventListener(type: string, listener: (event: { data?: unknown }) => void) { this.listeners.get(type)?.delete(listener) }
  close() {}
  emit(type: string, value?: unknown) { this.listeners.get(type)?.forEach(listener => listener({ data: JSON.stringify(value) })) }
}

it('server_fixture_updates_appbar_without_manual_refresh', async () => {
  const requests: string[] = [], responses = [golden.phases[1], golden.phases[2], golden.phases[3]]
  const api = createApiClient({ origin: 'http://localhost', fetch: async (url, init) => {
    const path = new URL(String(url)).pathname
    requests.push(`${init?.method} ${path}`)
    if (path === '/api/favorites/members') return Response.json({ song_ids: [] })
    if (path === '/api/state') return Response.json(responses.shift())
    throw new Error(`Unexpected read ${path}`)
  } })
  const store = createPlayerStore(), sockets: Socket[] = []
  const realtime = createRealtimeClient({ api, store, clock: { setTimeout, clearTimeout, random: () => 0 }, socketFactory: () => { const socket = new Socket(); sockets.push(socket); return socket } })
  const router = createPlayerRouter(createMemoryHistory()); await router.push('/library'); await router.isReady()
  const wrapper = mount(AppShell, { props: { store, realtime, api }, global: { plugins: [router] } })
  sockets[0]!.emit('message', golden.initial); await flushPromises()
  await wrapper.get('.status-toggle').trigger('click')
  expect(wrapper.get('.status-details').text()).toContain('曲库同步')
  expect(wrapper.get('.status-details').text()).toContain('同步中')
  const id = golden.phases[1]!.library_sync.activity_id
  expect(wrapper.findAll(`[data-notice="library-sync:${id}"]`)).toHaveLength(1)
  sockets[0]!.emit('message', golden.synced_invalidation); await flushPromises()
  expect(wrapper.get(`[data-notice="library-sync:${id}"]`).text()).toContain('已同步')
  sockets[0]!.emit('message', golden.failure_invalidation); await flushPromises()
  expect(wrapper.get('.status-details').text()).toContain('同步失败')
  expect(wrapper.findAll('.status-toggle')).toHaveLength(1)
  expect(wrapper.get('.status-toggle').classes()).toContain('warning')
  expect(sockets).toHaveLength(1)
  expect(requests.filter(r => r.endsWith('/api/state'))).toHaveLength(3)
  expect(requests.every(r => r.startsWith('GET'))).toBe(true)
  sockets[0]!.emit('close'); await flushPromises()
  expect(wrapper.get('.status-details').text()).toContain('已过期')
  expect(wrapper.get('.status-toggle').classes()).toContain('warning')
  wrapper.unmount()
})

it('decoder_generation_and_disconnect_reject_old_success_until_initial_recovery', async () => {
  const store = createPlayerStore(), newer = parseSnapshot(golden.phases[3])
  store.beginConnection(1); expect(store.acceptInitial(newer, 1)).toBe(true)
  const older = parseSnapshot(golden.phases[2]); older.sequence = newer.sequence + 1
  expect(store.acceptRefresh(older, 1)).toBe('uncovered')
  expect(store.snapshot?.library_sync.status).toBe('FAILED')
  store.markDisconnected(); expect(store.marker.trusted).toBe(false)
  store.beginConnection(2)
  expect(store.acceptRefresh(newer, 1)).toBe('obsolete')
  const restarted = structuredClone(newer); restarted.epoch = 'new-epoch'; restarted.sequence = 0; restarted.library_sync = parseSnapshot(golden.phases[0]).library_sync
  expect(store.acceptInitial(restarted, 2)).toBe(true)
  expect(store.snapshot?.library_sync.status).toBe('IDLE')
  expect(() => parseRealtimeFrame({ ...golden.synced_invalidation, domains: ['made-up'] })).toThrow()
  expect(() => parseSnapshot({ ...golden.phases[1], library_sync: { ...golden.phases[1]!.library_sync, status: 'made-up' } })).toThrow()
  expect(() => parseSnapshot({ ...golden.phases[1], library_sync: { ...golden.phases[1]!.library_sync, generation: -1 } })).toThrow()
})
