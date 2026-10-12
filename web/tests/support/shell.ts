import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h, inject } from 'vue'
import { createMemoryHistory, RouterView } from 'vue-router'
import { vi } from 'vitest'
import mpdInfo from '../fixtures/settings.json'
import { createPlayerRouter } from '../../src/router'
import { taskActionsKey, type TaskActions } from '../../src/runtime/taskActions'
import AppShell from '../../src/components/layout/AppShell.vue'
import { createApiClient } from '../../src/services/api'
import { createPlayerStore } from '../../src/stores/player'
import { parseSnapshot } from '../../src/services/wire'
import { playerState } from './player'
import { transport } from './transport'
export async function shellPage(...responses: Parameters<typeof transport>) {
  return createShellPage(false, ...responses)
}
// Existing action tests keep their mutation/state response sequence while the
// newly implemented Queue performs real, independently decoded Song GETs.
export async function shellPageWithSongReads(...responses: Parameters<typeof transport>) {
  return createShellPage(true, ...responses)
}
async function createShellPage(songReads: boolean, ...responses: Parameters<typeof transport>) {
  const router = createPlayerRouter(createMemoryHistory())
  await router.push('/'); await router.isReady()
  const store = createPlayerStore()
  store.beginConnection(1); store.acceptInitial(playerState(), 1)
  const network = transport(...responses)
  const songRequests: string[] = []
  const libraryRequests: string[] = []
  const fetcher: typeof fetch = async (input, init) => {
    if (new URL(String(input)).pathname === '/api/system/mpd') return Response.json({ ...mpdInfo, errors: {} })
    if (new URL(String(input)).pathname === '/api/system/mpd/connection') return Response.json({ active: { host: 'mpd', port: 6600 }, saved: null, restart_required: false })
    if (new URL(String(input)).pathname === '/api/favorites/members') return Response.json({ song_ids: [] })
    // B05 Library routes now read real resources. Keep these reads separate
    // from existing mutation/replay response sequences, just like Queue Song GETs.
    if (init?.method === 'GET' && /^\/api\/library\/(songs$|(?:albums|artists|genres|years|tags)(?:$|\/[^/]+\/songs$))/.test(new URL(String(input)).pathname)) {
      libraryRequests.push(String(input))
      return Response.json({ items: [], count: 0 })
    }
    if (songReads && init?.method === 'GET' && new URL(String(input)).pathname.startsWith('/api/library/songs/')) {
      songRequests.push(String(input))
      return Response.json(playerState().current_song)
    }
    return network.fetch(input, init)
  }
  const api = createApiClient({ origin: 'http://localhost', fetch: fetcher })
  const realtime = { start: vi.fn(), stop: vi.fn(), refresh: vi.fn(async () => {
    store.acceptRefresh(await api.get('/api/state', parseSnapshot), store.marker.generation)
  }) }
  let tasks!: TaskActions
  const Probe = defineComponent({ setup() { tasks = inject(taskActionsKey)!; return () => null } })
  const wrapper = mount(defineComponent({ render: () => h(AppShell, { store, realtime, api }, { default: () => [h(Probe), h(RouterView)] }) }), { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, store, api, network, router, realtime, tasks, songRequests, libraryRequests }
}
