import { computed, ref, watch } from 'vue'
import type { PlayerStore } from '../../stores/player'
import type { PlayerRuntime } from '../player/playerActions'
import type { TaskActions } from '../../runtime/taskActions'
import { parseQueueItem, parseQueueList } from '../../services/wire'
import { parseNoContent, parsePlaylist, parsePlaylistList } from '../../services/resourceWire'
export function createQueueActions(player: PlayerStore, runtime: PlayerRuntime, tasks: TaskActions, playbackLocked: () => boolean) {
  const saveKey = ref<string | null>(null)
  const draft = ref<{ id: string; before: string | null; baseline: string } | null>(null)
  const locked = computed(() => !player.writable || playbackLocked() || tasks.entries.value.some(record => record.state === 'pending' || record.state === 'unknown' || record.busy))
  const baseline = () => JSON.stringify([player.marker.epoch, player.marker.generation, player.snapshot?.queue.revision,
    player.snapshot?.queue.items.map(item => [item.queue_item_id, item.position, item.source])])
  const stop = watch(() => [baseline(), locked.value], () => { if (draft.value && (draft.value.baseline !== baseline() || locked.value)) draft.value = null }, { flush: 'sync' })
  const currentItem = (id: string) => player.snapshot?.queue.items.find(item => item.queue_item_id === id)
  return {
    draft, locked, saveKey,
    play(id: string, title: string) {
      if (locked.value || draft.value || !currentItem(id)) return Promise.resolve()
      return tasks.run(runtime.api.createIntent('POST', `/api/playback/queue/items/${encodeURIComponent(id)}/play`, undefined), parseQueueItem, async () => {}, `播放 ${title} · 条目 ${id}`)
    },
    move(id: string, operation: 'next' | 'add', title: string) {
      const item = currentItem(id)
      if (locked.value || draft.value || !item || item.position <= 0) return Promise.resolve()
      const pending = [...(player.snapshot?.queue.items ?? [])].filter(i => i.position > 0).sort((a, b) => a.position - b.position)
      if ((operation === 'next' ? pending[0] : pending.at(-1))?.queue_item_id === id) return Promise.resolve()
      const before = operation === 'next' ? pending[0]!.queue_item_id : null
      return tasks.run(runtime.api.createIntent('PUT', `/api/playback/queue/items/${encodeURIComponent(id)}`, { before_queue_item_id: before }), parseQueueList, async () => {}, `${operation === 'next' ? '移为下一首' : '移到队尾'} ${title} · 条目 ${id}`)
    },
    remove(id: string, title: string) {
      if (locked.value || draft.value || !currentItem(id)) return Promise.resolve()
      return tasks.run(runtime.api.createIntent('DELETE', `/api/playback/queue/items/${encodeURIComponent(id)}`, undefined), parseNoContent, async () => {}, `删除 ${title} · 条目 ${id}`)
    },
    clear() {
      if (locked.value || draft.value) return Promise.resolve()
      return tasks.run(runtime.api.createIntent('DELETE', '/api/playback/queue', undefined), parseNoContent, async () => {}, '清空待播')
    },
    async save(name: string) {
      if (locked.value || draft.value || !name.trim()) return false
      const intent = runtime.api.createIntent('POST', '/api/playback/queue/save-as-playlist', { name })
      saveKey.value = intent.key
      await tasks.run(intent, parsePlaylist, async () => { await runtime.api.get('/api/playlists', parsePlaylistList) }, `保存 Playlist · ${name}`)
      return tasks.entries.value.find(record => record.intent.key === intent.key)?.state === 'confirmed'
    },
    begin(id: string) {
      if (locked.value || (currentItem(id)?.position ?? 0) <= 0) return false
      draft.value = { id, before: null, baseline: baseline() }; return true
    },
    target(before: string | null) {
      if (!draft.value || before === draft.value.id || (before !== null && (currentItem(before)?.position ?? 0) <= 0)) return false
      draft.value = { ...draft.value, before }; return true
    },
    cancel() { draft.value = null },
    drop(title: string) {
      const captured = draft.value; draft.value = null
      if (!captured || locked.value || captured.baseline !== baseline()) return Promise.resolve()
      const pending = [...(player.snapshot?.queue.items ?? [])].filter(item => item.position > 0).sort((a, b) => a.position - b.position)
      const index = pending.findIndex(item => item.queue_item_id === captured.id)
      if ((pending[index + 1]?.queue_item_id ?? null) === captured.before) return Promise.resolve()
      return tasks.run(runtime.api.createIntent('PUT', `/api/playback/queue/items/${encodeURIComponent(captured.id)}`, { before_queue_item_id: captured.before }), parseQueueList, async () => {}, `排序 ${title} · 条目 ${captured.id}`)
    },
    dispose() { draft.value = null; stop() },
  }
}
