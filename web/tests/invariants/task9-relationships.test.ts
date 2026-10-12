import { expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h, inject } from 'vue'
import { createMemoryHistory, RouterView } from 'vue-router'
import fixture from '../fixtures/task9.json'
import info from '../fixtures/settings.json'
import { deferred } from '../support/transport'
import AppShell from '../../src/components/layout/AppShell.vue'
import { createPlayerRouter } from '../../src/router'
import { createPlayerStore } from '../../src/stores/player'
import { createApiClient } from '../../src/services/api'
import { parseSnapshot } from '../../src/services/wire'
import { playlistResourcesKey, type PlaylistResources } from '../../src/stores/playlists'
import { taskActionsKey, type TaskActions } from '../../src/runtime/taskActions'
import { createPlaylistActions } from '../../src/components/library/playlistActions'

// Catches route disposal of sent intents, speculative facts, missing resource
// rereads after ACK, song/item identity confusion and duplicate shell owners.
it('server_fixture_to_resource_action_route_convergence', async () => {
  let phase = 0
  let pending = deferred<Response>()
  const writes: { path: string; init?: RequestInit }[] = []
  const api = createApiClient({ origin: 'http://localhost', fetch: async (input, init) => {
    const path = new URL(String(input)).pathname
    if (init?.method !== 'GET') { writes.push({ path, init }); return pending.promise }
    if (path === '/api/state') return Response.json(fixture.phases[phase]!.snapshot)
    if (path === '/api/system/mpd') return Response.json({ ...info, errors: {} })
    if (path === '/api/system/mpd/connection') return Response.json({ active: { host: 'mpd', port: 6600 }, saved: null, restart_required: false })
    const resources: Record<string, unknown> = fixture.phases[phase]!.resources
    if (path in resources) return Response.json(resources[path])
    throw new Error(`Unexpected read ${path}`)
  } })
  const store = createPlayerStore(); store.beginConnection(1); store.acceptInitial(parseSnapshot(fixture.phases[0]!.snapshot), 1)
  const realtime = { start: vi.fn(), stop: vi.fn(), refresh: async () => { store.acceptRefresh(await api.get('/api/state', parseSnapshot), 1) } }
  const router = createPlayerRouter(createMemoryHistory()); await router.push('/library/favorites'); await router.isReady()
  let tasks!: TaskActions, resources!: PlaylistResources
  const Probe = defineComponent({ setup() { tasks = inject(taskActionsKey)!; resources = inject(playlistResourcesKey)!; return () => null } })
  const wrapper = mount(defineComponent({ render: () => h(AppShell, { store, api, realtime }, { default: () => [h(Probe), h(RouterView)] }) }), { global: { plugins: [router] } })
  try {
    await flushPromises()
    const background = wrapper.get('.app-background').element
    expect(wrapper.findAll('[data-song-id]').map(n => n.attributes('data-song-id'))).toEqual(['a', 'c'])
    const baseline = store.snapshot
    await wrapper.get('[data-song-id="c"] .song-open').trigger('click'); await flushPromises()
    await wrapper.get('[data-favorite-toggle="c"]').trigger('click'); await flushPromises()
    await router.push('/queue'); await flushPromises()
    expect(store.snapshot).toBe(baseline)
    expect(wrapper.find('[data-favorite-display="c"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="operation-status"]')).toHaveLength(1)
    expect(writes.map(r => r.path)).toEqual(['/api/favorites/c'])
    phase = 1; pending.resolve(new Response(null, { status: 204 })); await flushPromises()
    await router.push('/library/favorites'); await flushPromises()
    expect(wrapper.findAll('[data-song-id]').map(n => n.attributes('data-song-id'))).toEqual(['a'])
    expect(tasks.entries.value[0]!.state).toBe('confirmed')
    expect(wrapper.get(`[data-notice="${tasks.entries.value[0]!.intent.key}"]`).text()).toContain('已同步')

    await router.push('/library/playlists/p'); await flushPromises()
    const entry = resources.entry('/api/playlists/p')
    const actions = createPlaylistActions(store, { api, refresh: realtime.refresh }, tasks, resources,
      () => entry.data && 'playlist_id' in entry.data ? entry.data : null, () => entry.fresh, () => false)
    pending = deferred<Response>()
    const added = actions.add('b'); await flushPromises()
    await router.push('/settings'); await flushPromises()
    expect(entry.data && 'song_ids' in entry.data ? entry.data.song_ids : []).toEqual(['c', 'a'])
    phase = 2; pending.resolve(Response.json(fixture.receipts[1])); await added; await flushPromises()
    await router.push('/library/playlists/p'); await flushPromises()
    expect(wrapper.findAll('[data-song-id]').map(n => n.attributes('data-song-id'))).toEqual(['c', 'a', 'b'])
    actions.dispose()

    pending = deferred<Response>()
    await wrapper.get('[data-song-id="b"] .song-open').trigger('click'); await flushPromises()
    await wrapper.get('[data-song-action="now"]').trigger('click'); await flushPromises()
    await router.push('/'); await flushPromises()
    expect(store.snapshot?.current_song?.song_id).toBe('a')
    phase = 3; pending.resolve(Response.json(fixture.receipts[2])); await flushPromises()
    expect(store.snapshot?.current_song?.song_id).toBe('b')
    expect(wrapper.get('[data-testid="actual-identity"]').text()).toContain('b')
    await router.push('/queue'); await flushPromises()
    const current = fixture.phases[3]!.snapshot.queue.items.find(i => i.position === 0)!
    expect(wrapper.find(`[data-queue-item="${current.queue_item_id}"]`).exists()).toBe(true)
    expect(wrapper.get('.app-background').element).toBe(background)
    expect(wrapper.find('.app-background img').exists()).toBe(false)
    expect(realtime.start).toHaveBeenCalledTimes(1)
    expect(realtime.stop).not.toHaveBeenCalled()
    expect(writes.map(r => r.path)).toEqual(['/api/favorites/c', '/api/playlists/p/songs', '/api/playback/songs/b/play'])
    expect(JSON.parse(String(writes[1]!.init?.body))).toEqual({ song_id: 'b' })
    expect(new Set(writes.map(r => new Headers(r.init?.headers).get('Idempotency-Key'))).size).toBe(3)
    // REST read cannot undo degraded write authority, even with a fresh DTO.
    store.markDisconnected(1); await realtime.refresh(); await flushPromises()
    expect(store.writable).toBe(false)
    await router.push('/library/favorites'); await flushPromises()
    await wrapper.get('[data-song-id="a"] .song-open').trigger('click'); await flushPromises()
    await wrapper.get('[data-favorite-toggle="a"]').trigger('click'); await flushPromises()
    expect(writes).toHaveLength(3)
  } finally { wrapper.unmount() }
  expect(realtime.stop).toHaveBeenCalledTimes(1)
})
