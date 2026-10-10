import { watch } from 'vue'
import type { createApiClient } from '../services/api'
import type { PlayerStore } from './player'
import { createResourceCache } from './resourceCache'

export function createPlaylistsStore<T>(options: { api: ReturnType<typeof createApiClient>; player: PlayerStore; decode: (value: unknown) => T }) {
  const cache = createResourceCache({ load: (path: string) => {
    if (!(path === '/api/playlists' || path.startsWith('/api/playlists/') || path === '/api/favorites')) throw new TypeError('Playlist resource path required')
    return options.api.get(path, options.decode)
  }, dependencies: ['library', 'playlist'] })
  const stop = watch(() => options.player.marker, marker => cache.invalidate(marker), { immediate: true, flush: 'sync' })
  return { ...cache, stop }
}
