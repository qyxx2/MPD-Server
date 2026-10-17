<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { useRoute } from 'vue-router'
import { playerKey } from '../components/player/playerFacts'
import { playerRuntimeKey } from '../components/player/playerActions'
import { playerSessionKey } from '../runtime/playerSession'
import { taskActionsKey } from '../runtime/taskActions'
import { createSongActions } from '../components/library/songActions'
import { useLibraryResource } from '../components/library/libraryResources'
import SongRow from '../components/library/SongRow.vue'
import LibraryTabs from '../components/library/LibraryTabs.vue'
import LibraryIcon from '../components/library/LibraryIcon.vue'
const route = useRoute()
const tabs = [{ kind: 'songs', label: '全部歌曲' }, { kind: 'albums', label: '专辑' }, { kind: 'artists', label: '艺术家' }, { kind: 'genres', label: '风格' }, { kind: 'years', label: '年代' }, { kind: 'tags', label: '标签' }] as const
const kind = computed(() => tabs.find(tab => tab.kind === route.query.kind)?.kind ?? 'songs')
const label = computed(() => tabs.find(tab => tab.kind === kind.value)!.label)
const sort = ref<`${'title' | 'modified_at'}:${'asc' | 'desc'}`>('title:asc')
const sorting = computed(() => {
  const [sort_by, sort_order] = sort.value.split(':') as ['title' | 'modified_at', 'asc' | 'desc']
  return { sort_by, sort_order }
})
const path = computed(() => {
  if (kind.value !== 'songs') return `/api/library/${kind.value}`
  return `/api/library/songs?sort_by=${sorting.value.sort_by}&sort_order=${sorting.value.sort_order}`
})
const entry = useLibraryResource(path, label)
const categories = computed(() => { const data = entry.value?.data; return data && 'kind' in data ? data.items : [] })
const songs = computed(() => { const data = entry.value?.data; return data && !('kind' in data) && 'items' in data ? data.items : [] })
const playable = computed(() => songs.value.filter(song => song.song_id && song.availability_status === 'AVAILABLE').length)
const player = inject(playerKey)!, runtime = inject(playerRuntimeKey), tasks = inject(taskActionsKey), session = inject(playerSessionKey)!
const actions = runtime && tasks ? createSongActions(player, runtime, tasks, () => Boolean(session.actions?.locked)) : null
function play(randomize: boolean) { if (entry.value?.fresh) void actions?.playCollection({ source_type: 'LIBRARY', ...(!randomize ? sorting.value : {}) }, randomize, playable.value, '全部歌曲') }
</script>
<template>
  <section class="library-content" aria-label="音乐库">
    <RouterLink class="library-search-link" to="/library/search">搜索音乐库</RouterLink>
    <LibraryTabs />
    <template v-if="kind === 'songs'">
      <div class="collection-actions"><button data-play-all :disabled="!actions || actions.locked.value || !entry?.fresh || !playable" @click="play(false)"><LibraryIcon name="play" />播放全部</button><button data-shuffle-all :disabled="!actions || actions.locked.value || !entry?.fresh || !playable" @click="play(true)"><LibraryIcon name="shuffle" />随机播放</button><select v-model="sort" class="song-sort" aria-label="排序方式">
        <option value="modified_at:asc">修改时间 · 正序</option><option value="modified_at:desc">修改时间 · 倒序</option>
        <option value="title:asc">名称/标题 · 正序</option><option value="title:desc">名称/标题 · 倒序</option>
      </select></div>
      <ul class="song-list"><SongRow v-for="song in songs" :key="song.song_id || song.file_uri" :song="song" :fresh="entry?.fresh" /></ul>
      <p v-if="entry?.data && !songs.length" class="library-empty">暂无歌曲</p>
    </template>
    <template v-else>
      <ul class="collection-list"><li v-for="item in categories" :key="item.id"><RouterLink :to="`/library/${kind}/${encodeURIComponent(item.id)}`" :data-collection-id="item.id" :aria-label="item.name"><span class="collection-name">{{ item.name || '—' }}</span><span class="collection-count">{{ item.song_count }} 首</span></RouterLink></li></ul>
      <p v-if="entry?.data && !categories.length" class="library-empty">暂无{{ label }}</p>
    </template>
  </section>
</template>
