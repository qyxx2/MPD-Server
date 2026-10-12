import { computed, inject, onUnmounted, watch, type ComputedRef } from 'vue'
import { playlistResourcesKey } from '../../stores/playlists'
import { playerKey } from '../player/playerFacts'
import { noticeKey } from '../../stores/notices'
export function usePlaylistResource(path: ComputedRef<string>, label: ComputedRef<string>) {
  const resources = inject(playlistResourcesKey)!, player = inject(playerKey)!, notices = inject(noticeKey)!
  const entry = computed(() => path.value ? resources?.entry(path.value) : undefined)
  let serial = 0, active: string | null = null
  async function read() {
    const generation = ++serial, key = path.value, epoch = player.marker.epoch, id = `playlist-resource:${key}`
    if (active && active !== id) notices.remove(active)
    active = key ? id : null
    if (!key || !resources || !epoch) return
    if (!resources.entry(key).fresh) notices.set({ id, scope: 'playlist', message: `读取 ${label.value}`, busy: true })
    try { await resources.read(key); if (serial === generation && path.value === key && epoch === player.marker.epoch) notices.remove(id) }
    catch (error) {
      if (serial !== generation || path.value !== key || epoch !== player.marker.epoch) return
      notices.set({ id, scope: 'playlist', message: `${label.value} · ${error instanceof Error ? error.message : String(error)}`, read })
    }
  }
  watch(() => JSON.stringify([path.value, player.marker.epoch, player.marker.generation, player.marker.revisions.library, player.marker.revisions.playlist, player.marker.trusted]), () => { void read() }, { immediate: true })
  onUnmounted(() => { ++serial; if (active) notices.remove(active) })
  return entry
}
