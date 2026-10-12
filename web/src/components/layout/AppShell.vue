<script setup lang="ts">
import { onMounted, onUnmounted, provide, ref, watch, watchEffect } from 'vue'
import type { PlayerStore } from '../../stores/player'
import type { PlayerRuntime } from '../player/playerActions'
import { playerRuntimeKey } from '../player/playerActions'
import { playerKey } from '../player/playerFacts'
import { createPlayerSession, playerSessionKey } from '../../runtime/playerSession'
import { createTaskActions, taskActionsKey, type TaskActions } from '../../runtime/taskActions'
import { createNoticeStore, noticeKey } from '../../stores/notices'
import { createArtworkStore, artworkKey } from '../../stores/artwork'
import { createQueueUi, queueUiKey } from '../../stores/queueUi'
import { createAppLibraryStore, songLibraryKey, libraryResourcesKey } from '../../stores/library'
import { createPlaylistsStore, playlistResourcesKey } from '../../stores/playlists'
import { parsePlaylistResource } from '../../services/resourceWire'
import { createFavoritesStore, favoritesKey } from '../../stores/favorites'
import { createOutputActions, outputActionsKey } from '../settings/outputActions'
import { createMPDConnection, mpdConnectionKey } from '../settings/mpdConnection'
import AppBar from './AppBar.vue'
import AppBackground from './AppBackground.vue'
import BottomNavigation from './BottomNavigation.vue'
const props = defineProps<{ store: PlayerStore; realtime: { start(): void; stop(): void; refresh?(): Promise<void> }; api?: PlayerRuntime['api'] }>()
provide(playerKey, props.store)
let tasks: TaskActions | null = null
const runtime = props.api && props.realtime.refresh ? { api: props.api, refresh: () => props.realtime.refresh!(), mutationLocked: () => Boolean(tasks?.entries.value.some(record => record.state === 'pending' || record.state === 'unknown' || record.busy)) } : null
if (runtime) provide(playerRuntimeKey, runtime)
const session = createPlayerSession(props.store, runtime)
provide(playerSessionKey, session)
const notices = createNoticeStore(); provide(noticeKey, notices)
const queueUi = createQueueUi(props.store); provide(queueUiKey, queueUi)
const library = props.api ? createAppLibraryStore({ api: props.api, player: props.store }) : null
if (library) { provide(songLibraryKey, library.songs); provide(libraryResourcesKey, library.resources) }
const playlists = props.api ? createPlaylistsStore({ api: props.api, player: props.store, decode: parsePlaylistResource }) : null
if (playlists) provide(playlistResourcesKey, playlists)
const artwork = createArtworkStore({ fetch: (input, init) => fetch(input, init) }); provide(artworkKey, artwork)
tasks = runtime ? createTaskActions({ ...runtime, player: props.store }) : null
if (tasks) provide(taskActionsKey, tasks)
const mpdConnection = runtime && tasks ? createMPDConnection(props.store, runtime, tasks, notices) : null
if (mpdConnection) provide(mpdConnectionKey, mpdConnection)
const output = runtime && tasks ? createOutputActions(props.store, runtime, tasks, notices, () => Boolean(session.actions?.locked)) : null
if (output) provide(outputActionsKey, output)
const favorites = runtime && tasks && playlists ? createFavoritesStore(props.store, playlists, runtime, tasks, notices) : null
if (favorites) provide(favoritesKey, favorites)
const background = ref<string | null>(null)
watch(() => [props.store.snapshot, props.store.writable, session.handoff.value, session.media.value.song, props.store.marker.revisions.library], () => {
  // Stale state retains only the already accepted resource; it grants no new identity.
  if (!props.store.writable || session.facts.value.stale) return
  const song = session.media.value.song
  const scope = `${props.store.marker.epoch}/${props.store.marker.revisions.library}/${props.store.marker.generation}/${session.artworkIdentity.value}`
  void artwork.read(song, scope)
}, { immediate: true, flush: 'sync' })
watchEffect(() => {
  const facts = session.facts.value
  if (facts.song && props.store.snapshot?.playback_observation.control_target) background.value = artwork.decodedUrl
  else if (!facts.stale && !session.handoff.value) background.value = null
  session.artworkNotice.value = artwork.status === '无封面' ? '' : artwork.status
})
watch(() => props.store.marker.epoch, () => notices.beginEpoch(), { flush: 'sync' })
let syncEpoch: string | null = null
let syncActivity: string | null = null
watch(() => [props.store.snapshot?.library_sync, props.store.marker.trusted, props.store.marker.epoch, props.store.error] as const, ([sync, trusted, epoch]) => {
  if (epoch !== syncEpoch) {
    for (const notice of notices.entries.value) if (notice.id.startsWith('library-sync:')) notices.remove(notice.id)
    syncActivity = null; syncEpoch = epoch
  }
  if (!sync || sync.status === 'IDLE' || !sync.activity_id) return
  const id = `library-sync:${sync.activity_id}`
  if (syncActivity && syncActivity !== id && notices.entries.value.find(n => n.id === syncActivity)?.status !== 'success') notices.remove(syncActivity)
  syncActivity = id
  const stale = !trusted || Boolean(props.store.error)
  const status = stale ? 'unknown' : sync.status === 'SYNCING' ? 'syncing' : sync.status === 'SYNCED' ? 'success' : 'failed'
  const message = stale ? '曲库同步状态已过期，等待重新读取' : sync.status === 'SYNCING'
    ? `同步中 · 已确认 ${sync.confirmed_count}，待确认 ${sync.pending_count}`
    : sync.status === 'SYNCED' ? '曲库已同步' : '曲库同步失败 · 无法确认 MPD 索引'
  notices.upsert({ id, scope: 'library', description: '曲库同步', status, message,
    read: status === 'success' ? undefined : props.realtime.refresh })
}, { immediate: true })
watch(() => session.notices.value, (records, old = []) => {
  const current = new Set(records.map(record => record.id))
  for (const record of old) if (!current.has(record.id) && record.status !== 'success') notices.remove(record.id)
  for (const record of records) {
    const previous = old.find(n => n.id === record.id)
    if (!previous || JSON.stringify([record.status, record.message, record.busy]) !== JSON.stringify([previous.status, previous.message, previous.busy])) notices.set(record)
  }
}, { immediate: true })
watch(() => tasks?.entries.value, (records, old = []) => {
  const current = new Set((records ?? []).map(record => record.intent.key))
  for (const record of old ?? []) if (!current.has(record.intent.key)) notices.remove(record.intent.key)
  for (const record of records ?? []) {
    const previous = old?.find(n => n.intent.key === record.intent.key)
    if (previous && JSON.stringify([record.state, record.busy, record.readFailed, record.message]) === JSON.stringify([previous.state, previous.busy, previous.readFailed, previous.message])) continue
    const status = record.busy ? record.state === 'pending' ? 'pending' : 'syncing' : record.state === 'unknown' ? 'unknown' : record.readFailed ? 'failed' : record.state === 'confirmed' ? 'success' : record.state
    notices.set({ id: record.intent.key, scope: 'task', description: record.description, status, message: record.busy && record.state === 'confirmed' ? '正在同步状态' : status === 'success' ? '操作已确认 · 已同步' : record.message,
      retry: record.busy ? undefined : record.retry, read: record.busy || status === 'success' ? undefined : record.state === 'retired' ? runtime?.refresh : record.read })
  }
}, { immediate: true, flush: 'sync' })
onMounted(() => props.realtime.start())
onUnmounted(() => { mpdConnection?.dispose(); output?.dispose(); favorites?.stop(); queueUi.dispose(); library?.resources.stop(); playlists?.stop(); tasks?.dispose(); session.dispose(); artwork.dispose(); props.realtime.stop() })
</script>
<template><main class="app-shell"><AppBackground :source="background" /><div class="shell-frame"><AppBar /><div class="shell-content"><slot /></div><BottomNavigation /></div></main></template>
