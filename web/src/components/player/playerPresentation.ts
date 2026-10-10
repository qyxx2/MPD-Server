import { computed, shallowRef, watch, type Ref } from 'vue'
import type { PlayerStore } from '../../stores/player'
import type { PlayerActions } from './playerActions'
import { derivePlayerFacts } from './playerFacts'

// Past media presentation only: never exposes capabilities, targets or a new clock sample.
export function createPlayerPresentation(store: PlayerStore, position: Ref<number | null>, actions?: PlayerActions) {
  type Media = Pick<ReturnType<typeof derivePlayerFacts>, 'song' | 'title' | 'duration'> & { primary: 'pause' | 'resume' }
  const retained = shallowRef<{ media: Media; position: number | null; scope: string } | null>(null)
  let armed = false, wasPending = false
  const media = (): Media => {
    const facts = derivePlayerFacts(store.snapshot, store.writable)
    return { song: facts.song, title: facts.title, duration: facts.duration, primary: facts.capabilities.pause ? 'pause' : 'resume' }
  }
  const handoff = shallowRef(false)
  let expiry: ReturnType<typeof setTimeout> | undefined
  function scope() {
    const s = store.snapshot
    return JSON.stringify([s?.epoch, store.marker.generation, store.marker.revisions.library,
      s?.playback?.song_id, s?.playback?.playback_context_id, s?.current_song?.song_id,
      s?.current_song?.file_uri, s?.queue.items.find(item => item.position === 0)?.queue_item_id])
  }
  function clear() { armed = false; retained.value = null; handoff.value = false; clearTimeout(expiry); expiry = undefined }
  const dispose = watch(() => [store.snapshot, store.writable, store.marker.generation, store.marker.revisions.library,
    store.error, position.value, actions?.ui.pending, actions?.ui.confirmed, actions?.ui.error, actions?.ui.unknown], () => {
    const pending = Boolean(actions?.ui.pending)
    if (pending && !wasPending) armed = true
    wasPending = pending
    const facts = derivePlayerFacts(store.snapshot, store.writable)
    const o = store.snapshot?.playback_observation
    if (facts.song && o?.control_target && o.bound_queue_item_id === store.snapshot?.queue.items.find(item => item.position === 0)?.queue_item_id) {
      if (handoff.value || !pending) armed = false
      clearTimeout(expiry); expiry = undefined; handoff.value = false
      retained.value = { media: media(), position: position.value ?? facts.position, scope: scope() }
      return
    }
    const quietUnknown = o?.freshness === 'unknown' && o.actual_freshness === 'unknown' &&
      o.actual_state === null && o.actual_current === null && o.bound_queue_item_id === null && o.control_target === null &&
      o.sync_status === 'UNBOUND' && !o.reconciliation_required && !o.error_code && !o.error_message
    if (!armed || !retained.value || retained.value.scope !== scope() || !store.writable || store.error ||
      !quietUnknown || !actions || (!actions.ui.pending && !actions.ui.confirmed) || actions.ui.error || actions.ui.unknown) { clear(); return }
    handoff.value = true
    // A missing observation cannot keep a historical presentation indefinitely.
    // This limits labelled retention; it never delays/filters canonical unknown.
    if (expiry === undefined) expiry = setTimeout(clear, 6000)
  }, { immediate: true, flush: 'sync' })
  return {
    handoff: computed(() => handoff.value),
    media: computed(() => handoff.value && retained.value ? retained.value.media : media()),
    position: computed(() => handoff.value && retained.value ? retained.value.position : position.value),
    dispose() { dispose(); clear() },
  }
}
