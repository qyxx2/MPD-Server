import { watch, type InjectionKey } from 'vue'
import type { createApiClient } from '../services/api'
import type { PlayerStore } from './player'
import { createResourceCache } from './resourceCache'

export function createPlaylistsStore<T>(options: { api: ReturnType<typeof createApiClient>; player: PlayerStore; decode: (value: unknown, path: string) => T }) {
  const cache = createResourceCache({ load: (path: string) => {
    if (!(path === '/api/playlists' || path.startsWith('/api/playlists/') || path === '/api/favorites' || path === '/api/favorites/members')) throw new TypeError('Playlist resource path required')
    return options.api.get(path, value => options.decode(value, path))
  }, dependencies: ['library', 'playlist'] })
  const stop = watch(() => options.player.marker, marker => cache.invalidate(marker), { immediate: true, flush: 'sync' })
  return { ...cache, stop }
}

export type PlaylistResources = ReturnType<typeof createPlaylistsStore<import('../types/resources').PlaylistResource>>
export const playlistResourcesKey: InjectionKey<PlaylistResources> = Symbol('playlist-resources')
