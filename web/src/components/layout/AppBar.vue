<script setup lang="ts">
import { inject } from 'vue'
import PlaybackStatus from '../player/PlaybackStatus.vue'
import { playerSessionKey } from '../../runtime/playerSession'
import { noticeKey } from '../../stores/notices'
const { actions, handoff, facts } = inject(playerSessionKey)!
const notices = inject(noticeKey)!
</script>
<template>
  <header class="page-header"><PlaybackStatus :actions="actions" :activities="notices"><aside v-if="facts.lastSong && !handoff" class="last-business" data-testid="last-business"><p class="label">最后业务歌曲 · 不代表实际正在播放</p><p>{{ facts.lastSong.title }}</p><p class="muted">{{ facts.lastSong.artists.join(' / ') || '艺术家未知' }}</p></aside></PlaybackStatus></header>
</template>
<style scoped>
.page-header { position: relative; z-index: 20; height: var(--app-bar-height); flex-shrink: 0; }
</style>
