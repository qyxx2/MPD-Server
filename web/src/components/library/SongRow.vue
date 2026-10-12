<script setup lang="ts">
import { computed, inject, ref, watch, onUnmounted, type DeepReadonly } from 'vue'
import type { Song } from '../../types/api'
import { playerKey } from '../player/playerFacts'
import { playerRuntimeKey } from '../player/playerActions'
import { playerSessionKey } from '../../runtime/playerSession'
import { taskActionsKey } from '../../runtime/taskActions'
import { createSongActions } from './songActions'
import { noticeKey } from '../../stores/notices'
import FavoriteIcon from './FavoriteIcon.vue'
import SongActionMenu from './SongActionMenu.vue'
const props = defineProps<{ song: DeepReadonly<Song>; fresh?: boolean }>()
const player = inject(playerKey)!, runtime = inject(playerRuntimeKey), tasks = inject(taskActionsKey), session = inject(playerSessionKey)!
const actions = runtime && tasks ? createSongActions(player, runtime, tasks, () => Boolean(session.actions?.locked)) : null
const notices = inject(noticeKey)!
let noticeId: string | null = null
watch(() => [props.song.song_id, props.song.availability_status, props.song.title], () => {
  if (noticeId) notices.remove(noticeId)
  noticeId = props.song.song_id && props.song.availability_status !== 'AVAILABLE' ? `library-song:${props.song.song_id}` : null
  if (noticeId) notices.set({ id: noticeId, scope: 'library', message: `${props.song.title} · ${props.song.availability_status} · 文件不可播放` })
}, { immediate: true })
onUnmounted(() => { if (noticeId) notices.remove(noticeId) })
const open = ref(false), opener = ref<HTMLButtonElement | null>(null)
const available = computed(() => Boolean(props.song.song_id) && props.song.availability_status === 'AVAILABLE')
const disabled = computed(() => !actions || actions.locked.value || !available.value || props.fresh === false)
function close() { if (!open.value) return; open.value = false; opener.value?.focus({ preventScroll: true }) }
function operate(operation: 'now' | 'next' | 'add') {
  if (disabled.value || !props.song.song_id) return
  const id = props.song.song_id, title = props.song.title; close()
  if (operation === 'now') void actions?.playNow({ song_id: id }, title, available.value)
  else if (operation === 'next') void actions?.playNext(id, title, available.value)
  else void actions?.add(id, title, available.value)
}
watch([() => props.song.song_id, () => player.marker.epoch], close)
</script>
<template>
  <li class="song-row" :data-song-id="song.song_id">
    <button ref="opener" class="song-open" :aria-label="`${song.title} · ${song.artists.join(' / ') || '—'}`" @click="open = true"><span class="song-title">{{ song.title || '—' }}</span><span class="song-artist">{{ song.artists.join(' / ') || '—' }}</span></button>
    <span v-if="!available" class="song-availability">{{ song.availability_status }}</span>
    <span class="song-favorite-slot" @click.stop><slot name="favorite"><FavoriteIcon :song-id="song.song_id" /></slot></span>
    <SongActionMenu v-if="open" :song="song" :disabled="disabled" @close="close" @action="operate" />
  </li>
</template>
