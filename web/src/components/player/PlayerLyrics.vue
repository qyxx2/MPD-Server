<script setup lang="ts">
import { inject } from 'vue'
import LyricsStage from './LyricsStage.vue'
import { playerKey } from './playerFacts'
import { playerSessionKey } from '../../runtime/playerSession'
defineProps<{ showArtworkReturn: boolean }>()
const store = inject(playerKey)!
const { actions, facts, media, mediaMode, artworkIdentity, displayPosition, seekLyric } = inject(playerSessionKey)!
</script>
<template><LyricsStage :show-artwork-return="showArtworkReturn" :song="media.song" :position="facts.song ? displayPosition : null" :duration="facts.duration" :seek-enabled="Boolean(actions?.facts.value.capabilities.seek && !actions.locked)" :resource-scope="`${store.marker.epoch}/${store.marker.revisions.library}/${store.marker.generation}/${artworkIdentity}`" @show-artwork="mediaMode = 'artwork'" @seek="seekLyric" /></template>
