<script setup lang="ts">
import { computed, inject, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { playerKey } from '../components/player/playerFacts'
import { playerRuntimeKey } from '../components/player/playerActions'
import { playerSessionKey } from '../runtime/playerSession'
import { taskActionsKey } from '../runtime/taskActions'
import { playlistResourcesKey } from '../stores/playlists'
import { createPlaylistActions } from '../components/library/playlistActions'
import { usePlaylistResource } from '../components/library/playlistResources'
import { useLibraryResource } from '../components/library/libraryResources'
import FavoriteIcon from '../components/library/FavoriteIcon.vue'
import LibraryTabs from '../components/library/LibraryTabs.vue'
import SongRow from '../components/library/SongRow.vue'
const route = useRoute(), router = useRouter()
const id = computed(() => typeof route.params.id === 'string' ? route.params.id : '')
const base = computed(() => id.value ? `/api/playlists/${encodeURIComponent(id.value)}` : '')
const list = usePlaylistResource(computed(() => id.value ? '' : '/api/playlists'), computed(() => '歌单'))
const detail = usePlaylistResource(base, computed(() => '歌单详情'))
const playlist = computed(() => { const p = detail.value?.data; return p && 'playlist_id' in p ? p : null })
const members = usePlaylistResource(computed(() => base.value ? `${base.value}/songs` : ''), computed(() => playlist.value?.name ?? '歌单歌曲'))
const playlists = computed(() => { const data = list.value?.data; return data && 'items' in data ? data.items.filter(p => 'playlist_id' in p) : [] })
const songs = computed(() => { const data = members.value?.data; return data && 'items' in data ? data.items.filter(s => 'song_id' in s) : [] })
// Full membership, not playable subset; missing metadata cannot silently disappear.
const consistent = computed(() => Boolean(detail.value?.fresh && members.value?.fresh && playlist.value && JSON.stringify(playlist.value.song_ids) === JSON.stringify(songs.value.map(s => s.song_id))))
const player = inject(playerKey)!, runtime = inject(playerRuntimeKey), tasks = inject(taskActionsKey), resources = inject(playlistResourcesKey), session = inject(playerSessionKey)!
const actions = runtime && tasks && resources ? createPlaylistActions(player, runtime, tasks, resources, () => playlist.value, () => consistent.value, () => Boolean(session.actions?.locked)) : null
const ghost = ref<{ x: number; y: number; title: string } | null>(null)
const insertion = computed(() => { const d = actions?.draft.value; return d ? d.ids[d.ids.indexOf(d.id) + 1] ?? 'end' : null })
const edit = ref<'create' | 'rename' | null>(null), name = ref(''), adding = ref(false), deleting = ref(false)
const availableSongs = useLibraryResource(computed(() => '/api/library/songs'), computed(() => '选择歌曲'))
const picker = computed(() => { const data = availableSongs.value?.data; return data && 'items' in data && !('kind' in data) ? data.items : [] })
const ordered = computed(() => (playlist.value?.song_ids ?? []).map(id => ({ id, song: songs.value.find(s => s.song_id === id) })))
watch(id, () => { edit.value = null; name.value = ''; adding.value = false; deleting.value = false; actions?.cancel() })
onUnmounted(() => { actions?.dispose(); window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', finish); window.removeEventListener('pointercancel', cancel) })
async function submit() { const captured = id.value; if (!actions || !edit.value) return; const ok = await (edit.value === 'create' ? actions.create(name.value) : actions.rename(name.value)); if (ok && id.value === captured) { edit.value = null; name.value = '' } }
async function removePlaylist() { const captured = id.value; if (await actions?.delete() && id.value === captured) await router.push('/library/playlists') }
let pointer: number | null = null
function begin(event: PointerEvent, songId: string) {
  if (event.button !== 0 || !actions?.begin(songId)) return
  event.preventDefault(); pointer = event.pointerId; ghost.value = { x: event.clientX + 12, y: event.clientY - 24, title: songs.value.find(s => s.song_id === songId)?.title ?? songId }
}
function rowAt(event: PointerEvent) {
  const target = typeof document.elementFromPoint === 'function' ? document.elementFromPoint(event.clientX, event.clientY) : event.target as Element | null
  return target instanceof Element ? target.closest<HTMLElement>('[data-playlist-member]') : null
}
function move(event: PointerEvent) {
  if (pointer !== event.pointerId || !actions?.draft.value) return
  if (ghost.value) ghost.value = { ...ghost.value, x: event.clientX + 12, y: event.clientY - 24 }
  const row = rowAt(event); if (!row) return
  event.preventDefault(); const rect = row.getBoundingClientRect()
  actions.target(row.dataset.playlistMember!, event.clientY > rect.top + rect.height / 2)
  const scroll = row.closest<HTMLElement>('.shell-content'); if (scroll) { const r = scroll.getBoundingClientRect(); if (event.clientY < r.top + 40) scroll.scrollTop -= 12; else if (event.clientY > r.bottom - 40) scroll.scrollTop += 12 }
}
function finish(event: PointerEvent) { if (pointer !== event.pointerId) return; move(event); pointer = null; ghost.value = null; if (!rowAt(event)) actions?.cancel(); else void actions?.drop() }
function cancel() { pointer = null; ghost.value = null; actions?.cancel() }
watch(() => actions?.draft.value, value => { if (!value) ghost.value = null })
watch(edit, () => { void nextTick(() => { const input = document.getElementById('playlist-name'); input?.scrollIntoView?.({ block: 'nearest' }); input?.focus() }) })
onMounted(() => { window.addEventListener('pointermove', move, { passive: false }); window.addEventListener('pointerup', finish); window.addEventListener('pointercancel', cancel) })
function keyMove(songId: string, direction: number) {
  const ids = playlist.value?.song_ids ?? [], index = ids.indexOf(songId), target = ids[index + direction]
  if (target && actions?.begin(songId)) { actions.target(target, direction > 0); void actions.drop() }
}
</script>
<template>
  <section class="library-content playlist-content" aria-label="歌单">
    <LibraryTabs v-if="!id" /><RouterLink v-else class="library-back" to="/library/playlists">‹ 播放列表</RouterLink>
    <template v-if="!id">
      <button data-create-playlist :disabled="!actions || actions.locked.value" @click="edit = 'create'; name = ''">创建歌单</button>
      <ul class="collection-list"><li v-for="p in playlists" :key="p.playlist_id"><RouterLink :data-playlist-id="p.playlist_id" :to="`/library/playlists/${encodeURIComponent(p.playlist_id)}`"><span class="collection-name">{{ p.name }}</span><span class="collection-count">{{ p.song_ids.length }} 首{{ p.is_system ? ' · 系统' : '' }}</span></RouterLink></li></ul>
      <p v-if="list?.fresh && !playlists.length" class="library-empty">暂无歌单</p>
    </template>
    <template v-else-if="playlist">
      <h2 class="playlist-title">{{ playlist.name }}</h2>
      <div class="collection-actions">
        <button data-add-songs :disabled="!actions || actions.locked.value || !consistent" @click="adding = !adding">{{ adding ? '完成加歌' : '添加歌曲' }}</button>
        <button v-if="!playlist.is_system" data-rename :disabled="!actions || actions.locked.value || !consistent" @click="edit = 'rename'; name = playlist.name">重命名</button>
        <button v-if="!playlist.is_system" data-delete-playlist :disabled="!actions || actions.locked.value || !consistent" @click="deleting = true">删除歌单</button>
      </div>
      <div v-if="deleting" class="playlist-confirm" role="group" aria-label="确认删除歌单"><span>删除「{{ playlist.name }}」？</span><button data-confirm-delete :disabled="!actions || actions.locked.value || !consistent" @click="removePlaylist">确认删除</button><button @click="deleting = false">取消</button></div>
      <ul class="playlist-members">
        <li v-for="row in ordered" :key="row.id" :data-playlist-member="row.id" :class="{ 'playlist-dragging': actions?.draft.value?.id === row.id }" :data-drop="insertion === row.id" :data-drop-end="insertion === 'end' && row.id === ordered.at(-1)?.id">
          <button :data-reorder="row.id" class="playlist-handle" :aria-label="`拖动排序 ${row.song?.title ?? row.id}`" :disabled="!actions || actions.locked.value || !consistent" @pointerdown="begin($event, row.id)" @keydown.up.prevent="keyMove(row.id, -1)" @keydown.down.prevent="keyMove(row.id, 1)">≡</button>
          <ul class="song-list playlist-song"><SongRow v-if="row.song" :song="row.song" :fresh="consistent" /><li v-else class="song-row">{{ row.id }} <FavoriteIcon :song-id="row.id" /></li></ul>
          <button :data-remove-song="row.id" :aria-label="`移除 ${row.song?.title ?? row.id}`" :disabled="!actions || actions.locked.value || !consistent" @click="actions?.remove(row.id)">移除</button>
        </li>
      </ul>
      <p v-if="consistent && !ordered.length" class="library-empty">暂无歌曲</p>
      <section v-if="adding" aria-label="选择加入歌单的歌曲"><h3>选择歌曲</h3><ul class="playlist-picker"><li v-for="song in picker" :key="song.song_id || song.file_uri"><span>{{ song.title }} <FavoriteIcon :song-id="song.song_id" /><small v-if="song.availability_status !== 'AVAILABLE'"> · {{ song.availability_status }}</small></span><button :data-add-song="song.song_id" :disabled="!actions || actions.locked.value || !consistent || !availableSongs?.fresh || !song.song_id" @click="actions?.add(song.song_id!)">加入</button></li></ul></section>
    </template>
    <div v-if="ghost && actions?.draft.value" class="playlist-ghost" aria-hidden="true" :style="{ transform: `translate(${ghost.x}px,${ghost.y}px)` }">{{ ghost.title }}</div>
    <form v-if="edit" class="playlist-name-form" data-submit-name @submit.prevent="submit"><label :for="'playlist-name'">{{ edit === 'create' ? '歌单名称' : '新名称' }}</label><input id="playlist-name" v-model="name" data-playlist-name autocomplete="off" /><div><button type="submit" :disabled="!actions || actions.locked.value || !name.trim()">保存</button><button type="button" @click="edit = null; name = ''">取消</button></div></form>
  </section>
</template>
