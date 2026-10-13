import { computed, shallowRef, ref, watch, type InjectionKey } from 'vue'
import type { PlayerStore } from '../../stores/player'
import type { PlayerRuntime } from '../player/playerActions'
import type { TaskActions } from '../../runtime/taskActions'
import type { createNoticeStore } from '../../stores/notices'
import type { MPDConnection, MPDAddress } from '../../types/resources'
import { parseMPDConnection } from '../../services/resourceWire'
export function createMPDConnection(player: PlayerStore, runtime: PlayerRuntime, tasks: TaskActions, notices: ReturnType<typeof createNoticeStore>) {
  const value = shallowRef<MPDConnection | null>(null), fresh = ref(false)
  let alive = true, serial = 0, activated = false
  const path = '/api/system/mpd/connection'
  async function read() {
    activated = true
    const token = ++serial, epoch = player.marker.epoch, generation = player.marker.generation
    fresh.value = false
    try {
      const result = await runtime.api.get(path, parseMPDConnection)
      if (!alive || token !== serial || epoch !== player.marker.epoch || generation !== player.marker.generation) return
      value.value = result; fresh.value = true
      notices.remove('mpd-connection-read')
      if (result.restart_required) notices.set({ id: 'mpd-connection-restart', scope: 'settings', message: 'MPD 地址已保存 · 服务重启后生效' })
      else notices.remove('mpd-connection-restart')
    } catch (error) {
      if (!alive || token !== serial || epoch !== player.marker.epoch || generation !== player.marker.generation) return
      notices.set({ id: 'mpd-connection-read', scope: 'settings', message: `MPD 地址读取 · ${String(error)}`, read })
      throw error
    }
  }
  const locked = computed(() => !player.writable || !fresh.value || Boolean(runtime.mutationLocked?.()))
  const stop = watch(() => [player.marker.epoch, player.marker.generation, player.marker.trusted], (current, previous) => {
    ++serial; fresh.value = false
    if (previous && current[0] !== previous[0]) { value.value = null; notices.remove('mpd-connection-restart'); notices.remove('mpd-connection-read') }
    if (activated && player.marker.trusted) void read().catch(() => {})
  }, { flush: 'sync' })
  return { value, fresh, locked, read, save(address: MPDAddress) {
    if (locked.value) return Promise.resolve()
    return tasks.run(runtime.api.createIntent('PUT', path, { host: address.host, port: address.port }), parseMPDConnection, read, '保存 MPD 地址（重启后生效）')
  }, dispose() { alive = false; ++serial; stop(); notices.remove('mpd-connection-read'); notices.remove('mpd-connection-restart') } }
}
export type MPDConnectionSettings = ReturnType<typeof createMPDConnection>
export const mpdConnectionKey: InjectionKey<MPDConnectionSettings> = Symbol('mpd-connection')
