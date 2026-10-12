<script setup lang="ts">
import { computed, inject } from 'vue'
import type { PlayerFacts } from './playerFacts'
import { artworkKey } from '../../stores/artwork'
const props = defineProps<{ song: PlayerFacts['song']; resourceScope: string }>()
const artwork = inject(artworkKey)!
const source = computed(() => props.song ? artwork.decodedUrl : null)
function imageError(event: Event) {
  const image = event.currentTarget
  if (image instanceof HTMLImageElement && image.getAttribute('src')) artwork.fail(image.getAttribute('src')!)
}
</script>
<template>
  <div class="artwork-stage">
    <img v-if="source" :key="source" :src="source" :alt="`${song?.title || '歌曲'}封面`" @error="imageError">
    <div v-else class="artwork-placeholder" data-testid="artwork-placeholder" :aria-label="artwork.status || '无封面'"><span aria-hidden="true" class="record-mark">♪</span></div>
  </div>
</template>
