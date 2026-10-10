import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import fixture from '../fixtures/wire.json'
import { createApiClient } from '../../src/services/api'
import { createPlayerStore } from '../../src/stores/player'
import { parseSnapshot } from '../../src/services/wire'
import AppShell from '../../src/components/layout/AppShell.vue'
import PlayerView from '../../src/views/PlayerView.vue'
import { transport } from './transport'
export function playerState() {
  const value = parseSnapshot(structuredClone(fixture.snapshot))
  value.playback_observation.duration_seconds = 180
  return value
}
export function playerPage(...responses: Parameters<typeof transport>) {
  const network = transport(...responses)
  const api = createApiClient({ origin: 'http://localhost', fetch: network.fetch })
  const store = createPlayerStore()
  store.beginConnection(1); store.acceptInitial(parseSnapshot(playerState()), 1)
  const realtime = { start() {}, stop() {}, async refresh() { store.acceptRefresh(await api.get('/api/state', parseSnapshot), 1) } }
  const wrapper = mount(defineComponent({ render: () => h(AppShell, { store, realtime, api }, { default: () => h(PlayerView) }) }))
  return { wrapper, store, network, realtime, api }
}
export { fixture, flushPromises }
