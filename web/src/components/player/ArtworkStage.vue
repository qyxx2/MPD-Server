<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import type { PlayerFacts } from './playerFacts'
const props = defineProps<{ song: PlayerFacts['song']; resourceScope: string }>()
const emit = defineEmits<{ notice: [message: string] }>()
const source = ref<string | null>(null)
const status = ref('无封面')
let generation = 0
let abort: AbortController | null = null
function clear() {
  abort?.abort(); abort = null
  if (source.value) URL.revokeObjectURL(source.value)
  source.value = null
}
watch(() => JSON.stringify([props.resourceScope, props.song?.song_id, props.song?.file_uri, props.song?.artwork]), async () => {
  const id = ++generation
  clear()
  const song = props.song
  if (!song?.song_id || !song.artwork) { status.value = '无封面'; return }
  status.value = '封面加载中'
  abort = new AbortController()
  try {
    const response = await fetch(`/api/library/songs/${encodeURIComponent(song.song_id)}/artwork`, { signal: abort.signal, cache: 'no-store' })
    if (id !== generation) return
    if (response.status === 404) { status.value = '无封面'; return }
    if (!response.ok) throw new Error('Artwork read failed')
    const blob = await response.blob()
    if (id !== generation) return
    source.value = URL.createObjectURL(blob)
  } catch {
    if (id === generation) status.value = '封面读取失败'
  }
}, { immediate: true })
watch(status, value => emit('notice', value === '无封面' ? '' : value), { immediate: true })
function imageResult(event: Event, failed: boolean) {
  const image = event.currentTarget
  if (!source.value || !(image instanceof HTMLImageElement) || image.getAttribute('src') !== source.value) return
  if (failed) { clear(); status.value = '封面读取失败' }
  else status.value = ''
}
onUnmounted(() => { ++generation; clear() })
</script>
<template>
  <div class="artwork-stage">
    <img v-if="source" :key="source" :src="source" :alt="`${song?.title || '歌曲'}封面`" @load="imageResult($event, false)" @error="imageResult($event, true)">
    <div v-else class="artwork-placeholder" data-testid="artwork-placeholder" :aria-label="status"><span aria-hidden="true" class="record-mark">♪</span></div>
  </div>
</template>
