<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, watch } from 'vue'
import LyricsStage from '../components/player/LyricsStage.vue'
import ArtworkStage from '../components/player/ArtworkStage.vue'
import { derivePlayerFacts, outputMetadata, playerKey, sourceMetadata } from '../components/player/playerFacts'
import PlaybackControls from '../components/player/PlaybackControls.vue'
import PlaybackStatus from '../components/player/PlaybackStatus.vue'
import ProgressControl from '../components/player/ProgressControl.vue'
import { createPlayerActions, playerRuntimeKey } from '../components/player/playerActions'
import { createPlayerClock } from '../components/player/playerClock'
import { createPlayerPresentation } from '../components/player/playerPresentation'
import { parseLyrics } from '../components/player/lyrics'
const mediaMode = ref<'artwork' | 'lyrics'>('artwork')
const runtime = inject(playerRuntimeKey, null)
const store = inject(playerKey)!
const actions = runtime ? createPlayerActions(store, runtime) : undefined
const clock = createPlayerClock(store)
const displayPosition = ref<number | null>(clock.position())
let tick: ReturnType<typeof setInterval> | undefined
function visibility() {
  clock.setVisible(!document.hidden)
  displayPosition.value = clock.position()
  if (!document.hidden) void runtime?.refresh().catch(() => {})
}
onMounted(() => {
  tick = setInterval(() => { displayPosition.value = clock.position() }, 100)
  document.addEventListener('visibilitychange', visibility)
  clock.setVisible(!document.hidden)
  // Initial WS latency is unknown: establish a conservatively timed HTTP baseline.
  if (store.writable && store.snapshot?.playback_observation.actual_state === 'playing') void runtime?.refresh().catch(() => {})
})
onUnmounted(() => { actions?.dispose(); clock.dispose(); clearInterval(tick); document.removeEventListener('visibilitychange', visibility) })
watch(() => [store.snapshot, store.writable, store.readTiming], () => { displayPosition.value = clock.position() }, { flush: 'sync' })
watch(() => store.writable, ready => { if (ready) void runtime?.refresh().catch(() => {}) })
const presentation = createPlayerPresentation(store, displayPosition, actions)
onUnmounted(() => presentation.dispose())
const position = presentation.position
const media = presentation.media
const handoff = presentation.handoff
const artworkIdentity = ref('')
watch(() => store.snapshot, () => {
  const o = store.snapshot?.playback_observation
  if (o?.control_target) artworkIdentity.value = JSON.stringify([o.bound_queue_item_id, o.control_target.token, o.actual_current?.entry_id])
  else if (!handoff.value) artworkIdentity.value = ''
}, { immediate: true, flush: 'sync' })
const facts = computed(() => derivePlayerFacts(store.snapshot, store.writable))
function seekLyric(seconds: number) {
  if (!actions || actions.locked || !actions.facts.value.capabilities.seek) return
  actions.beginSeek(); actions.preview(seconds); void actions.releaseSeek()
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
const statusFeedback = computed(() => {
  if (handoff.value) return ''
  if (facts.value.stale) return `${facts.value.diagnostic} · 观察已过期`
  const observation = store.snapshot?.playback_observation
  if (observation?.actual_state === 'stopped' && observation.sync_status === 'CONFIRMED') return facts.value.stateLabel
  if (observation?.actual_state === null && observation.sync_status === 'UNBOUND') return '实际状态未知 · 等待播放观察'
  return facts.value.diagnostic === '已确认' ? '' : facts.value.diagnostic
})
const artworkNotice = ref('')
const notices = computed(() => {
  const result: { id: string; message: string; busy?: boolean }[] = []
  const add = (id: string, message: string, busy = false) => result.push({ id, message, busy })
  if (!store.writable) add('connection', '连接中断 · 只读；等待完整状态恢复')
  if (!handoff.value && store.writable && !facts.value.capabilities.pause && !facts.value.capabilities.resume) add('selection', '需明确选曲后播放')
  if (store.error) add('read', '状态读取异常，保留最后事实')
  const song = media.value.song
  if (song && song.availability_status !== 'AVAILABLE') add('file', song.availability_status === 'MISSING' ? '文件缺失' : '文件不可读')
  if (mediaMode.value === 'artwork' && artworkNotice.value) add('artwork', artworkNotice.value, artworkNotice.value === '封面加载中')
  if (mediaMode.value === 'lyrics') {
    const lyrics = parseLyrics(song?.lyrics || '', song?.lyrics_format || null)
    if (song?.lyrics_status === 'read_error') add('lyrics-read', `歌词读取失败${song.lyrics ? ' · 显示可用文本' : ''}`)
    else if (!song?.lyrics) add('lyrics-missing', '无歌词')
    if (song?.lyrics && !lyrics.synchronized) add('lyrics-format', `${song.lyrics_format?.toLowerCase() === 'lrc' ? '无法同步 · 普通文本' : '普通文本 · 不同步'}${song.lyrics_source ? ` · ${song.lyrics_source}` : ''}`)
    if (lyrics.synchronized && (!facts.value.song || displayPosition.value === null)) add('lyrics-clock', '进度未确认 · 暂无高亮')
  }
  return result
})
</script>
<template>
  <article class="player">
    <header class="page-header"><p class="eyebrow">MPD SERVER</p><PlaybackStatus :actions="actions" :handoff="handoff" :status-feedback="statusFeedback" :notices="notices"><aside v-if="facts.lastSong && !handoff" class="last-business" data-testid="last-business"><p class="label">最后业务歌曲 · 不代表实际正在播放</p><p>{{ facts.lastSong.title }}</p><p class="muted">{{ facts.lastSong.artists.join(' / ') || '艺术家未知' }}</p></aside></PlaybackStatus><span class="connection connection-slot" aria-hidden="true">实时连接</span></header>
    <section class="player-content" aria-label="播放状态">
      <div class="media-stage">
        <button v-if="mediaMode === 'artwork'" type="button" class="artwork-toggle" aria-label="显示歌词" @click="mediaMode = 'lyrics'">
          <ArtworkStage :song="media.song" :resource-scope="`${store.marker.epoch}/${store.marker.revisions.library}/${store.marker.generation}/${artworkIdentity}`" @notice="artworkNotice = $event" />
        </button>
        <LyricsStage v-else :song="media.song" :position="facts.song ? displayPosition : null" :duration="facts.duration" :seek-enabled="Boolean(actions?.facts.value.capabilities.seek && !actions.locked)" :resource-scope="`${store.marker.epoch}/${store.marker.revisions.library}/${store.marker.generation}/${artworkIdentity}`" @show-artwork="mediaMode = 'artwork'" @seek="seekLyric" />
      </div>
      <div class="identity" data-testid="actual-identity"><h2>{{ media.title }}</h2><p class="artist">{{ media.song?.artists.join(' / ') || '艺术家未知' }}</p><p v-if="media.song?.album" class="muted">{{ media.song.album }}</p></div>
      <div class="metadata-row"><div data-testid="source-metadata" class="metadata" aria-label="源文件格式"><p>{{ sourceMetadata(media.song) }}</p></div><span data-testid="output-fact" class="dac-summary" aria-label="输出确认事实" :title="dacDetail">{{ dacSummary }}</span></div>
      <ProgressControl :actions="actions" :position="position" :duration="media.duration" />
      <PlaybackControls v-if="actions" :actions="actions" :handoff="handoff" :display-primary="media.primary" :status-feedback="statusFeedback" />
    </section>
  </article>
</template>

<style scoped>
.player { display: flex; flex-direction: column; flex: 1; width: 100%; padding-bottom: calc(var(--app-bottom-bar-height) + env(safe-area-inset-bottom)); }
.player-content { display: flex; flex-direction: column; flex: 1; }
.page-header { position: relative; }
.connection-slot { visibility: hidden; }
.media-stage { width: 100%; min-height: 4rem; flex: 1; display: grid; grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(0, 1fr); container-type: size; }
.artwork-toggle { width: min(100%, 100cqh); height: auto; align-self: center; justify-self: center; max-width: 100%; aspect-ratio: 1; padding: 0; border: 0; border-radius: var(--radius-medium); background: transparent; cursor: pointer; }
.artwork-toggle > .artwork-stage { width: 100%; height: 100%; }
</style>
