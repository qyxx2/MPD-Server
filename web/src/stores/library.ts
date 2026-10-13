import { watch, type InjectionKey } from 'vue'
import type { Song } from '../types/api'
import type { createApiClient } from '../services/api'
import type { PlayerStore } from './player'
import { createResourceCache } from './resourceCache'
import { parseLibraryResource } from '../services/resourceWire'

export function createLibraryStore<T>(options: { api: ReturnType<typeof createApiClient>; player: PlayerStore; decode: (value: unknown, path: string) => T }) {
  const cache = createResourceCache({ load: (path: string) => {
    if (!path.startsWith('/api/library/')) throw new TypeError('Library resource path required')
    return options.api.get(path, value => options.decode(value, path))
  }, dependencies: ['library'] })
  const stop = watch(() => options.player.marker, marker => cache.invalidate(marker), { immediate: true, flush: 'sync' })
  return { ...cache, stop }
}
export type SongLibraryStore = ReturnType<typeof createLibraryStore<Song>>
export const songLibraryKey: InjectionKey<SongLibraryStore> = Symbol('song-library')

// One cache for all Library paths. Queue keeps its typed Song projection;
// category/list consumers share the same epoch/revision owner and lifetime.
export function createAppLibraryStore(options: { api: ReturnType<typeof createApiClient>; player: PlayerStore }) {
  const resources = createLibraryStore({ ...options, decode: parseLibraryResource })
  const songs: SongLibraryStore = {
    ...resources,
    async read(path) {
      const resource = await resources.read(path)
      if (!('song_id' in resource)) throw new TypeError('Song resource required')
      return resource
    },
    entry(path) {
      const entry = resources.entry(path)
      return {
        get data() { const data = entry.data; return data && 'song_id' in data ? data : null },
        get fresh() { return entry.fresh }, get loading() { return entry.loading }, get error() { return entry.error },
      }
    },
  }
  return { resources, songs }
}
export type LibraryResources = ReturnType<typeof createAppLibraryStore>['resources']
export const libraryResourcesKey: InjectionKey<LibraryResources> = Symbol('library-resources')
