<script setup lang="ts">
import { onMounted, onUnmounted, provide } from 'vue'
import type { PlayerStore } from '../../stores/player'
import type { PlayerRuntime } from '../player/playerActions'
import { playerRuntimeKey } from '../player/playerActions'
import { playerKey } from '../player/playerFacts'
const props = defineProps<{ store: PlayerStore; realtime: { start(): void; stop(): void; refresh?(): Promise<void> }; api?: PlayerRuntime['api'] }>()
provide(playerKey, props.store)
if (props.api && props.realtime.refresh) provide(playerRuntimeKey, { api: props.api, refresh: () => props.realtime.refresh!() })
onMounted(() => props.realtime.start())
onUnmounted(() => props.realtime.stop())
</script>
<template><main class="app-shell"><slot /></main></template>
