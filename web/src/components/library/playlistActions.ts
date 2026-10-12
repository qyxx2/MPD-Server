import { computed, ref, watch } from 'vue'
import type { DeepReadonly } from 'vue'
import type { JsonValue } from '../../types/api'
import type { Playlist } from '../../types/resources'
import type { PlayerStore } from '../../stores/player'
import type { PlaylistResources } from '../../stores/playlists'
import type { PlayerRuntime } from '../player/playerActions'
import type { TaskActions } from '../../runtime/taskActions'
import { parseNoContent, parsePlaylist } from '../../services/resourceWire'
export function createPlaylistActions(player: PlayerStore, runtime: PlayerRuntime, tasks: TaskActions, resources: PlaylistResources, current: () => DeepReadonly<Playlist> | null, fresh: () => boolean, playbackLocked: () => boolean) {
  const locked = computed(() => !player.writable || playbackLocked() || tasks.entries.value.some(r => r.state === 'pending' || r.state === 'unknown' || r.busy))
  const draft = ref<{ ids: string[]; baseline: string; id: string } | null>(null)
  const baseline = () => JSON.stringify([player.marker.epoch, player.marker.generation, player.marker.trusted, player.marker.revisions.library, player.marker.revisions.playlist, current()?.playlist_id, current()?.song_ids])
  const stop = watch(() => [baseline(), locked.value, fresh()], () => { if (draft.value && (draft.value.baseline !== baseline() || locked.value || !fresh())) draft.value = null }, { flush: 'sync' })
  const path = (id: string) => `/api/playlists/${encodeURIComponent(id)}`
  async function run(method: 'POST' | 'PATCH' | 'DELETE' | 'PUT', url: string, payload: JsonValue | undefined, label: string, id?: string, deleted = false) {
    if (locked.value || (id && (!fresh() || current()?.playlist_id !== id))) return false
    const intent = runtime.api.createIntent(method, url, payload)
    await tasks.run(intent, method === 'DELETE' ? parseNoContent : parsePlaylist, async () => {
      await resources.read('/api/playlists', { force: true })
      if (id && !deleted) await Promise.all([resources.read(path(id), { force: true }), resources.read(`${path(id)}/songs`, { force: true })])
    }, label)
    return tasks.entries.value.find(r => r.intent.key === intent.key)?.state === 'confirmed'
  }
  return { locked, draft,
    create(name: string) { return name.trim() ? run('POST', '/api/playlists', { name }, `创建歌单 ${name}`) : Promise.resolve(false) },
    rename(name: string) { const p = current(); return p && !p.is_system && name.trim() ? run('PATCH', path(p.playlist_id), { name }, `重命名 ${p.name}`, p.playlist_id) : Promise.resolve(false) },
    delete() { const p = current(); return p && !p.is_system ? run('DELETE', path(p.playlist_id), undefined, `删除歌单 ${p.name}`, p.playlist_id, true) : Promise.resolve(false) },
    add(songId: string) { const p = current(); return p && songId ? run('POST', `${path(p.playlist_id)}/songs`, { song_id: songId }, `加入 ${p.name}`, p.playlist_id) : Promise.resolve(false) },
    remove(songId: string) { const p = current(); return p?.song_ids.includes(songId) ? run('DELETE', `${path(p.playlist_id)}/songs/${encodeURIComponent(songId)}`, undefined, `从 ${p.name} 移除歌曲`, p.playlist_id) : Promise.resolve(false) },
    begin(id: string) { const p = current(); if (locked.value || !fresh() || !p?.song_ids.includes(id)) return false; draft.value = { id, ids: [...p.song_ids], baseline: baseline() }; return true },
    target(id: string, after: boolean) {
      const d = draft.value; if (!d || !d.ids.includes(id)) return
      if (id === d.id) { draft.value = { ...d, ids: [...(current()?.song_ids ?? [])] }; return }
      const ids = [...(current()?.song_ids ?? [])].filter(i => i !== d.id); ids.splice(ids.indexOf(id) + Number(after), 0, d.id); draft.value = { ...d, ids }
    },
    cancel() { draft.value = null },
    drop() {
      const d = draft.value, p = current(); draft.value = null
      if (!d || !p || d.baseline !== baseline() || JSON.stringify(d.ids) === JSON.stringify(p.song_ids)) return Promise.resolve(false)
      return run('PUT', `${path(p.playlist_id)}/songs/order`, { ordered_song_ids: d.ids }, `调整 ${p.name} 顺序 · 冲突后请重新拖动`, p.playlist_id)
    },
    dispose() { draft.value = null; stop() },
  }
}
