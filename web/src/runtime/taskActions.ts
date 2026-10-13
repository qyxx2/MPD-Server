import { computed, shallowReactive, watch, type InjectionKey } from 'vue'
import type { createApiClient } from '../services/api'
import type { PlayerStore } from '../stores/player'
import { ApiError, type MutationIntent } from '../types/api'
export function createTaskActions(options: { api: ReturnType<typeof createApiClient>; player: PlayerStore; refresh(): Promise<void> }) {
  type Record = { intent: MutationIntent; description: string; epoch: string | null; state: 'pending' | 'unknown' | 'confirmed' | 'failed' | 'retired'; message: string; busy: boolean; readFailed: boolean; retry?: () => Promise<void>; read: () => Promise<void> }
  const records = shallowReactive(new Map<string, Readonly<Record>>())
  const jobs = new Map<string, { decode: (value: unknown) => unknown; read: () => Promise<void> }>()
  let alive = true
  const set = (key: string, change: Partial<Record>) => {
    const record = records.get(key)
    if (alive && record) records.set(key, Object.freeze({ ...record, ...change }))
  }
  async function read(key: string) {
    const record = records.get(key), job = jobs.get(key)
    if (!record || !job || !alive || record.epoch !== options.player.marker.epoch) return
    set(key, { busy: true })
    try {
      await options.refresh()
      if (!alive || record.epoch !== options.player.marker.epoch) return
      await job.read()
      if (!alive || record.epoch !== options.player.marker.epoch) return
      if (options.player.error) throw options.player.error
      set(key, { message: record.state === 'confirmed' ? '操作已确认' : record.message, busy: false, readFailed: false })
    } catch { if (record.epoch !== options.player.marker.epoch) return; set(key, { readFailed: true, busy: false }) }
  }
  async function send(key: string) {
    const record = records.get(key), job = jobs.get(key)
    if (!record || !job || !alive) return
    set(key, { state: 'pending', message: '正在处理操作', busy: true, readFailed: false, retry: undefined })
    try {
      await options.api.send(record.intent, job.decode)
      if (!alive || record.epoch !== options.player.marker.epoch) return
      set(key, { state: 'confirmed', message: '操作已确认', busy: true, retry: undefined })
      await read(key)
    } catch (error) {
      if (!alive || record.epoch !== options.player.marker.epoch) return
      const unknown = !(error instanceof ApiError) || error.kind !== 'http'
      set(key, { state: unknown ? 'unknown' : 'failed', busy: false,
        message: `${unknown ? '结果未知 · ' : ''}${error instanceof ApiError ? `${error.code} · ${error.message}` : String(error)}`,
        retry: unknown ? () => retry(key) : undefined })
      if (!unknown) await read(key)
    }
  }
  function retry(key: string): Promise<void> {
    const record = records.get(key)
    if (!alive || !options.player.writable || record?.state !== 'unknown' || record.busy || record.epoch !== options.player.marker.epoch) return Promise.resolve()
    return send(key)
  }
  const stop = watch(() => options.player.marker.epoch, (epoch, old) => {
    if (old === null || epoch === old) return
    for (const [key, record] of records) if (record.epoch !== epoch) {
      if (record.state !== 'confirmed' || record.busy || record.readFailed)
        set(key, { state: 'retired', message: '服务会话已改变 · 旧操作结果需重新读取', busy: false, retry: undefined })
      else records.delete(key)
      jobs.delete(key)
    }
  }, { flush: 'sync' })
  return {
    entries: computed(() => [...records.values()].map(record => ({ ...record, message: record.message + (record.readFailed ? ' · 读取失败，保留最后事实' : '') }))),
    run<T>(intent: MutationIntent, decode: (value: unknown) => T, resourceRead: () => Promise<void>, description = intent.method === 'DELETE' ? '删除条目' : intent.path.includes('/scan') ? '扫描曲库' : intent.path.includes('/queue') ? '更新队列' : intent.path.includes('/playlists') ? '更新歌单' : '保存设置'): Promise<void> {
      if (!alive || !options.player.writable || records.has(intent.key)) return Promise.resolve()
      jobs.set(intent.key, { decode, read: resourceRead })
      records.set(intent.key, Object.freeze({ intent, description, epoch: options.player.marker.epoch, state: 'pending', message: '正在处理操作', busy: true, readFailed: false, read: () => read(intent.key) }))
      return send(intent.key)
    },
    retry,
    dispose() { alive = false; stop(); jobs.clear() },
  }
}
export type TaskActions = ReturnType<typeof createTaskActions>
export const taskActionsKey: InjectionKey<TaskActions> = Symbol('task-actions')
