<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref } from 'vue'
import { routerKey } from 'vue-router'
import { libraryResourcesKey } from '../../stores/library'
import { noticeKey } from '../../stores/notices'
import FavoriteIcon from '../library/FavoriteIcon.vue'
import PlayerLyrics from './PlayerLyrics.vue'
import ArtworkStage from './ArtworkStage.vue'
import { outputMetadata, playerKey, sourceMetadata } from './playerFacts'
import PlaybackControls from './PlaybackControls.vue'
import ProgressControl from './ProgressControl.vue'
import { playerSessionKey } from '../../runtime/playerSession'
const props = defineProps<{ presentation: 'portrait' | 'landscape' }>()
const emit = defineEmits<{ infoHeight: [height: number, minimumWidth: number] }>()
const information = ref<HTMLElement | null>(null)
const songDetails = ref<HTMLDetailsElement | null>(null)
function closeDetails() {
  if (!songDetails.value) return
  songDetails.value.open = false
  songDetails.value.querySelector('summary')?.focus()
}
let sizeObserver: ResizeObserver | undefined
onMounted(() => {
  if (props.presentation !== 'landscape' || !information.value || typeof ResizeObserver === 'undefined') return
  sizeObserver = new ResizeObserver(() => {
    if (!information.value) return
    const controls = information.value.querySelector<HTMLElement>('.transport-row')
    const minimumWidth = controls ? [...controls.children].reduce((sum, child) => sum + child.getBoundingClientRect().width, 0) + (parseFloat(getComputedStyle(controls).columnGap) || 0) * Math.max(0, controls.children.length - 1) : 0
    emit('infoHeight', information.value.getBoundingClientRect().height, minimumWidth)
  })
  sizeObserver.observe(information.value)
})
onUnmounted(() => sizeObserver?.disconnect())
const store = inject(playerKey)!
const { actions, facts, position, media, handoff, mediaMode, artworkIdentity, statusFeedback } = inject(playerSessionKey)!
const router = inject(routerKey, undefined), resources = inject(libraryResourcesKey, undefined), notices = inject(noticeKey)!
const artistPending = ref(false)
let active = true
const navigationNotice = 'player-artist-navigation'
onUnmounted(() => { active = false; notices.remove(navigationNotice) })
async function openArtist(name: string) {
  if (!router || !resources || artistPending.value) return
  const song = media.value.song, epoch = store.marker.epoch, route = router.currentRoute.value
  const current = () => active && router.currentRoute.value === route && media.value.song === song && store.marker.epoch === epoch
  artistPending.value = true
  notices.set({ id: navigationNotice, scope: 'library', message: `读取艺术家 · ${name}`, busy: true })
  try {
    const data = await resources.read('/api/library/artists')
    if (!current()) { notices.remove(navigationNotice); return }
    const artist = 'kind' in data && data.kind === 'artists' ? data.items.find(item => item.name === name) : undefined
    if (!artist) throw new Error('音乐库中未找到该艺术家')
    notices.remove(navigationNotice)
    await router.push(`/library/artists/${encodeURIComponent(artist.id)}`)
  } catch (error) {
    if (current()) notices.set({ id: navigationNotice, scope: 'library', message: `艺术家 · ${name} · ${error instanceof Error ? error.message : String(error)}`, read: () => openArtist(name) })
  } finally { artistPending.value = false }
}
function openAlbum() {
  const id = media.value.song?.album_id
  if (id) void router?.push(`/library/albums/${encodeURIComponent(id)}`)
}
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
  <article class="player" :class="{ 'landscape-player': presentation === 'landscape' }">
    <section class="player-content" aria-label="播放状态">
      <div class="media-stage">
        <div v-if="presentation === 'landscape'" class="landscape-artwork"><ArtworkStage :song="media.song" :resource-scope="`${store.marker.epoch}/${store.marker.revisions.library}/${store.marker.generation}/${artworkIdentity}`" /></div>
        <button v-else-if="mediaMode === 'artwork'" type="button" class="artwork-toggle" aria-label="显示歌词" @click="mediaMode = 'lyrics'">
          <ArtworkStage :song="media.song" :resource-scope="`${store.marker.epoch}/${store.marker.revisions.library}/${store.marker.generation}/${artworkIdentity}`" />
        </button>
        <PlayerLyrics v-else :show-artwork-return="true" />
      </div>
      <div ref="information" class="player-information">
      <div class="identity" data-testid="actual-identity">
        <details v-if="presentation === 'landscape'" ref="songDetails" class="player-song-details" @keydown.esc.prevent.stop="closeDetails">
          <summary aria-label="查看完整歌曲信息"><h2 :title="media.title">{{ media.title }}</h2></summary>
          <div class="player-song-information" role="region" aria-label="完整歌曲信息">
            <p>{{ media.title }}</p><p>{{ media.song?.artists.join(' / ') || '艺术家未知' }}</p><p>{{ media.song?.album || '专辑未知' }}</p>
            <p>{{ sourceMetadata(media.song) }}</p><p>{{ dacDetail }}</p>
            <button type="button" @click="closeDetails">关闭歌曲信息</button>
          </div>
        </details>
        <h2 v-else :title="media.title">{{ media.title }}</h2>
        <div class="player-artist-row">
          <p class="artist" :title="media.song?.artists.join(' / ')"><template v-for="(artist, index) in media.song?.artists" :key="`${index}:${artist}`"><span v-if="index" aria-hidden="true"> / </span><button type="button" class="player-metadata-link" data-player-library="artists" :aria-label="`查看艺术家 ${artist}`" :disabled="artistPending" @click="openArtist(artist)">{{ artist }}</button></template><template v-if="!media.song?.artists.length">艺术家未知</template></p>
          <FavoriteIcon v-if="media.song?.song_id" :song-id="media.song.song_id" :blocked="handoff || !facts.song || facts.song.song_id !== media.song.song_id || Boolean(actions?.locked)" interactive />
        </div>
        <p class="muted" :title="media.song?.album || undefined"><button v-if="media.song?.album_id && media.song.album" type="button" class="player-metadata-link" data-player-library="albums" :aria-label="`查看专辑 ${media.song.album}`" @click="openAlbum">{{ media.song.album }}</button><template v-else>{{ media.song?.album || '\u00a0' }}</template></p>
      </div>
      <div class="metadata-row"><div data-testid="source-metadata" class="metadata" aria-label="源文件格式"><p>{{ sourceMetadata(media.song) }}</p></div><span data-testid="output-fact" class="dac-summary" aria-label="输出确认事实" :title="dacDetail">{{ dacSummary }}</span></div>
      <ProgressControl :actions="actions" :position="position" :duration="media.duration" />
      <PlaybackControls v-if="actions" :actions="actions" :handoff="handoff" :display-primary="media.primary" :status-feedback="statusFeedback" />
      </div>
    </section>
  </article>
