import type { Notice } from '../stores/notices'
import type { PlayerStore } from '../stores/player'
import { computed, onMounted, ref, watch, type InjectionKey } from 'vue'
import { derivePlayerFacts } from '../components/player/playerFacts'
import { createPlayerActions, type PlayerRuntime } from '../components/player/playerActions'
import { createPlayerClock } from '../components/player/playerClock'
import { createPlayerPresentation } from '../components/player/playerPresentation'
import { parseLyrics } from '../components/player/lyrics'
export function createPlayerSession(store: PlayerStore, runtime: PlayerRuntime | null) {
  const mediaMode = ref<'artwork' | 'lyrics'>('artwork')
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

  const stopPosition = watch(() => [store.snapshot, store.writable, store.readTiming], () => { displayPosition.value = clock.position() }, { flush: 'sync' })
  const stopWritable = watch(() => store.writable, ready => { if (ready) void runtime?.refresh().catch(() => {}) })
  const presentation = createPlayerPresentation(store, displayPosition, actions)

  const position = presentation.position
  const media = presentation.media
  const handoff = presentation.handoff
  const artworkIdentity = ref('')
  const stopIdentity = watch(() => store.snapshot, () => {
    const o = store.snapshot?.playback_observation
    if (o?.control_target) artworkIdentity.value = JSON.stringify([o.bound_queue_item_id, o.control_target.token, o.actual_current?.entry_id])
    else if (!handoff.value) artworkIdentity.value = ''
  }, { immediate: true, flush: 'sync' })
  const facts = computed(() => derivePlayerFacts(store.snapshot, store.writable))
  function seekLyric(seconds: number) {
    if (!actions || actions.locked || !actions.facts.value.capabilities.seek) return
    actions.beginSeek(); actions.preview(seconds); void actions.releaseSeek()
  }
  const statusFeedback = computed(() => {
    if (handoff.value) return ''
    if (facts.value.stale) return `${facts.value.diagnostic} · 观察已过期`
    const observation = store.snapshot?.playback_observation
    if (observation?.actual_state === 'stopped' && observation.sync_status === 'CONFIRMED') return facts.value.stateLabel
    if (observation?.actual_state === null && observation.sync_status === 'UNBOUND') return '实际状态未知 · 等待播放观察'
    return facts.value.diagnostic === '已确认' ? '' : facts.value.diagnostic
  })
  const artworkNotice = ref('')
  let operationNumber = 0, previousAction: string | null = null, wasConfirmed = false
  const operationId = ref('')
  const stopOperation = watch(() => [actions?.ui.pending, actions?.ui.stopPending, actions?.ui.confirmed, actions?.ui.action, store.marker.epoch] as const, (current, old) => {
    if (current[4] !== old?.[4]) { operationId.value = ''; previousAction = null; wasConfirmed = false }
    if ((current[0] || current[1]) && (!operationId.value || previousAction !== current[3] || wasConfirmed && !current[2])) {
      operationId.value = `player-operation:${store.marker.epoch}:${++operationNumber}`
    }
    previousAction = current[3] ?? null; wasConfirmed = Boolean(current[2])
  }, { flush: 'sync' })
  const notices = computed(() => {
    const result: Notice[] = []
    const add = (id: string, message: string, busy = false, level?: 'info' | 'warning') => result.push({ id, scope: 'player', message, busy, level,
      read: ['connection', 'read', 'playback-status'].includes(id) && runtime ? () => runtime.refresh() : undefined })
    const ui = actions?.ui
    if (ui && operationId.value && (ui.pending || ui.stopPending || ui.syncing || ui.unknown || ui.error || ui.confirmed)) {
      const description = ui.action ? { pause: '暂停', resume: '继续播放', next: '下一首', previous: '上一首', seek: '调整进度', stop: '停止播放' }[ui.action] : '播放操作'
      const awaitingObservation = ui.confirmed && ui.action !== 'stop' && !facts.value.bound
      const status = ui.unknown ? 'unknown' : ui.error ? 'failed' : ui.readFailed ? 'failed' : ui.pending || ui.stopPending ? 'pending' : ui.syncing || handoff.value ? 'syncing' : awaitingObservation ? 'failed' : 'success'
      const message = ui.unknown ? `结果未知 · ${ui.error}` : ui.error || (ui.readFailed || awaitingObservation && !handoff.value ? '操作已确认 · 状态未同步' : status === 'pending' || status === 'syncing' ? `${ui.confirmed ? '操作已确认 · ' : ''}${ui.action === 'seek' ? '正在同步进度' : '正在同步播放状态'} · 展示上次确认数据` : '操作已确认 · 已同步')
      result.push({ id: operationId.value, scope: 'player', description, status, message,
        retry: ui.unknown ? () => actions!.retry() : undefined, read: status === 'failed' || status === 'unknown' ? () => actions!.refresh() : undefined })
    }
    // Handoff and canonical diagnostics are a separate fact only when no
    // operation already explains the same transition.
    if (handoff.value && !result.length) add('playback-status', '正在同步 · 展示上次确认数据', true)
    else if (statusFeedback.value) add('playback-status', statusFeedback.value, false, statusFeedback.value === facts.value.stateLabel && store.snapshot?.playback_observation.sync_status === 'CONFIRMED' ? 'info' : undefined)
    if (!store.writable) add('connection', '连接中断 · 只读；等待完整状态恢复')
    if (!handoff.value && store.writable && !facts.value.capabilities.pause && !facts.value.capabilities.resume) add('selection', '需明确选曲后播放')
    if (store.error) add('read', '状态读取异常，保留最后事实')
    const song = media.value.song
    if (song && song.availability_status !== 'AVAILABLE') add('file', song.availability_status === 'MISSING' ? '文件缺失' : '文件不可读')
    if (artworkNotice.value) add('artwork', artworkNotice.value, artworkNotice.value === '封面加载中')
    if (mediaMode.value === 'lyrics') {
      const lyrics = parseLyrics(song?.lyrics || '', song?.lyrics_format || null)
      if (song?.lyrics_status === 'read_error') add('lyrics-read', `歌词读取失败${song.lyrics ? ' · 显示可用文本' : ''}`)
      else if (!song?.lyrics) add('lyrics-missing', '无歌词')
      if (song?.lyrics && !lyrics.synchronized) add('lyrics-format', `${song.lyrics_format?.toLowerCase() === 'lrc' ? '无法同步 · 普通文本' : '普通文本 · 不同步'}${song.lyrics_source ? ` · ${song.lyrics_source}` : ''}`)
      if (lyrics.synchronized && (!facts.value.song || displayPosition.value === null)) add('lyrics-clock', '进度未确认 · 暂无高亮')
    }
    return result
  })

  function dispose() { actions?.dispose(); clock.dispose(); presentation.dispose(); stopPosition(); stopWritable(); stopIdentity(); stopOperation(); clearInterval(tick); document.removeEventListener('visibilitychange', visibility) }
  return { actions, clock, presentation, position, media, handoff, mediaMode, artworkIdentity, artworkNotice, facts, statusFeedback, notices, displayPosition, seekLyric, dispose }
}
export type PlayerSession = ReturnType<typeof createPlayerSession>
export const playerSessionKey: InjectionKey<PlayerSession> = Symbol('player-session')
