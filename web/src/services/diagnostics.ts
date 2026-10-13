import type { ActivityStatus } from '../stores/notices'
// Browser-only diagnostics: no raw messages, request bodies, paths, credentials
// or mutation keys. Local correlation numbers are unrelated to idempotency keys.
export function activityDiagnostic(activity: number, source: string, status: ActivityStatus) {
  const known = ['player', 'task', 'library', 'playlist', 'queue', 'favorites', 'settings', 'output']
  try { console.info('[activity]', { activity, source: known.includes(source) ? source : 'other', status }) }
  catch { /* Diagnostics must never change business results or activity state. */ }
}
export function shortActivityCopy(value: string) {
  return [...value.replace(/\b(?:https?:\/\/|\/api\/|\/music\/|file:\/\/)[^\s]+/g, '关联资源')].slice(0, 96).join('') + ([...value].length > 96 ? '…' : '')
}
