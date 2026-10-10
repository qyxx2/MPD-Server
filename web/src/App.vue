<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppShell from './components/layout/AppShell.vue'
import { createApiClient } from './services/api'
import { createRealtimeClient } from './services/realtime'
import { createPlayerStore } from './stores/player'
const acceptanceLabel = import.meta.env.VITE_ACCEPTANCE_LABEL
if (acceptanceLabel) document.title = `MPD-Server · ${acceptanceLabel}`
const store = createPlayerStore()
const api = createApiClient({ origin: window.location.origin, fetch: window.fetch.bind(window) })
const realtime = createRealtimeClient({ api, store, socketFactory: url => new WebSocket(url), clock: { setTimeout, clearTimeout, random: Math.random } })
</script>
<template><AppShell :store="store" :realtime="realtime" :api="api"><RouterView /></AppShell></template>
