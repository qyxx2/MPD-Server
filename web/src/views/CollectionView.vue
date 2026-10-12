<script setup lang="ts">
import { computed, inject, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { playerKey } from '../components/player/playerFacts'
import { playerRuntimeKey } from '../components/player/playerActions'
import { playerSessionKey } from '../runtime/playerSession'
import { taskActionsKey } from '../runtime/taskActions'
import { createSongActions } from '../components/library/songActions'
import { useLibraryResource } from '../components/library/libraryResources'
import SongRow from '../components/library/SongRow.vue'
import LibraryIcon from '../components/library/LibraryIcon.vue'
import { noticeKey } from '../stores/notices'
import type { CategoryKind, LibrarySource } from '../types/resources'
const route = useRoute()
const searchQuery = computed(() => typeof route.query.search === 'string' ? route.query.search : null)
const back = computed(() => searchQuery.value !== null
  ? { path: '/library/search', query: { q: searchQuery.value } }
  : { path: '/library', query: { kind: kind.value } })
const kind = computed(() => route.params.kind as CategoryKind)
const id = computed(() => String(route.params.id))
const names = { albums: '专辑', artists: '艺术家', genres: '风格', years: '年代', tags: '标签' }
const label = computed(() => names[kind.value])
const summaries = useLibraryResource(computed(() => `/api/library/${kind.value}`), label)
const summary = computed(() => { const data = summaries.value?.data; return data && 'kind' in data ? data.items.find(item => item.id === id.value) : undefined })
const title = computed(() => summary.value?.name ?? id.value)
const entry = useLibraryResource(computed(() => `/api/library/${kind.value}/${encodeURIComponent(id.value)}/songs`), title)
const songs = computed(() => { const data = entry.value?.data; return data && !('kind' in data) && 'items' in data ? data.items : [] })
const player = inject(playerKey)!, runtime = inject(playerRuntimeKey), tasks = inject(taskActionsKey), session = inject(playerSessionKey)!
const notices = inject(noticeKey)!
const artists = computed(() => summary.value?.album_artists.length ? summary.value.album_artists : songs.value[0]?.album_artists ?? [])
const year = computed(() => summary.value?.year ?? songs.value[0]?.year)
const coverSong = computed(() => songs.value.find(song => song.song_id && song.artwork && (!summary.value?.artwork || song.artwork.artwork_id === summary.value.artwork.artwork_id)))
const coverUrl = computed(() => coverSong.value ? `/api/library/songs/${encodeURIComponent(coverSong.value.song_id!)}/artwork?v=${encodeURIComponent(JSON.stringify([player.marker.epoch, player.marker.revisions.library, coverSong.value.artwork]))}` : null)
const coverFailed = ref(false)
const coverNotice = 'library-album-cover'
watch(() => JSON.stringify([kind.value, id.value, coverUrl.value]), () => { coverFailed.value = false; notices.remove(coverNotice) })
function coverError(event: Event) {
  if ((event.target as HTMLImageElement).getAttribute('src') !== coverUrl.value) return
  coverFailed.value = true
  notices.set({ id: coverNotice, scope: 'library', message: `${title.value} · 封面读取失败`, read: async () => { coverFailed.value = false; notices.remove(coverNotice) } })
}
onUnmounted(() => notices.remove(coverNotice))
const actions = runtime && tasks ? createSongActions(player, runtime, tasks, () => Boolean(session.actions?.locked)) : null
const source = computed<LibrarySource>(() => ({ source_type: ({ albums: 'ALBUM', artists: 'ARTIST', genres: 'GENRE', years: 'YEAR', tags: 'TAG' } as const)[kind.value], source_id: id.value }))
function play(randomize: boolean) { if (entry.value?.fresh) void actions?.playCollection(source.value, randomize, songs.value.length, title.value) }
</script>
<template>
  <section class="library-content" :aria-label="title">
    <RouterLink class="library-back" :to="back" :aria-label="searchQuery !== null ? '返回搜索' : '返回分类'"><LibraryIcon name="back" /><LibraryIcon v-if="searchQuery === null" :name="kind" /><span>{{ searchQuery !== null ? '搜索' : label }}</span></RouterLink>
    <div v-if="kind === 'albums'" class="album-summary">
      <div class="album-cover"><img v-if="coverUrl && !coverFailed" :key="coverUrl" :src="coverUrl" :alt="`${title} 封面`" @error="coverError" /><div v-else class="album-cover-placeholder" role="img" aria-label="默认专辑封面"><LibraryIcon name="albums" /></div></div>
      <div class="album-metadata"><h2 class="collection-heading" :title="title">{{ title }}</h2><p :title="artists.join(' / ')">{{ artists.join(' / ') || '未知艺术家' }}</p><p>{{ year ?? '年代未知' }}<template v-if="summary"> · {{ summary.song_count }} 首</template></p></div>
    </div>
    <h2 v-else class="collection-heading collection-title"><LibraryIcon :name="kind" />{{ title }}</h2>
    <div class="collection-actions"><button data-play-all :disabled="!actions || actions.locked.value || !entry?.fresh || !songs.length" @click="play(false)"><LibraryIcon name="play" />播放全部</button><button data-shuffle-all :disabled="!actions || actions.locked.value || !entry?.fresh || !songs.length" @click="play(true)"><LibraryIcon name="shuffle" />随机播放</button></div>
    <p v-if="entry?.data" class="collection-scope">可播放歌曲 · {{ songs.length }} 首</p>
    <ul class="song-list"><SongRow v-for="song in songs" :key="`${id}:${song.song_id || song.file_uri}`" :song="song" :fresh="entry?.fresh" /></ul>
    <p v-if="entry?.data && !songs.length" class="library-empty">暂无歌曲</p>
  </section>
</template>
