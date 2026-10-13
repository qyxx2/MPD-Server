<script setup lang="ts">
import { computed, inject } from 'vue'
import { favoritesKey } from '../../stores/favorites'
const props = defineProps<{ songId: string | null | undefined; interactive?: boolean; blocked?: boolean; menu?: boolean }>()
const favorites = inject(favoritesKey, undefined)
const selected = computed(() => Boolean(props.songId && favorites?.isFavorite(props.songId)))
const disabled = computed(() => props.blocked || !favorites || !props.songId || favorites.locked(props.songId))
function toggle() { if (!disabled.value && props.songId) void favorites?.setFavorite(props.songId, !selected.value) }
</script>
<template>
  <button v-if="interactive || menu" type="button" class="favorite-toggle" :class="{ 'favorite-selected': selected && !menu, 'favorite-menu': menu }" :data-favorite-toggle="songId" :aria-label="selected ? '取消收藏' : '收藏'" :aria-pressed="selected" :disabled="disabled" @click.stop="toggle"><svg v-if="!menu" viewBox="0 0 24 24" width="26" height="26" :fill="selected ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" /></svg><span v-if="menu">{{ selected ? '取消收藏' : '收藏' }}</span></button>
  <span v-else-if="selected" class="favorite-selected favorite-display" @click.stop :data-favorite-display="songId" role="img" aria-label="已收藏"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" /></svg></span>
</template>
