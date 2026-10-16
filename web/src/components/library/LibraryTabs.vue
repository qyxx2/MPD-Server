<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LibraryIcon from './LibraryIcon.vue'
const route = useRoute(), router = useRouter(), strip = ref<HTMLElement | null>(null)
const tabs = [{ kind: 'songs', label: '全部歌曲' }, { kind: 'albums', label: '专辑' }, { kind: 'artists', label: '艺术家' }, { kind: 'favorites', label: '收藏' }, { kind: 'playlists', label: '播放列表' }, { kind: 'genres', label: '风格' }, { kind: 'years', label: '年代' }, { kind: 'tags', label: '标签' }] as const
const selected = computed(() => route.path === '/library/playlists' ? 'playlists' : route.path === '/library/favorites' ? 'favorites' : tabs.find(t => t.kind === route.query.kind)?.kind ?? 'songs')
function choose(kind: typeof tabs[number]['kind']) { if (kind === 'playlists' || kind === 'favorites') void router.push(`/library/${kind}`); else void router.replace({ path: '/library', query: { kind } }) }
watch(selected, async () => { await nextTick(); strip.value?.querySelector<HTMLElement>('[aria-pressed="true"]')?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' }) }, { immediate: true })
</script>
<template><div ref="strip" class="library-tabs" role="group" aria-label="浏览分类"><button v-for="tab in tabs" :key="tab.kind" :data-library-kind="tab.kind" :aria-pressed="selected === tab.kind" @click="choose(tab.kind)"><LibraryIcon :name="tab.kind" /><span>{{ tab.label }}</span></button></div></template>
