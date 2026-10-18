import { computed, shallowReactive, type InjectionKey } from 'vue'
import { activityDiagnostic, shortActivityCopy } from '../services/diagnostics'
export type ActivityStatus = 'pending' | 'syncing' | 'unknown' | 'failed' | 'retired' | 'success' | 'info'
export interface Notice {
  id: string; scope: string; message: string; busy?: boolean; level?: 'warning' | 'info'
  status?: ActivityStatus; description?: string; resource?: string; updatedOrder?: number
  retry?: () => Promise<void>; read?: () => Promise<void>
}
export type Activity = Readonly<Notice & { status: ActivityStatus; description: string; resource: string; updatedOrder: number }>
export const unresolvedActivity = (notice: Activity) => notice.level === 'warning' || ['pending', 'syncing', 'unknown', 'failed', 'retired'].includes(notice.status)
export function createNoticeStore() {
  const records = shallowReactive(new Map<string, Activity>())
  const correlations = new Map<string, number>()
  let order = 0, correlation = 0
  const sorted = () => [...records.values()].sort((a, b) => b.updatedOrder - a.updatedOrder || a.id.localeCompare(b.id))
  const recent = (max = 5) => sorted().slice(0, Math.max(0, Math.min(5, max)))
  function set(notice: Notice) {
    const previous = records.get(notice.id)
    const status = notice.status ?? (notice.busy ? 'pending' : notice.level === 'info' ? 'info' : notice.retry || notice.read || /失败|异常|中断|不可读|缺失|未知|未确认|需明确|只读|无法|超时/.test(notice.message) ? 'failed' : 'info')
    const changed = !previous || status !== previous.status || (notice.level === 'warning') !== (previous.level === 'warning')
    const value: Activity = Object.freeze({ ...notice, status, description: shortActivityCopy(notice.description ?? ''), resource: shortActivityCopy(notice.resource ?? ''), message: shortActivityCopy(notice.message),
      busy: status === 'pending' || status === 'syncing', updatedOrder: changed ? ++order : previous.updatedOrder,
      retry: status === 'unknown' ? notice.retry : undefined, read: status === 'success' || status === 'info' ? undefined : notice.read })
    if (changed) {
      if (!correlations.has(notice.id)) correlations.set(notice.id, ++correlation)
      activityDiagnostic(correlations.get(notice.id)!, notice.scope, status)
    }
    records.set(notice.id, value)
    // Completed display history is bounded; unresolved owners stay elsewhere.
    const completed = sorted().filter(n => n.status === 'success' && !unresolvedActivity(n))
    for (const old of completed.slice(5)) { records.delete(old.id); correlations.delete(old.id) }
  }
  const remove = (id: string) => { records.delete(id); correlations.delete(id) }
  return {
    entries: computed(() => [...records.values()]), set, upsert: set, remove, recent,
    summary: computed(() => {
      const all = [...records.values()], shown = new Set(recent().map(n => n.id))
      return { warning: all.some(n => n.level === 'warning' || ['unknown', 'failed', 'retired'].includes(n.status)), busy: all.some(n => n.busy),
        hiddenUnresolved: all.filter(n => unresolvedActivity(n) && !shown.has(n.id)).length }
    }),
    beginEpoch() { for (const notice of records.values()) if (notice.status === 'success') remove(notice.id) },
    async readUnfinished() {
      for (const notice of [...records.values()]) {
        if (!unresolvedActivity(notice) || notice.busy || !notice.read) continue
        set({ ...notice, status: 'syncing', retry: undefined })
        try { await notice.read() }
        catch { /* Business owners retain their typed failure. */ }
        // Owners may replace or remove the activity during read. Do not invent success.
        const current = records.get(notice.id)
        if (current?.status === 'syncing') set({ ...notice })
      }
    },
  }
}
export type NoticeStore = ReturnType<typeof createNoticeStore>
export const noticeKey: InjectionKey<NoticeStore> = Symbol('notices')