</template>

<style scoped>
.player { display: flex; flex-direction: column; flex: 1; width: 100%; }
.player-content { display: flex; flex-direction: column; flex: 1; }
.media-stage { width: 100%; min-height: 4rem; flex: 1; display: grid; grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(0, 1fr); container-type: size; }
.artwork-toggle { width: min(100%, 100cqh); height: auto; align-self: center; justify-self: center; max-width: 100%; aspect-ratio: 1; padding: 0; border: 0; border-radius: var(--radius-medium); background: transparent; cursor: pointer; }
.artwork-toggle > .artwork-stage { width: 100%; height: 100%; }
.identity h2 { display: block; height: auto; max-height: none; margin: .75rem 0 .5rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.player-metadata-link { min-width: 0; max-width: 100%; min-height: 44px; padding: 0; border: 0; color: inherit; background: transparent; text-align: left; line-height: inherit; overflow-wrap: anywhere; border-radius: var(--radius-small); cursor: pointer; }
.player-metadata-link:hover { background: var(--glass-surface); }
.identity .artist { height: 3.5em; max-height: 3.5em; font-size: 1.125rem; }
.identity .muted { height: 3.5em; max-height: 3.5em; margin-top: .2rem; font-size: 1rem; }
.player-artist-row .favorite-toggle { transform: none; }
.player-information { display: contents; }
.landscape-player { min-height: 0; height: 100%; margin: 0; max-width: none; }
.landscape-player .player-content { flex: none; height: 100%; justify-content: center; gap: 0; }
.landscape-player .media-stage { flex: none; height: var(--player-width); min-height: 0; }
.landscape-artwork { width: 100%; aspect-ratio: 1; }
.landscape-artwork > .artwork-stage { width: 100%; height: 100%; border-radius: 24px; }
.landscape-player .player-information { display: flex; flex: none; flex-direction: column; gap: .25rem; padding-top: 0; }
.landscape-player .identity h2 { margin: 0; font-size: 1.75rem; line-height: 1.3; }
.landscape-player .identity .artist, .landscape-player .identity .muted { height: 44px; max-height: 44px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.landscape-player .identity .muted { height: max(44px, 1.6em); max-height: none; margin: 0; }
.landscape-player .metadata p { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.landscape-player .identity .artist { height: max(44px, 1.5em); max-height: none; }
.player-song-details { min-width: 0; }
.player-song-details summary { position: relative; list-style: none; cursor: pointer; }
.player-song-details summary::-webkit-details-marker { display: none; }
/* Expand the title's hit area without changing the confirmed heading geometry. */
.player-song-details summary::after { content: ''; position: absolute; inset-inline: 0; top: 50%; transform: translateY(-50%); height: max(100%, 44px); }
.player-song-information { position: fixed; z-index: 14; inset: 50% auto auto 50%; transform: translate(-50%, -50%); width: min(28rem, calc(100vw - 2rem)); max-height: calc(100dvh - 2rem); overflow: auto; padding: 1rem; border: 1px solid var(--subtle-border); border-radius: var(--radius-small); background: var(--overlay-surface); box-shadow: 0 .5rem 1.5rem #0006; overflow-wrap: anywhere; }
.player-song-information p + p { margin-top: .5rem; }
.player-song-information button { margin-top: .75rem; color: var(--accent); border: 0; border-radius: var(--radius-small); background: transparent; }
</style>
