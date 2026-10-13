<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import FavoriteIcon from './FavoriteIcon.vue'
defineProps<{ songId: string }>()
const emit = defineEmits<{ close: [] }>()
const panel = ref<HTMLElement | null>(null)
onMounted(() => { void nextTick(() => (panel.value?.querySelector<HTMLElement>('button:not(:disabled)') ?? panel.value)?.focus()) })
function key(event: KeyboardEvent) {
  if (event.key === 'Escape') { event.preventDefault(); emit('close') }
  if (event.key !== 'Tab') return
  const buttons = [...(panel.value?.querySelectorAll<HTMLElement>('button:not(:disabled)') ?? [])]
  const first = buttons[0], last = buttons.at(-1)
  if (!first) { event.preventDefault(); return }
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
}
</script>
<template><div class="song-menu-backdrop" @click.self="emit('close')"><section ref="panel" class="song-menu" role="dialog" aria-modal="true" :aria-label="songId" tabindex="-1" @keydown="key"><FavoriteIcon :song-id="songId" menu /><button @click="emit('close')">关闭</button></section></div></template>
