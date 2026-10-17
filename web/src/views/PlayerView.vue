<script setup lang="ts">
import { inject } from 'vue'
import { layoutModeKey } from '../components/layout/layoutMode'
import PlayerPanel from '../components/player/PlayerPanel.vue'
import PlayerLyrics from '../components/player/PlayerLyrics.vue'
const layout = inject(layoutModeKey)!
</script>
<template><PlayerLyrics v-if="layout.mode.value === 'landscape'" :show-artwork-return="false" /><PlayerPanel v-else presentation="portrait" /></template>
