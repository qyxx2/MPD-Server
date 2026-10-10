import { watch } from 'vue'
import type { createApiClient } from '../services/api'
import type { PlayerStore } from './player'
import { createResourceCache } from './resourceCache'

export function createLibraryStore<T>(options: { api: ReturnType<typeof createApiClient>; player: PlayerStore; decode: (value: unknown) => T }) {
  const cache = createResourceCache({ load: (path: string) => {
    if (!path.startsWith('/api/library/')) throw new TypeError('Library resource path required')
    return options.api.get(path, options.decode)
  }, dependencies: ['library'] })
  const stop = watch(() => options.player.marker, marker => cache.invalidate(marker), { immediate: true, flush: 'sync' })
  return { ...cache, stop }
}
