import { computed, watch, type InjectionKey } from 'vue'
import type { PlayerStore } from './player'
import type { PlaylistResources } from './playlists'
import type { PlayerRuntime } from '../components/player/playerActions'
import type { TaskActions } from '../runtime/taskActions'
import type { createNoticeStore } from './notices'
import { parseCollection, parseNoContent } from '../services/resourceWire'
const path = '/api/favorites/members'
export function createFavoritesStore(player: PlayerStore, resources: PlaylistResources, runtime: PlayerRuntime, tasks: TaskActions, notices: ReturnType<typeof createNoticeStore>) {
  const entry = resources.entry(path)
  const members = computed(() => entry.data && 'song_ids' in entry.data && !('playlist_id' in entry.data) ? entry.data.song_ids : [])
  let alive = true, serial = 0
  async function read(force = false) {
    const current = ++serial, epoch = player.marker.epoch
    if (!epoch) return
    const id = 'favorites-resource'
    if (!entry.fresh) notices.set({ id, scope: 'favorites', message: '读取收藏', busy: true })
    try { await resources.read(path, { force }); if (alive && serial === current && epoch === player.marker.epoch) notices.remove(id) }
    catch (error) {
      if (alive && serial === current && epoch === player.marker.epoch) notices.set({ id, scope: 'favorites', message: `收藏 · ${String(error)}`, read: () => read(true) })
      throw error
    }
  }
  const stop = watch(() => JSON.stringify([player.marker.epoch, player.marker.generation, player.marker.trusted, player.marker.revisions.library, player.marker.revisions.playlist]), () => { void read().catch(() => {}) }, { immediate: true })
  function locked(songId: string) {
    return !songId || !player.writable || !entry.fresh || tasks.entries.value.some(r => r.state === 'pending' || r.state === 'unknown' || r.busy || (r.readFailed && r.intent.path === `/api/favorites/${encodeURIComponent(songId)}`))
  }
  return { entry, members, isFavorite: (id: string) => members.value.includes(id), locked, read,
    setFavorite(id: string, enabled: boolean) {
      if (locked(id) || enabled === members.value.includes(id)) return Promise.resolve()
      const intent = runtime.api.createIntent(enabled ? 'PUT' : 'DELETE', `/api/favorites/${encodeURIComponent(id)}`, undefined)
      return tasks.run(intent, enabled ? value => { const c = parseCollection(value); if (c.source_type !== 'FAVORITES') throw new TypeError('Favorites receipt required'); return c } : parseNoContent,
        async () => { await read(true) }, enabled ? '收藏歌曲' : '取消收藏歌曲')
    },
    stop() { alive = false; ++serial; stop(); notices.remove('favorites-resource') },
  }
}
export type FavoritesStore = ReturnType<typeof createFavoritesStore>
export const favoritesKey: InjectionKey<FavoritesStore> = Symbol('favorites')
