<script setup lang="ts">
import FavoriteIcon from '../components/library/FavoriteIcon.vue'
import { computed, inject, nextTick, onMounted, onUnmounted, ref, watch, type DeepReadonly } from 'vue'
import { playerKey } from '../components/player/playerFacts'
import { deriveQueue } from '../components/queue/queuePresentation'
import { createQueueActions } from '../components/queue/queueActions'
import { playerRuntimeKey } from '../components/player/playerActions'
import { playerSessionKey } from '../runtime/playerSession'
import { taskActionsKey } from '../runtime/taskActions'
import QueueOccurrence from '../components/queue/QueueOccurrence.vue'
import { queueUiKey } from '../stores/queueUi'
import { songLibraryKey } from '../stores/library'
import { noticeKey } from '../stores/notices'
import type { Song } from '../types/api'
const player = inject(playerKey)!
const ui = inject(queueUiKey)!
const songs = inject(songLibraryKey)
const notices = inject(noticeKey)!
const runtime = inject(playerRuntimeKey)
const tasks = inject(taskActionsKey)
const session = inject(playerSessionKey)!
const actions = runtime && tasks ? createQueueActions(player, runtime, tasks, () => Boolean(session.actions?.locked)) : null
const queue = computed(() => deriveQueue(player.snapshot, player.writable))
ui.enter()
const view = ref<HTMLElement | null>(null)
const menuId = ref<string | null>(null)
const panel = ref<'clear' | 'save' | null>(null)
const name = ref('')
const dialog = ref<HTMLElement | null>(null)
let opener: HTMLElement | null = null
const menuItem = computed(() => visible.value.find(item => item.queue_item_id === menuId.value))
function openPanel(kind: 'clear' | 'save' | string, event: Event) {
  if (!actions || actions.locked.value || actions.draft.value) return
  opener = event.currentTarget as HTMLElement
  if (kind === 'clear' || kind === 'save') { panel.value = kind; menuId.value = null }
  else { menuId.value = kind; panel.value = null }
  void nextTick(() => dialog.value?.querySelector<HTMLElement>('input:not(:disabled),button:not(:disabled)')?.focus())
}
function closePanel() { menuId.value = null; panel.value = null; opener?.focus() }
function dialogKey(event: KeyboardEvent) {
  if (event.key === 'Escape') { event.preventDefault(); closePanel() }
  if (event.key !== 'Tab') return
  const controls = [...(dialog.value?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled)') ?? [])]
  const first = controls[0], last = controls.at(-1)
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}
function operate(operation: 'next' | 'add' | 'delete') {
  const item = menuItem.value
  if (!item) return
  const title = metadata(item.song_id)?.title || item.song_id
  closePanel()
  if (operation === 'delete') void actions?.remove(item.queue_item_id, title)
  else if (item.position > 0) void actions?.move(item.queue_item_id, operation, title)
}
async function save() {
  if (await actions?.save(name.value)) { name.value = ''; closePanel() }
}

const played = computed(() => queue.value.played.slice(0, ui.expandedCount.value).reverse())
const visible = computed(() => [...played.value, ...(queue.value.current ? [queue.value.current] : []), ...queue.value.next])
watch(() => player.marker.epoch, (epoch, old) => { if (old && epoch !== old) { name.value = ''; closePanel() } })
watch(() => tasks?.entries.value.find(record => record.intent.key === actions?.saveKey.value), record => {
  if (record?.state === 'confirmed' && !record.busy && !record.readFailed) { name.value = ''; if (panel.value === 'save') closePanel() }
})
watch(() => menuItem.value, item => { if (menuId.value && !item) closePanel() })
const scroller = () => view.value?.closest<HTMLElement>('.shell-content')
let entryPositioned = false
async function positionEntry() {
  if (entryPositioned || !queue.value.current) return
  await nextTick()
  const container = scroller()
  if (container) { container.scrollTop = 0; entryPositioned = true }
}
onMounted(() => { void positionEntry() })
watch(() => queue.value.current?.queue_item_id, () => { void positionEntry() })
const dragMoved = ref(false)
const dropHint = ref<{ id: string; after: boolean } | null>(null)
const ghost = ref<{ id: string; x: number; y: number; width: number } | null>(null)
let pointer: { id: number; item: string; x: number; y: number; offsetX: number; offsetY: number; width: number; handle: HTMLElement; active: boolean } | null = null
let hold: ReturnType<typeof setTimeout> | undefined
let frame: number | undefined
function clearDragVisuals() {
  clearTimeout(hold); hold = undefined
  if (frame !== undefined) cancelAnimationFrame(frame)
  frame = undefined; ghost.value = null; dropHint.value = null; dragMoved.value = false
}
function cancelDrag() {
  const captured = pointer; pointer = null
  clearDragVisuals()
  if (captured?.handle.hasPointerCapture?.(captured.id)) captured.handle.releasePointerCapture(captured.id)
  actions?.cancel()
}
function updateDrag() {
  if (!pointer?.active) return
  ghost.value = { id: pointer.item, x: pointer.x - pointer.offsetX, y: pointer.y - pointer.offsetY, width: pointer.width }
  const row = document.elementFromPoint(pointer.x, pointer.y)?.closest<HTMLElement>('[data-queue-item]')
  const id = row?.dataset.queueItem
  const target = queue.value.next.find(item => item.queue_item_id === id)
  // Invalid release must never reuse a previously valid insertion target.
  dragMoved.value = false; dropHint.value = null
  if (!row || !target || id === pointer.item) return
  const bounds = row.getBoundingClientRect()
  const after = pointer.y > bounds.top + bounds.height / 2
  const pending = [...(player.snapshot?.queue.items ?? [])].filter(item => item.position > 0 && item.queue_item_id !== pointer?.item).sort((a, b) => a.position - b.position)
  const index = pending.findIndex(item => item.queue_item_id === id)
  const before = after ? pending[index + 1]?.queue_item_id ?? null : target.queue_item_id
  if (actions?.target(before)) { dragMoved.value = true; dropHint.value = { id: target.queue_item_id, after } }
}
function scrollDrag() {
  if (!pointer?.active) return
  const container = scroller()
  if (!container) return
  const bounds = container.getBoundingClientRect()
  if (bounds.height <= 0) return
  const edge = Math.min(56, bounds.height / 4)
  const distance = pointer.y < bounds.top + edge ? pointer.y - bounds.top - edge
    : pointer.y > bounds.bottom - edge ? pointer.y - bounds.bottom + edge : 0
  const speed = Math.max(-12, Math.min(12, distance / edge * 12))
  if (speed && pointer.x >= bounds.left && pointer.x <= bounds.right) {
    container.scrollTop += speed
    updateDrag()
  }
  frame = requestAnimationFrame(scrollDrag)
}
function startDrag(id: string, event: PointerEvent) {
  if (event.button !== 0 || !actions || actions.locked.value) return
  cancelDrag(); suppressClick = true; pullStart = null
  const handle = event.currentTarget as HTMLElement
  const bounds = handle.closest<HTMLElement>('[data-queue-item]')!.getBoundingClientRect()
  pointer = { id: event.pointerId, item: id, x: event.clientX, y: event.clientY,
    offsetX: event.clientX - bounds.left, offsetY: event.clientY - bounds.top, width: bounds.width, handle, active: false }
  handle.setPointerCapture?.(event.pointerId)
  // The dedicated handle owns this gesture; small touch drift does not abort it.
  hold = setTimeout(() => {
    if (pointer && actions.begin(id)) {
      pointer.active = true; updateDrag(); scrollDrag()
    }
  }, 230)
}
function moveDrag(event: PointerEvent) {
  if (!pointer || pointer.id !== event.pointerId) return
  pointer.x = event.clientX; pointer.y = event.clientY
  if (!pointer.active) return
  event.preventDefault(); updateDrag()
}
function endDrag(event: PointerEvent) {
  if (!pointer || pointer.id !== event.pointerId) return
  pointer.x = event.clientX; pointer.y = event.clientY
  if (pointer.active) updateDrag()
  const captured = pointer; const valid = captured.active && dragMoved.value
  pointer = null; clearDragVisuals()
  if (valid) void actions?.drop(metadata(player.snapshot?.queue.items.find(item => item.queue_item_id === captured.item)?.song_id ?? '')?.title || captured.item)
  else actions?.cancel()
  if (captured.handle.hasPointerCapture?.(captured.id)) captured.handle.releasePointerCapture(captured.id)
}
watch(() => actions?.draft.value, (draft, old) => { if (!draft && old && pointer?.active) cancelDrag() }, { flush: 'sync' })
function press(event: PointerEvent) {
  if ((event.target as HTMLElement)?.closest('.queue-play')) suppressClick = false
}
function play(id: string, songId: string) {
  if (suppressClick) { suppressClick = false; return }
  void actions?.play(id, metadata(songId)?.title || songId)
}
let pullStart: { x: number; y: number } | null = null
let pullDistance = 0
let suppressClick = false
function startPull(event: TouchEvent) {
  if (pointer || (event.target as HTMLElement)?.closest('.queue-drag')) { pullStart = null; return }
  suppressClick = false
  const touch = event.touches[0]
  pullStart = touch && event.touches.length === 1 && (scroller()?.scrollTop ?? 0) <= 0 ? { x: touch.clientX, y: touch.clientY } : null
  pullDistance = 0
}
function revealDistance(distance: number) {
  pullDistance += distance
  while (pullDistance >= 64 && ui.expandedCount.value < queue.value.played.length) { ui.reveal(); pullDistance -= 64 }
}
function movePull(event: TouchEvent) {
  const touch = event.touches[0]
  if (!pullStart || !touch || event.touches.length !== 1) return
  const distance = touch.clientY - pullStart.y
  if (distance <= 0 || Math.abs(touch.clientX - pullStart.x) > distance || ui.expandedCount.value >= queue.value.played.length) { pullStart = null; return }
  event.preventDefault(); suppressClick = true
  revealDistance(distance); pullStart = { x: touch.clientX, y: touch.clientY }
}
function wheel(event: WheelEvent) {
  if ((scroller()?.scrollTop ?? 0) > 0 || event.deltaY >= 0 || ui.expandedCount.value >= queue.value.played.length) return
  event.preventDefault(); revealDistance(-event.deltaY)
}
const ids = computed(() => [...new Set([...(queue.value.current ? [queue.value.current] : []), ...played.value, ...queue.value.next].map(item => item.song_id))])
const path = (id: string) => `/api/library/songs/${encodeURIComponent(id)}`
function metadata(id: string): DeepReadonly<Song> | null {
  const data = songs?.entry(path(id)).data
  return data?.song_id === id ? data : null
}
let request = 0
const noticeIds = new Set<string>()
async function readMetadata() {
  const serial = ++request
  for (const id of noticeIds) notices.remove(id)
  noticeIds.clear()
  if (!songs || !player.marker.epoch || !ids.value.length) return
  const identity = player.marker.epoch
  await Promise.all(ids.value.map(async id => {
    const noticeId = `queue-metadata:${id}`
    noticeIds.add(noticeId)
    if (!songs.entry(path(id)).fresh) notices.set({ id: noticeId, scope: 'queue', message: `读取歌曲 ${id}`, busy: true })
    try {
      await songs.read(path(id))
      if (serial !== request || identity !== player.marker.epoch) return
      notices.remove(noticeId)
      const data = metadata(id)
      if (data && data.availability_status !== 'AVAILABLE') notices.set({ id: noticeId, scope: 'queue', message: `${data.title || id} · ${data.availability_status}`, read: readMetadata })
    } catch (error) {
      if (serial !== request || identity !== player.marker.epoch) return
      notices.set({ id: noticeId, scope: 'queue', message: `歌曲 ${id} · ${error instanceof Error ? error.message : String(error)}`, read: readMetadata })
    }
  }))
}
watch(() => JSON.stringify([ids.value, player.marker.epoch, player.marker.revisions.library, player.marker.generation, player.marker.trusted]), () => { void readMetadata() }, { immediate: true })
onUnmounted(() => { cancelDrag(); actions?.dispose(); ++request; for (const id of noticeIds) notices.remove(id) })
</script>
<template>
  <div ref="view" class="queue-view" @pointerdown.capture="press" @touchstart="startPull" @touchmove="movePull" @touchend="pullStart = null" @touchcancel="pullStart = null" @wheel="wheel">
    <ul class="queue-list"><QueueOccurrence v-for="item in visible" :key="item.queue_item_id" :item="item" :song="metadata(item.song_id)" :icon="item.position === 0 ? queue.currentIcon : null" :disabled="!actions || actions.locked.value" :menu-open="menuId === item.queue_item_id" @more="openPanel(item.queue_item_id, $event)" :data-dragging="actions?.draft.value?.id === item.queue_item_id" :data-drop="dropHint?.id === item.queue_item_id && !dropHint.after" :data-drop-after="dropHint?.id === item.queue_item_id && dropHint.after" @play="play(item.queue_item_id, item.song_id)" @drag-start="startDrag(item.queue_item_id, $event)" @drag-move="moveDrag" @drag-end="endDrag" @drag-cancel="cancelDrag" /></ul>
    <div v-if="ghost" class="queue-drag-ghost" aria-hidden="true" :style="{ width: `${ghost.width}px`, transform: `translate3d(${ghost.x}px, ${ghost.y}px, 0)` }"><span class="queue-title">{{ metadata(player.snapshot?.queue.items.find(item => item.queue_item_id === ghost?.id)?.song_id ?? '')?.title || '—' }}</span><span class="queue-artist">{{ metadata(player.snapshot?.queue.items.find(item => item.queue_item_id === ghost?.id)?.song_id ?? '')?.artists.join(' / ') || '—' }}</span></div>
    <div class="queue-tools"><button data-queue-clear :disabled="!actions || actions.locked.value" @click="openPanel('clear', $event)">清空待播</button><button data-queue-save :disabled="!actions || actions.locked.value" @click="openPanel('save', $event)">保存为 Playlist</button></div>
    <div v-if="panel || menuItem" class="queue-dialog-backdrop" :class="{ 'queue-song-backdrop': menuItem }" @click.self="closePanel">
      <section ref="dialog" class="queue-dialog" :class="{ 'queue-song-menu': menuItem }" role="dialog" aria-modal="true" :aria-label="panel === 'save' ? '保存为 Playlist' : panel === 'clear' ? '清空待播' : '歌曲操作'" @keydown="dialogKey">
        <template v-if="menuItem">
          <div class="song-details"><strong>{{ metadata(menuItem.song_id)?.title || menuItem.song_id }}</strong><span>{{ metadata(menuItem.song_id)?.artists.join(' / ') || '—' }}</span><span>{{ metadata(menuItem.song_id)?.album || '—' }}</span><span v-if="metadata(menuItem.song_id) && metadata(menuItem.song_id)?.availability_status !== 'AVAILABLE'">{{ metadata(menuItem.song_id)?.availability_status }}</span></div>
          <button v-if="menuItem.position > 0" data-queue-operation="next" :disabled="!actions || actions.locked.value" @click="operate('next')">移为下一首</button><button v-if="menuItem.position > 0" data-queue-operation="add" :disabled="!actions || actions.locked.value" @click="operate('add')">移到队尾</button><button data-queue-operation="delete" :disabled="!actions || actions.locked.value" @click="operate('delete')">删除此条目</button><FavoriteIcon :song-id="menuItem.song_id" menu /></template>
        <template v-else-if="panel === 'clear'"><p>清空全部待播，保留当前与已播放项。AutoPlay 可能补充候选。</p><button data-confirm-clear :disabled="!actions || actions.locked.value" @click="closePanel(); actions?.clear()">确认清空待播</button></template>
        <form v-else data-save-form @submit.prevent="save"><label for="queue-playlist-name">Playlist 名称</label><input id="queue-playlist-name" v-model="name" aria-label="Playlist 名称" autocomplete="off" :disabled="!actions || actions.locked.value" /><p>保存提交时全部待播，包含隐藏候选，不包含当前与已播放项。重复歌曲会拒绝保存。</p><button type="submit" :disabled="!name.trim() || !actions || actions.locked.value">保存</button></form>
        <button data-dialog-cancel @click="closePanel">取消</button>
      </section>
    </div>
    <p v-if="!visible.length" class="queue-empty">—</p>
  </div>
</template>
