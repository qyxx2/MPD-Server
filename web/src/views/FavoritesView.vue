<script setup lang="ts">
import { computed, inject, watch, onUnmounted, ref } from 'vue'
import { favoritesKey } from '../stores/favorites'
import { songLibraryKey } from '../stores/library'
import { playerKey } from '../components/player/playerFacts'
import { playerRuntimeKey } from '../components/player/playerActions'
import { playerSessionKey } from '../runtime/playerSession'
import { taskActionsKey } from '../runtime/taskActions'
import { noticeKey } from '../stores/notices'
import { createSongActions } from '../components/library/songActions'
import LibraryTabs from '../components/library/LibraryTabs.vue'
import SongRow from '../components/library/SongRow.vue'
import FavoriteUnavailableMenu from '../components/library/FavoriteUnavailableMenu.vue'
import FavoriteIcon from '../components/library/FavoriteIcon.vue'
const favorites = inject(favoritesKey)!, library = inject(songLibraryKey)!, player = inject(playerKey)!
const ids = computed(() => favorites?.members.value ?? [])
const notices = inject(noticeKey)!, runtime = inject(playerRuntimeKey), tasks = inject(taskActionsKey), session = inject(playerSessionKey)!
const actions = runtime && tasks ? createSongActions(player, runtime, tasks, () => Boolean(session.actions?.locked)) : null
const menu = ref<string | null>(null)
let opener: HTMLElement | null = null
function openMenu(id: string, event: Event) { opener = event.currentTarget as HTMLElement; menu.value = id }
function closeMenu() { menu.value = null; opener?.focus() }
let alive = true, generation = 0
const noticeIds = new Set<string>()
async function metadata(id: string, current = generation) {
  const path = `/api/library/songs/${encodeURIComponent(id)}`, noticeId = `favorite-song:${id}`, epoch = player.marker.epoch
  try { await library.read(path); if (alive && generation === current && epoch === player.marker.epoch) { notices.remove(noticeId); noticeIds.delete(noticeId) } }
  catch (error) {
    if (!alive || generation !== current || epoch !== player.marker.epoch) return
    noticeIds.add(noticeId); notices.set({ id: noticeId, scope: 'favorites', message: `${id} · ${String(error)}`, read: () => metadata(id) })
  }
}
watch(() => [ids.value, player.marker], () => {
  ++generation
  for (const id of noticeIds) { notices.remove(id); noticeIds.delete(id) }
  for (const id of ids.value) void metadata(id)
}, { immediate: true })
onUnmounted(() => { alive = false; ++generation; for (const id of noticeIds) notices.remove(id) })
const rows = computed(() => ids.value.map(id => ({ id, entry: library.entry(`/api/library/songs/${encodeURIComponent(id)}`) })))
const playable = computed(() => rows.value.filter(row => row.entry.fresh && row.entry.data?.availability_status === 'AVAILABLE').length)
function play(randomize: boolean) { if (favorites?.entry.fresh) void actions?.playCollection({ source_type: 'FAVORITES' }, randomize, playable.value, '收藏') }

</script>
<template>
  <section class="library-content" aria-label="收藏"><LibraryTabs />
    <div class="collection-actions"><button data-play-all :disabled="!actions || actions.locked.value || !favorites?.entry.fresh || !playable" @click="play(false)">播放全部</button><button data-shuffle-all :disabled="!actions || actions.locked.value || !favorites?.entry.fresh || !playable" @click="play(true)">随机播放</button></div>
    <ul class="song-list"><template v-for="row in rows" :key="row.id"><SongRow v-if="row.entry.data" :song="row.entry.data" :fresh="row.entry.fresh" /><li v-else class="song-row"><button @click="openMenu(row.id, $event)">{{ row.id }}</button><FavoriteIcon :song-id="row.id" /><FavoriteUnavailableMenu v-if="menu === row.id" :song-id="row.id" @close="closeMenu" /></li></template></ul>
    <p v-if="favorites?.entry.fresh && !ids.length" class="library-empty">暂无收藏</p>
  </section>
</template>
