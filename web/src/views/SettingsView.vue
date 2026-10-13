<script setup lang="ts">
import { computed, inject, onUnmounted, shallowRef, ref, watch } from 'vue'
import MPDConnectionPanel from '../components/settings/MPDConnectionPanel.vue'
import OutputPanel from '../components/player/OutputPanel.vue'
import { playerKey } from '../components/player/playerFacts'
import { playerRuntimeKey } from '../components/player/playerActions'
import { noticeKey } from '../stores/notices'
import { parseMPDInfo } from '../services/resourceWire'
import type { MPDInfo } from '../types/resources'
const player = inject(playerKey)!, runtime = inject(playerRuntimeKey), notices = inject(noticeKey)!
const info = shallowRef<MPDInfo | null>(null), fresh = ref(false)
let serial = 0, alive = true
async function read() {
  const token = ++serial, epoch = player.marker.epoch, generation = player.marker.generation
  if (!runtime || !epoch) return
  fresh.value = false
  notices.set({ id: 'settings-mpd', scope: 'settings', message: '读取 MPD 信息', busy: true })
  try {
    const result = await runtime.api.get('/api/system/mpd', parseMPDInfo)
    if (!alive || token !== serial || epoch !== player.marker.epoch || generation !== player.marker.generation) return
    info.value = result; fresh.value = true
    const errors = Object.entries(result.errors).map(([source, error]) => `${source} · ${error.code} · ${error.message}`)
    if (errors.length) notices.set({ id: 'settings-mpd', scope: 'settings', message: errors.join('；'), read })
    else notices.remove('settings-mpd')
  } catch (error) { if (alive && token === serial && epoch === player.marker.epoch && generation === player.marker.generation) notices.set({ id: 'settings-mpd', scope: 'settings', message: `MPD 信息 · ${String(error)}`, read }) }
}
watch(() => [player.marker.epoch, player.marker.generation, player.marker.trusted], () => { ++serial; fresh.value = false; if (player.marker.trusted) void read() }, { immediate: true })
onUnmounted(() => { alive = false; ++serial; notices.remove('settings-mpd') })
const stats = [{ key: 'songs', label: '歌曲' }, { key: 'albums', label: '专辑' }, { key: 'artists', label: '艺术家' }, { key: 'uptime', label: '运行时间（秒）' }, { key: 'db_playtime', label: '曲库总时长（秒）' }, { key: 'playtime', label: '累计播放（秒）' }, { key: 'db_update', label: '曲库更新时间（Unix秒）' }] as const
const stale = computed(() => !fresh.value || !player.marker.trusted)
</script>
<template>
  <section class="settings-content" aria-label="设置">
    <MPDConnectionPanel />
    <OutputPanel />
    <section class="settings-section" data-mpd-info :data-stale="stale" aria-label="关于 MPD">
      <h2>关于 MPD</h2>
      <dl class="settings-facts"><dt>版本</dt><dd>{{ info?.version ?? '—' }}</dd><dt>版本来源</dt><dd>{{ info?.version_source === 'verified_capability' ? '已验证能力' : '—' }}</dd><dt>连接</dt><dd>{{ info?.connected === true ? '已连接' : info?.connected === false ? '未连接' : '—' }}</dd><template v-for="stat in stats" :key="stat.key"><dt>{{ stat.label }}</dt><dd :data-mpd-stat="stat.key">{{ info?.stats[stat.key] ?? '—' }}</dd></template><dt>曲库更新</dt><dd>{{ info?.database_update_status.updating === true ? '更新中' : info?.database_update_status.updating === false ? '空闲' : '—' }}</dd><dt>更新任务</dt><dd>{{ info?.database_update_status.job_id ?? '—' }}</dd><dt>观察时间</dt><dd>{{ info?.observed_at ?? '—' }}</dd></dl>
    </section>
  </section>
</template>
