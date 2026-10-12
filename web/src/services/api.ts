import type { JsonValue, MutationIntent, MutationMethod } from '../types/api'

import { ApiError } from '../types/api'
export { ApiError } from '../types/api'

export interface ReadClock {
  setTimeout(callback: () => void, ms: number): ReturnType<typeof setTimeout>
  clearTimeout(timer: ReturnType<typeof setTimeout>): void
}

export function createApiClient(options: { fetch: typeof fetch; origin: string; readTimeoutMs?: number; clock?: ReadClock }) {
  const readTimeoutMs = options.readTimeoutMs ?? 10_000
  const clock = options.clock ?? { setTimeout: (callback, ms) => setTimeout(callback, ms), clearTimeout: timer => clearTimeout(timer) }
  const base = new URL(options.origin)
  if (!['http:', 'https:'].includes(base.protocol)) throw new TypeError('HTTP origin required')
  const origin = base.origin
  const socketUrl = new URL('/api/realtime', origin)
  socketUrl.protocol = socketUrl.protocol === 'https:' ? 'wss:' : 'ws:'

  async function request<T>(path: string, init: RequestInit, decode: (value: unknown) => T): Promise<T> {
    const url = apiUrl(path)
    let response: Response
    try { response = await options.fetch(url, { ...init, redirect: 'error' }) }
    catch (error) { throw new ApiError('network', null, 'NETWORK_UNKNOWN', 'Request outcome is unknown', error) }
    if (init.signal?.aborted) throw init.signal.reason
    let value: unknown
    try { value = response.status === 204 ? undefined : await response.json() }
    catch (error) {
      if (error instanceof SyntaxError) throw new ApiError('wire', response.status, 'INVALID_RESPONSE', 'Response is not valid JSON')
      throw new ApiError('network', response.status, 'NETWORK_UNKNOWN', 'Request outcome is unknown', error)
    }
    if (!response.ok) {
      const body = value as { error?: { code?: unknown; message?: unknown; details?: unknown } } | null
      const error = body?.error
      throw new ApiError('http', response.status,
        typeof error?.code === 'string' ? error.code : 'HTTP_ERROR',
        typeof error?.message === 'string' ? error.message : 'Request failed', error?.details ?? null)
    }
    if (init.signal?.aborted) throw init.signal.reason
    return decode(value)
  }

  function apiUrl(path: string): string {
    const url = new URL(path, origin)
    if (!path.startsWith('/api/') || url.origin !== origin || !url.pathname.startsWith('/api/') || url.hash) {
      throw new TypeError('Same-origin /api/ path required')
    }
    return url.href
  }

  return {
    realtimeUrl: socketUrl.href,
    createIntent(method: MutationMethod, path: string, payload: JsonValue | undefined): MutationIntent {
      apiUrl(path)
      const canonicalPayload = payload === undefined ? undefined : JSON.stringify(canonicalize(payload))
      const captured = canonicalPayload === undefined ? undefined : freezeJson(JSON.parse(canonicalPayload))
      // Secure contexts have randomUUID; LAN HTTP still provides getRandomValues.
      const key = Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('')
      return Object.freeze({ key, method, path, payload: captured, canonicalPayload })
    },
    send<T>(intent: MutationIntent, decode: (value: unknown) => T) {
      return request(intent.path, {
        method: intent.method, cache: 'no-store',
        headers: { 'Idempotency-Key': intent.key, ...(intent.canonicalPayload === undefined ? {} : { 'Content-Type': 'application/json' }) },
        body: intent.canonicalPayload,
      }, decode)
    },
    async get<T>(path: string, decode: (value: unknown) => T, readOptions: { signal?: AbortSignal } = {}) {
      const controller = new AbortController()
      let timer: ReturnType<typeof setTimeout> | undefined
      let cancel = () => {}
      // Abort alone is insufficient: transports (and Response bodies) can ignore it.
      const deadline = new Promise<never>((_resolve, reject) => {
        cancel = () => {
          const error = new ApiError('network', null, 'READ_CANCELLED', 'Read cancelled')
          reject(error); controller.abort(error)
        }
        readOptions.signal?.addEventListener('abort', cancel, { once: true })
        if (readOptions.signal?.aborted) { cancel(); return }
        timer = clock.setTimeout(() => {
          const error = new ApiError('network', null, 'READ_TIMEOUT', path.split('?')[0] === '/api/state'
            ? '状态读取超时，请重试' : '资源读取超时，请重试')
          reject(error); controller.abort(error)
        }, readTimeoutMs)
      })
      try {
        const reading = controller.signal.aborted ? deadline : request(path, { method: 'GET', cache: 'no-store', signal: controller.signal }, decode)
        return await Promise.race([deadline, reading])
      } finally {
        if (timer !== undefined) clock.clearTimeout(timer)
        readOptions.signal?.removeEventListener('abort', cancel)
      }
    },
  }
}

function canonicalize(value: JsonValue, ancestors = new Set<object>()): JsonValue {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return value
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value !== 'object') throw new TypeError('Payload must be JSON')
  if (ancestors.has(value)) throw new TypeError('Cyclic payload')
  if (!Array.isArray(value) && Object.getPrototypeOf(value) !== Object.prototype) throw new TypeError('Payload must be plain JSON')
  ancestors.add(value)
  const result = Array.isArray(value)
    ? Array.from(value, entry => canonicalize(entry, ancestors))
    : Object.fromEntries(Object.keys(value).sort().map(key => [key, canonicalize(value[key]!, ancestors)]))
  ancestors.delete(value)
  return result
}

function freezeJson(value: JsonValue): JsonValue {
  if (value !== null && typeof value === 'object') {
    Object.values(value).forEach(freezeJson)
    Object.freeze(value)
  }
  return value
}
