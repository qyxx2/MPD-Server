import { defineComponent, h, inject, type VNode } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, RouterView } from 'vue-router'
import { vi } from 'vitest'
import mpdInfo from '../fixtures/settings.json'
import AppShell from '../../src/components/layout/AppShell.vue'
import { createPlayerRouter } from '../../src/router'
import { createPlayerStore } from '../../src/stores/player'
import { createApiClient } from '../../src/services/api'
import { parseSnapshot } from '../../src/services/wire'
import { taskActionsKey, type TaskActions } from '../../src/runtime/taskActions'
import { playerState } from './player'
import wire from '../fixtures/library.json'
export { wire }
export async function libraryPage(path = '/library', override?: (path: string, init?: RequestInit) => Promise<Response> | undefined, extra?: VNode) {
  const requests: { path: string; init?: RequestInit }[] = []
  const store = createPlayerStore(); store.beginConnection(1); store.acceptInitial(playerState(), 1)
  const api = createApiClient({ origin: 'http://localhost', fetch: async (input, init) => {
    const url = new URL(String(input)); const path = url.pathname + url.search; requests.push({ path, init })
    const response = override?.(path, init); if (response) return await response
    if (path === '/api/system/mpd') return Response.json({ ...mpdInfo, errors: {} })
    if (path === '/api/system/mpd/connection') return Response.json({ active: { host: 'mpd', port: 6600 }, saved: null, restart_required: false })
    if (path === '/api/favorites/members') return Response.json({ song_ids: [] })
    if (path === '/api/state') return Response.json(playerState())
    if (path.endsWith('/songs') && path !== '/api/library/songs') return Response.json(wire.album_songs)
    if (path.startsWith('/api/library/songs/')) return Response.json({ ...playerState().current_song, song_id: decodeURIComponent(path.split('/').at(-1)!) })
    for (const kind of ['songs', 'albums', 'artists', 'genres', 'years', 'tags'] as const)
      if (url.pathname === `/api/library/${kind}`) return Response.json(wire[kind])
    throw new Error(`Unexpected ${init?.method} ${path}`)
  } })
  const realtime = { start: vi.fn(), stop: vi.fn(), refresh: vi.fn(async () => { store.acceptRefresh(await api.get('/api/state', parseSnapshot), store.marker.generation) }) }
  const router = createPlayerRouter(createMemoryHistory()); await router.push(path); await router.isReady()
  let tasks!: TaskActions
  const Probe = defineComponent({ setup() { tasks = inject(taskActionsKey)!; return () => null } })
  const wrapper = mount(defineComponent({ render: () => h(AppShell, { store, realtime, api }, { default: () => [h(Probe), h(RouterView), extra] }) }), { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router, store, api, tasks, requests, realtime }
}
