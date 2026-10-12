import { readonly, shallowReactive, type InjectionKey } from 'vue'
import type { PlayerFacts } from '../components/player/playerFacts'
export function createArtworkStore(options: { fetch: typeof fetch }) {
  const state = shallowReactive({ decodedUrl: null as string | null, status: '无封面' })
  let identity = '', generation = 0, abort: AbortController | null = null
  let releaseDecoded: (() => void) | null = null
  const clear = () => {
    abort?.abort(); abort = null
    releaseDecoded?.(); releaseDecoded = null
    state.decodedUrl = null
  }
  async function read(song: PlayerFacts['song'], scope: string) {
    const key = JSON.stringify([scope, song?.song_id, song?.file_uri, song?.artwork])
    if (identity === key) return
    identity = key; const serial = ++generation
    clear()
    if (!song?.song_id || !song.artwork) { state.status = '无封面'; return }
    state.status = '封面加载中'
    abort = new AbortController()
    let candidate: string | null = null
    const revoke = URL.revokeObjectURL?.bind(URL)
    try {
      const response = await options.fetch(`/api/library/songs/${encodeURIComponent(song.song_id)}/artwork`, { signal: abort.signal, cache: 'no-store' })
      if (serial !== generation) return
      if (response.status === 404) { state.status = '无封面'; return }
      if (!response.ok) throw new Error('Artwork read failed')
      const blob = await response.blob()
      if (serial !== generation) return
      candidate = URL.createObjectURL(blob)
      const image = new Image()
      image.src = candidate
      if (typeof image.decode === 'function') await image.decode()
      else await new Promise<void>((resolve, reject) => { image.onload = () => resolve(); image.onerror = () => reject(new Error('Artwork decode failed')) })
      if (serial !== generation) return
      state.decodedUrl = candidate; const accepted = candidate; releaseDecoded = () => revoke?.(accepted); candidate = null; state.status = ''
    } catch {
      if (serial === generation) state.status = '封面读取失败'
    } finally { if (candidate) revoke?.(candidate) }
  }
  const view = readonly(state)
  return {
    get decodedUrl() { return view.decodedUrl }, get status() { return view.status }, read,
    fail(url: string) { if (url !== state.decodedUrl) return; clear(); state.status = '封面读取失败' },
    dispose() { ++generation; identity = ''; clear() },
  }
}
export type ArtworkStore = ReturnType<typeof createArtworkStore>
export const artworkKey: InjectionKey<ArtworkStore> = Symbol('artwork')
