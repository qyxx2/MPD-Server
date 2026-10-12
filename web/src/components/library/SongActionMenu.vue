<script setup lang="ts">
import FavoriteIcon from './FavoriteIcon.vue'
import { nextTick, onMounted, ref } from 'vue'
import type { DeepReadonly } from 'vue'
import type { Song } from '../../types/api'
defineProps<{ song: DeepReadonly<Song>; disabled: boolean }>()
const emit = defineEmits<{ action: [operation: 'now' | 'next' | 'add']; close: [] }>()
const panel = ref<HTMLElement | null>(null)
onMounted(() => { void nextTick(() => (panel.value?.querySelector<HTMLElement>('button:not(:disabled)') ?? panel.value)?.focus()) })
function key(event: KeyboardEvent) {
  if (event.key === 'Escape') { event.preventDefault(); emit('close') }
  if (event.key !== 'Tab') return
  const buttons = [...(panel.value?.querySelectorAll<HTMLElement>('button:not(:disabled)') ?? [])]
  const first = buttons[0], last = buttons.at(-1)
  if (!first) { event.preventDefault(); return }
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}
</script>
<template>
  <div class="song-menu-backdrop" @click.self="emit('close')">
    <section ref="panel" class="song-menu" role="dialog" aria-modal="true" :aria-label="song.title" tabindex="-1" @keydown="key">
      <div class="song-details"><strong>{{ song.title }}</strong><span>{{ song.artists.join(' / ') || '—' }}</span><span>{{ song.album || '—' }}</span><span v-if="song.availability_status !== 'AVAILABLE'">{{ song.availability_status }}</span></div>
      <FavoriteIcon :song-id="song.song_id" menu />
      <button data-song-action="now" :disabled="disabled" @click="emit('action', 'now')">立即播放</button>
      <button data-song-action="next" :disabled="disabled" @click="emit('action', 'next')">下一首播放</button>
      <button data-song-action="add" :disabled="disabled" @click="emit('action', 'add')">加入队尾</button>
    </section>
  </div>
</template>
