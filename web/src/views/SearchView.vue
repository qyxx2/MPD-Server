<script setup lang="ts">
import { computed, inject, onUnmounted, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { libraryResourcesKey } from '../stores/library'
import { playerKey } from '../components/player/playerFacts'
import { noticeKey } from '../stores/notices'
import SongRow from '../components/library/SongRow.vue'
import LibraryIcon from '../components/library/LibraryIcon.vue'
import type { Song } from '../types/api'
import type { SearchGroup } from '../types/resources'

const route = useRoute(), router = useRouter()
const resources = inject(libraryResourcesKey)!, player = inject(playerKey)!, notices = inject(noticeKey)!
const input = computed(() => typeof route.query.q === 'string' ? route.query.q : '')
const query = computed(() => input.value.trim())
const path = computed(() => `/api/library/search/results?q=${encodeURIComponent(query.value)}`)
const result = shallowRef<{ path: string; groups: (SearchGroup & { songs: readonly Song[] })[]; songs: readonly Song[]; fresh: boolean } | null>(null)
const songs = computed(() => {
  if (result.value?.path !== path.value || !query.value) return []
  const ordered = [...result.value.groups.flatMap(group => group.songs), ...result.value.songs]
  const seen = new Set<string | null>()
  return ordered.filter(song => {
    if (seen.has(song.song_id)) return false
    seen.add(song.song_id)
    return true
  })
})
const groups = computed(() => result.value?.path === path.value && query.value ? result.value.groups : [])
const labels = { albums: '专辑', artists: '艺术家', genres: '风格', years: '年代', tags: '标签' }
let serial = 0, notice: string | null = null, entered = true
function change(event: Event) {
  const q = (event.target as HTMLInputElement).value
  void router.replace({ path: '/library/search', query: q ? { q } : {} })
}
async function read() {
  const generation = ++serial, key = path.value, epoch = player.marker.epoch
  result.value = null
  if (notice) notices.remove(notice)
  notice = null
  if (!query.value || !epoch) return
  const id = `search:${key}`; notice = id
  notices.set({ id, scope: 'library', message: `搜索 · ${query.value}`, busy: true })
  const current = () => generation === serial && key === path.value && epoch === player.marker.epoch
  try {
    const collection = await resources.read(key, { force: entered }); entered = false
    if (!current()) return
    if (!('groups' in collection)) throw new TypeError('Search results required')
    const ids = [...new Set([...collection.groups.flatMap(g => g.song_ids), ...collection.song_ids])]
    const resolved = await Promise.all(ids.map(async songId => {
      const song = await resources.read(`/api/library/songs/${encodeURIComponent(songId)}`)
      if (!('song_id' in song)) throw new TypeError('Song resource required')
      return song
    }))
    if (!current()) return
    const byId = new Map(resolved.map(song => [song.song_id, song]))
    result.value = { path: key, groups: collection.groups.map(group => ({ ...group, song_ids: [...group.song_ids], songs: group.song_ids.map(id => byId.get(id)!) })), songs: collection.song_ids.map(id => byId.get(id)!), fresh: resources.entry(key).fresh && ids.every(songId => resources.entry(`/api/library/songs/${encodeURIComponent(songId)}`).fresh) }
    notices.remove(id)
  } catch (error) {
    if (!current()) return
    notices.set({ id, scope: 'library', message: `搜索 · ${query.value} · ${error instanceof Error ? error.message : String(error)}`, read })
  }
}
watch(() => JSON.stringify([query.value, player.marker.epoch, player.marker.generation, player.marker.revisions.library, player.marker.trusted]), () => { void read() }, { immediate: true, flush: 'sync' })
onUnmounted(() => { ++serial; if (notice) notices.remove(notice) })
</script>
<template>
  <section class="library-content" aria-label="搜索">
    <RouterLink class="library-back" to="/library"><LibraryIcon name="back" /><span>音乐库</span></RouterLink>
    <form class="search-input" role="search" @submit.prevent>
      <input id="library-search" type="search" aria-label="搜索歌曲、艺术家、专辑、专辑艺术家、风格、年代或标签" :value="input" placeholder="搜索音乐库" autocomplete="off" enterkeyhint="search" @input="change" />
      <button type="button" aria-label="清空搜索" :disabled="!input" @click="router.replace('/library/search')">清空</button>
    </form>
    <div v-if="groups.length" class="search-categories" data-search-categories aria-label="匹配的归类">
      <RouterLink v-for="group in groups" :key="`${group.kind}:${group.source_id}`" data-search-category :title="group.name" :aria-label="`${labels[group.kind]} · ${group.name}`" :to="{ path: `/library/${group.kind}/${encodeURIComponent(group.source_id)}`, query: { search: input } }"><LibraryIcon :name="group.kind" /><span>{{ group.name }}</span></RouterLink>
    </div>
    <ul class="song-list"><SongRow v-for="song in songs" :key="`${path}:${song.song_id}`" :song="song" :fresh="result?.fresh" /></ul>
    <p v-if="!query" class="library-empty">输入关键词搜索</p>
    <p v-else-if="result?.path === path && !songs.length && !groups.length" class="library-empty">没有匹配的歌曲或归类</p>
  </section>
</template>
