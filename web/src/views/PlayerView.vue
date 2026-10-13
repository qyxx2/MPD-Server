<script setup lang="ts">
import { computed, inject } from 'vue'
import FavoriteIcon from '../components/library/FavoriteIcon.vue'
import LyricsStage from '../components/player/LyricsStage.vue'
import ArtworkStage from '../components/player/ArtworkStage.vue'
import { outputMetadata, playerKey, sourceMetadata } from '../components/player/playerFacts'
import PlaybackControls from '../components/player/PlaybackControls.vue'
import ProgressControl from '../components/player/ProgressControl.vue'
import { playerSessionKey } from '../runtime/playerSession'
const store = inject(playerKey)!
const { actions, facts, position, media, handoff, mediaMode, artworkIdentity, displayPosition, statusFeedback, seekLyric } = inject(playerSessionKey)!
const dacSummary = computed(() => {
  if (facts.value.outputFreshness === 'unknown') return 'DAC尚未确认'
  if (facts.value.outputFreshness === 'stale') return 'DAC状态已过期'
  return facts.value.output?.status === 'ACTIVE' ? 'DAC已启用' : facts.value.output?.status === 'INACTIVE' ? 'DAC未启用' : 'DAC不可用'
})
const dacDetail = computed(() => {
  const observation = store.snapshot?.output_observation
  const error = observation?.error_message || facts.value.output?.error_message
  return [dacSummary.value, facts.value.outputFreshness === 'unknown' ? null : outputMetadata(facts.value.output), error].filter(Boolean).join(' · ')
})
</script>
<template>
  <article class="player">
    <section class="player-content" aria-label="播放状态">
      <div class="media-stage">
        <button v-if="mediaMode === 'artwork'" type="button" class="artwork-toggle" aria-label="显示歌词" @click="mediaMode = 'lyrics'">
          <ArtworkStage :song="media.song" :resource-scope="`${store.marker.epoch}/${store.marker.revisions.library}/${store.marker.generation}/${artworkIdentity}`" />
        </button>
        <LyricsStage v-else :song="media.song" :position="facts.song ? displayPosition : null" :duration="facts.duration" :seek-enabled="Boolean(actions?.facts.value.capabilities.seek && !actions.locked)" :resource-scope="`${store.marker.epoch}/${store.marker.revisions.library}/${store.marker.generation}/${artworkIdentity}`" @show-artwork="mediaMode = 'artwork'" @seek="seekLyric" />
      </div>
      <div class="identity" data-testid="actual-identity"><h2 :title="media.title">{{ media.title }}</h2><div class="player-artist-row"><p class="artist" :title="media.song?.artists.join(' / ')">{{ media.song?.artists.join(' / ') || '艺术家未知' }}</p><FavoriteIcon v-if="media.song?.song_id" :song-id="media.song.song_id" :blocked="handoff || !facts.song || facts.song.song_id !== media.song.song_id || Boolean(actions?.locked)" interactive /></div><p class="muted" :title="media.song?.album || undefined">{{ media.song?.album || '\u00a0' }}</p></div>
      <div class="metadata-row"><div data-testid="source-metadata" class="metadata" aria-label="源文件格式"><p>{{ sourceMetadata(media.song) }}</p></div><span data-testid="output-fact" class="dac-summary" aria-label="输出确认事实" :title="dacDetail">{{ dacSummary }}</span></div>
      <ProgressControl :actions="actions" :position="position" :duration="media.duration" />
      <PlaybackControls v-if="actions" :actions="actions" :handoff="handoff" :display-primary="media.primary" :status-feedback="statusFeedback" />
    </section>
  </article>
</template>

<style scoped>
.player { display: flex; flex-direction: column; flex: 1; width: 100%; }
.player-content { display: flex; flex-direction: column; flex: 1; }
.media-stage { width: 100%; min-height: 4rem; flex: 1; display: grid; grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(0, 1fr); container-type: size; }
.artwork-toggle { width: min(100%, 100cqh); height: auto; align-self: center; justify-self: center; max-width: 100%; aspect-ratio: 1; padding: 0; border: 0; border-radius: var(--radius-medium); background: transparent; cursor: pointer; }
.artwork-toggle > .artwork-stage { width: 100%; height: 100%; }
.identity h2 { display: block; height: auto; max-height: none; margin: .75rem 0 .15rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
