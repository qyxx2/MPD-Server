import { computed } from 'vue'
import type { PlayerStore } from '../../stores/player'
import type { PlayerRuntime } from '../player/playerActions'
import type { TaskActions } from '../../runtime/taskActions'
import type { LibrarySource } from '../../types/resources'
import { parsePlaybackState, parseQueueItem, WireError } from '../../services/wire'
export interface SongTarget { song_id: string; queue_item_id?: string }
export function createSongActions(player: PlayerStore, runtime: PlayerRuntime, tasks: TaskActions, playbackLocked: () => boolean) {
  const locked = computed(() => !player.writable || playbackLocked() || tasks.entries.value.some(record => record.state === 'pending' || record.state === 'unknown' || record.busy))
  function song(target: SongTarget, operation: 'now' | 'next' | 'add', title: string, available: boolean) {
    if (locked.value || !available || !target.song_id) return Promise.resolve()
    const path = operation === 'now' && target.queue_item_id
      ? `/api/playback/queue/items/${encodeURIComponent(target.queue_item_id)}/play`
      : `/api/playback/songs/${encodeURIComponent(target.song_id)}/${{ now: 'play', next: 'play-next', add: 'queue' }[operation]}`
    return tasks.run(runtime.api.createIntent('POST', path, undefined), value => {
      const item = parseQueueItem(value)
      if (item.song_id !== target.song_id || (operation === 'now' && item.position !== 0) || (operation === 'now' && target.queue_item_id && item.queue_item_id !== target.queue_item_id)) throw new WireError('Playback receipt identity mismatch')
      return item
    }, async () => {}, `${{ now: '立即播放', next: '下一首播放', add: '加入队尾' }[operation]} ${title}`)
  }
  return { locked,
    playNow: (target: SongTarget, title: string, available = true) => song(target, 'now', title, available),
    playNext: (song_id: string, title: string, available = true) => song({ song_id }, 'next', title, available),
    add: (song_id: string, title: string, available = true) => song({ song_id }, 'add', title, available),
    playCollection(source: LibrarySource, randomize: boolean, playableCount: number, title: string) {
      if (locked.value || playableCount <= 0) return Promise.resolve()
      return tasks.run(runtime.api.createIntent('POST', '/api/playback/collections/play', { ...source, randomize }), value => value === null ? null : parsePlaybackState(value), async () => {}, `${randomize ? '随机播放' : '播放全部'} ${title}`)
    },
  }
}
export type SongActions = ReturnType<typeof createSongActions>
