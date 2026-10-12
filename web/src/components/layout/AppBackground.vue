<script setup lang="ts">
import { inject } from 'vue'
import { artworkKey } from '../../stores/artwork'
defineProps<{ source: string | null }>()
const artwork = inject(artworkKey)!
function imageError(event: Event) { const image = event.currentTarget; if (image instanceof HTMLImageElement) { const url = image.getAttribute('src'); if (url) artwork.fail(url) } }
</script>
<template><div class="app-background" aria-hidden="true"><img v-if="source" :key="source" :src="source" alt="" @error="imageError"><div v-if="source" class="background-shade" /></div></template>
<style scoped>
.app-background { position: fixed; inset: 0; z-index: -1; pointer-events: none; overflow: hidden; background: radial-gradient(ellipse at 5% 0%, var(--ambient-background), transparent 60%), var(--page-background); }
.app-background img { position: absolute; inset: -4rem; width: calc(100% + 8rem); height: calc(100% + 8rem); object-fit: cover; filter: blur(28px); }
.background-shade { position: absolute; inset: 0; background: var(--artwork-shade); }
@supports not (filter: blur(1px)) { .app-background img, .background-shade { display: none; } }
</style>
