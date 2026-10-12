<script setup lang="ts">
import { computed, inject, ref, watch, onMounted } from 'vue'
import { mpdConnectionKey } from './mpdConnection'
import type { MPDAddress } from '../../types/resources'
import { playerKey } from '../player/playerFacts'
const connection = inject(mpdConnectionKey, null), player = inject(playerKey)!
const host = ref(''), port = ref('6600'), edited = ref(false)
watch(() => connection?.value.value, value => { if (value && !edited.value) { host.value = (value.saved ?? value.active).host; port.value = String((value.saved ?? value.active).port) } }, { immediate: true })
watch(() => player.marker.epoch, () => { edited.value = false; host.value = ''; port.value = '6600' })
onMounted(() => { void connection?.read().catch(() => {}) })
const valid = computed(() => Boolean(host.value.trim()) && !/[\s/]/.test(host.value) && /^\d+$/.test(port.value) && Number(port.value) >= 1 && Number(port.value) <= 65535)
function formatAddress(address: MPDAddress) { return `${address.host.includes(':') ? `[${address.host}]` : address.host}:${address.port}` }
function save() { if (valid.value) void connection?.save({ host: host.value, port: Number(port.value) }) }
</script>
<template><section class="settings-section" aria-label="MPD 接入" :data-stale="!connection?.fresh.value || !player.marker.trusted">
  <h2>MPD 接入</h2>
  <dl class="settings-facts"><dt>{{ connection?.fresh.value && player.marker.trusted ? '当前地址' : '最后确认地址（过期）' }}</dt><dd data-mpd-active>{{ connection?.value.value ? formatAddress(connection.value.value.active) : '—' }}</dd><dt>已保存地址</dt><dd data-mpd-saved>{{ connection?.value.value?.saved ? formatAddress(connection.value.value.saved) : '—' }}</dd></dl>
  <form class="settings-form" @submit.prevent="save"><div class="mpd-address-row" role="group" aria-label="MPD 地址"><input class="mpd-host-input" name="mpd-host" aria-label="主机/IP" v-model="host" autocomplete="off" autocapitalize="none" spellcheck="false" @input="edited = true" /><span class="mpd-address-separator" aria-hidden="true">:</span><input class="mpd-port-input" name="mpd-port" aria-label="端口" v-model="port" inputmode="numeric" size="4" @input="edited = true" /></div><button data-save-mpd :disabled="!connection || connection.locked.value || !valid">保存（重启后生效）</button></form>
</section></template>
