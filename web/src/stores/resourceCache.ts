import { readonly, shallowReactive } from 'vue'
import type { ResourceMarker } from './player'
import type { Revisions } from '../types/api'

export function createResourceCache<T>(options: { load: (key: string) => Promise<T>; dependencies: readonly (keyof Revisions)[] }) {
  type Entry = { data: T | null; fresh: boolean; loading: boolean; error: unknown }
  type Row = { state: Entry; generation: number; flight: Promise<T> | null }
  const rows = new Map<string, Row>()
  let known: ResourceMarker | null = null
  function row(key: string): Row {
    let value = rows.get(key)
    if (!value) {
      value = { state: shallowReactive({ data: null, fresh: false, loading: false, error: null }), generation: 0, flight: null }
      rows.set(key, value)
    }
    return value
  }
  function invalidate(marker: ResourceMarker, invalidation: { force?: boolean } = {}) {
    if (known?.epoch === marker.epoch && (marker.generation < known.generation || marker.sequence < known.sequence)) return
    const changed = !known || known.epoch !== marker.epoch || known.generation !== marker.generation || known.trusted !== marker.trusted ||
      options.dependencies.some(dependency => known!.revisions[dependency] !== marker.revisions[dependency])
    known = { ...marker, revisions: { ...marker.revisions } }
    if (changed || invalidation.force) {
      for (const value of rows.values()) {
        value.generation++; value.flight = null; value.state.fresh = false; value.state.loading = false
      }
    }
  }
  function read(key: string): Promise<T> {
    const value = row(key)
    if (value.state.fresh) return Promise.resolve(value.state.data as T)
    if (value.flight) return value.flight
    if (!known?.epoch) return Promise.reject(new Error('Resource epoch baseline unavailable'))
    const generation = value.generation
    const captured = known
    value.state.loading = true
    // Convert synchronous transport/decoder setup failures to an awaited rejection.
    // The flight is installed before that rejection can run finally.
    let request: Promise<T>
    try { request = options.load(key) }
    catch (error) { request = Promise.reject(error) }
    const promise = (async () => {
      try {
        const data = await request
        if (generation !== value.generation) return await read(key)
        value.state.data = freeze(structuredClone(data))
        value.state.fresh = captured.trusted
        value.state.error = null
        return value.state.data
      } catch (error) {
        if (generation !== value.generation) return await read(key)
        value.state.error = error; value.state.fresh = false
        throw error
      } finally {
        if (generation === value.generation) { value.state.loading = false; value.flight = null }
      }
    })()
    value.flight = promise
    return promise
  }
  return { read, invalidate, entry: (key: string) => readonly(row(key).state) }
}
function freeze<T>(value: T): T {
  if (value !== null && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value) }
  return value
}
