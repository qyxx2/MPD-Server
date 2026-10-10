<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { PlayerFacts } from './playerFacts'
import { activeCue, parseLyrics } from './lyrics'
const props = defineProps<{ song: PlayerFacts['song']; position: number | null; resourceScope: string; seekEnabled?: boolean; duration?: number | null }>()
const emit = defineEmits<{ showArtwork: []; seek: [seconds: number] }>()
const document = computed(() => parseLyrics(props.song?.lyrics || '', props.song?.lyrics_format || null))
const active = computed(() => activeCue(document.value, props.position))
const following = ref(true)
const content = ref<HTMLElement | null>(null)
let returnTimer: ReturnType<typeof setTimeout> | undefined
let gesture: { x: number; y: number; started: number; dragged: boolean } | null = null
let suppressClick = false
function clearReturn() { clearTimeout(returnTimer); returnTimer = undefined }
function selected() { return window.getSelection()?.isCollapsed === false }
function scheduleReturn() {
  clearReturn()
  if (!document.value.synchronized || following.value || gesture || selected()) return
  returnTimer = setTimeout(() => { returnTimer = undefined; if (!selected()) { following.value = true; void locate() } }, 3000)
}
async function locate() {
  await nextTick()
  if (!following.value || !active.value.length) return
  const cue = content.value?.querySelector<HTMLElement>('[aria-current="true"]')
  if (!cue || !content.value) return
  const reduced = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
  content.value.scrollTo?.({ top: Math.max(0, cue.offsetTop - content.value.clientHeight / 2 + cue.offsetHeight / 2), behavior: reduced ? 'auto' : 'smooth' })
}
function manual() { following.value = false; scheduleReturn() }
function pointerStart(event: PointerEvent) {
  gesture = { x: event.clientX, y: event.clientY, started: Date.now(), dragged: false }
  suppressClick = false; manual()
}
function pointerMove(event: PointerEvent) {
  if (gesture && Math.hypot(event.clientX - gesture.x, event.clientY - gesture.y) > 8) gesture.dragged = true
}
function pointerEnd(event: PointerEvent) {
  if (!gesture) return
  suppressClick = event.type === 'pointercancel' || Boolean(gesture && (gesture.dragged || Date.now() - gesture.started >= 500))
  gesture = null; scheduleReturn()
}
function scrolled() { if (gesture) gesture.dragged = true; if (!following.value) scheduleReturn() }
function keyboard(event: KeyboardEvent) { if (['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(event.key)) manual() }
function cuePosition(seconds: number) { return seconds - document.value.offsetMs / 1000 }
function canSeek(seconds: number) { const target = cuePosition(seconds); return props.seekEnabled && props.duration != null && target >= 0 && target <= props.duration }
function activate(seconds: number, event: MouseEvent | KeyboardEvent) {
  if (event.type === 'click' && suppressClick) { suppressClick = false; return }
  if (!canSeek(seconds) || selected()) return
  clearReturn(); following.value = true
  emit('seek', cuePosition(seconds))
}
function selectionChanged() { if (!following.value) scheduleReturn() }
onMounted(() => { window.document.addEventListener('selectionchange', selectionChanged); window.addEventListener('pointerup', pointerEnd); window.addEventListener('pointercancel', pointerEnd) })
onUnmounted(() => { clearReturn(); window.document.removeEventListener('selectionchange', selectionChanged); window.removeEventListener('pointerup', pointerEnd); window.removeEventListener('pointercancel', pointerEnd) })
watch(() => JSON.stringify([props.resourceScope, props.song?.song_id, props.song?.file_uri, props.song?.lyrics, props.song?.lyrics_format]), () => { clearReturn(); suppressClick = Boolean(gesture); gesture = null; following.value = true; void locate() }, { immediate: true })
watch(() => active.value.join(','), () => { void locate() })
</script>
<template>
  <section class="lyrics-stage" aria-label="歌词">
    <div class="lyrics-header">
      <button type="button" class="artwork-return" aria-label="显示封面" @click="emit('showArtwork')">
        <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M4 4l5 5M9 4v5H4M20 20l-5-5M15 20v-5h5" /></svg>
      </button>
    </div>
    <div ref="content" class="lyrics-content" aria-label="歌词内容" tabindex="0" @wheel.passive="manual" @pointerdown="pointerStart" @pointermove="pointerMove" @pointerup="pointerEnd" @pointercancel="pointerEnd" @scroll.passive="scrolled" @keydown="keyboard">
      <template v-if="document.synchronized">
        <p v-for="(cue, index) in document.cues" :key="index" class="lyric-cue" :class="{ 'seekable': canSeek(cue.seconds) }" :role="canSeek(cue.seconds) ? 'button' : undefined" :tabindex="canSeek(cue.seconds) ? 0 : undefined" :aria-label="canSeek(cue.seconds) ? `跳转到歌词：${cue.text}` : undefined" :aria-current="active.includes(index) ? 'true' : undefined" @click="activate(cue.seconds, $event)" @keydown.enter.prevent.stop="activate(cue.seconds, $event)" @keydown.space.prevent.stop="activate(cue.seconds, $event)">{{ cue.text || '　' }}</p>
        <p v-for="(note, index) in document.notes" :key="`note-${index}`" class="lyric-note">{{ note }}</p>
      </template>
      <p v-else class="lyrics-plain">{{ document.text }}</p>
    </div>
  </section>
</template>
<style scoped>
.lyrics-stage { height: 100%; min-height: 0; display: flex; flex-direction: column; position: relative; background: transparent; padding: .25rem 3.25rem .25rem .5rem; overflow: hidden; }
.lyrics-header { flex: none; display: flex; align-items: flex-start; gap: .5rem; }
.artwork-return { position: absolute; right: 0; top: 0; display: grid; place-items: center; border: 0; border-radius: var(--radius-small); background: transparent; color: var(--text-secondary); cursor: pointer; }
.lyrics-content { min-height: 0; flex: 1; overflow-y: auto; overscroll-behavior: contain; position: relative; user-select: text; -webkit-user-select: text; touch-action: pan-y; overflow-wrap: anywhere; }
.lyric-cue { color: var(--text-secondary); padding: .65rem .25rem; line-height: 1.7; white-space: pre-wrap; }
.lyric-cue.seekable { cursor: pointer; }
.lyric-cue[aria-current="true"] { color: var(--accent); font-weight: 650; background: rgba(49, 183, 226, .1); border-radius: .5rem; }
.lyrics-plain, .lyric-note { white-space: pre-wrap; line-height: 1.8; color: var(--text-secondary); }
</style>
