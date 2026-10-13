import { computed, inject, onUnmounted, watch, type ComputedRef } from 'vue'
import { libraryResourcesKey } from '../../stores/library'
import { playerKey } from '../player/playerFacts'
import { noticeKey } from '../../stores/notices'
export function useLibraryResource(path: ComputedRef<string>, label: ComputedRef<string>) {
  const resources = inject(libraryResourcesKey), player = inject(playerKey)!, notices = inject(noticeKey)!
  const entry = computed(() => resources?.entry(path.value))
  let serial = 0, active: string | null = null
  async function read() {
    const generation = ++serial, key = path.value, epoch = player.marker.epoch, id = `library-resource:${key}`
    if (active && active !== id) notices.remove(active)
    active = id
    if (!resources || !epoch) return
    if (!resources.entry(key).fresh) notices.set({ id, scope: 'library', message: `读取 ${label.value}`, busy: true })
    try {
      await resources.read(key)
      if (serial === generation && path.value === key && epoch === player.marker.epoch) notices.remove(id)
    } catch (error) {
      if (serial !== generation || path.value !== key || epoch !== player.marker.epoch) return
      notices.set({ id, scope: 'library', message: `${label.value} · ${error instanceof Error ? error.message : String(error)}`, read })
    }
  }
  watch(() => JSON.stringify([path.value, player.marker.epoch, player.marker.generation, player.marker.revisions.library, player.marker.trusted]), () => { void read() }, { immediate: true })
  onUnmounted(() => { ++serial; if (active) notices.remove(active) })
  return entry
}
