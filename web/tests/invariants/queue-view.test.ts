import { expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { shellPage } from '../support/shell'
import { playerState } from '../support/player'
import { deferred } from '../support/transport'

function queueState() {
  const state = playerState()
  return { ...state, sequence: state.sequence + 1, explicit_stop_generation: 2, queue: { revision: 8, items: [
    { queue_item_id: 'played-old', song_id: 'song-a', position: -2, source: 'MANUAL' as const, playback_context_id: 'context-a' },
    { queue_item_id: 'played-recent', song_id: 'song-a', position: -1, source: 'AUTOPLAY' as const, playback_context_id: 'context-a' },
    ...state.queue.items,
  ] } }
}
const rows = (h: Awaited<ReturnType<typeof shellPage>>) => h.wrapper.findAll('[data-queue-item]').map(row => row.attributes('data-queue-item')!)
async function pull(h: Awaited<ReturnType<typeof shellPage>>, distance = 72) {
  const view = h.wrapper.get('.queue-view')
  await view.trigger('touchstart', { touches: [{ clientX: 20, clientY: 100 }] })
  await view.trigger('touchmove', { touches: [{ clientX: 20, clientY: 100 + distance }] })
  await view.trigger('touchend', { touches: [] })
  await flushPromises()
}
it('continuous_occurrences_confirm_icons_without_claiming_actual', async () => {
  const state = queueState()
  state.queue.items.find(item => item.position > 0)!.source = 'MANUAL'
  const h = await shellPage(Response.json(state.current_song))
  h.store.acceptRefresh(state, 1)
  await h.router.push('/queue'); await flushPromises()
  expect(rows(h)).toEqual(['item-a', 'item-b'])
  expect(h.wrapper.find('h2').exists()).toBe(false)
  expect(h.wrapper.find('details').exists()).toBe(false)
  expect(h.wrapper.find('[data-testid="expand-played"]').exists()).toBe(false)
  expect(h.wrapper.get('[data-queue-item="item-a"] [data-playback-icon]').attributes('aria-label')).toBe('已暂停')
  expect(h.wrapper.find('[data-queue-item="item-b"] [data-playback-icon]').exists()).toBe(false)
  await pull(h); expect(rows(h)).toEqual(['played-recent', 'item-a', 'item-b'])
  await pull(h); expect(rows(h)).toEqual(['played-old', 'played-recent', 'item-a', 'item-b'])
  expect(h.wrapper.find('[data-queue-item="played-recent"] [data-playback-icon]').exists()).toBe(false)
  const playing = structuredClone(state); playing.sequence++; playing.playback_observation.actual_state = 'playing'
  h.store.acceptRefresh(playing, 1); await flushPromises()
  expect(h.wrapper.get('[data-playback-icon]').attributes('aria-label')).toBe('正在播放')
  for (const mode of ['unbound', 'stale', 'unknown', 'stopped'] as const) {
    const next = structuredClone(playing); next.sequence = ++playing.sequence
    if (mode === 'unbound') { next.playback_observation.bound_queue_item_id = null; next.playback_observation.sync_status = 'UNBOUND'; next.playback_observation.matches_current = false }
    else if (mode === 'stopped') next.playback_observation.actual_state = 'stopped'
    else next.playback_observation.actual_freshness = mode
    h.store.acceptRefresh(next, 1); await flushPromises()
    expect(h.wrapper.find('[data-playback-icon]').exists()).toBe(false)
  }
  h.store.markDisconnected(); await flushPromises()
  expect(h.wrapper.find('[data-playback-icon]').exists()).toBe(false)
  expect(h.network.requests.every(request => request.init?.method === 'GET')).toBe(true)
  h.wrapper.unmount()
})

it('entry_hides_played_pull_reveals_and_lifecycle_resets_without_inventing_stop', async () => {
  const state = queueState()
  const h = await shellPage(Response.json(state.current_song))
  h.store.acceptRefresh(state, 1)
  const scroller = h.wrapper.get('.shell-content').element
  scroller.scrollTop = 250
  await h.router.push('/queue'); await flushPromises()
  expect(scroller.scrollTop).toBe(0)
  expect(rows(h)).toEqual(['item-a', 'item-b'])
  await pull(h); await pull(h); expect(rows(h).slice(0, 2)).toEqual(['played-old', 'played-recent'])
  scroller.scrollTop = 50
  state.sequence++; state.history.session_id = null; state.playback_observation.actual_state = 'stopped'; state.playback_observation.sync_status = 'UNCONFIRMED_STOP'
  h.store.acceptRefresh(structuredClone(state), 1); await flushPromises()
  expect(rows(h).slice(0, 2)).toEqual(['played-old', 'played-recent']); expect(scroller.scrollTop).toBe(50)
  h.store.markDisconnected(); await flushPromises(); expect(rows(h)).toHaveLength(4)
  h.store.beginConnection(2); h.store.acceptInitial(structuredClone(state), 2)
  await h.router.push('/library'); await h.router.push('/queue'); await flushPromises()
  expect(rows(h)).toEqual(['item-a', 'item-b']); expect(scroller.scrollTop).toBe(0)
  await pull(h)
  state.sequence++; state.explicit_stop_generation = 3
  h.store.acceptRefresh(structuredClone(state), 2); await flushPromises(); expect(rows(h)).toHaveLength(2)
  await pull(h)
  const late = structuredClone(state); late.sequence--; late.explicit_stop_generation = 2
  expect(h.store.acceptRefresh(late, 2)).toBe('uncovered'); await flushPromises(); expect(rows(h)).toHaveLength(3)
  const regress = structuredClone(state); regress.sequence++; regress.explicit_stop_generation = 2
  expect(h.store.acceptRefresh(regress, 2)).toBe('uncovered')
  state.sequence++; state.playback!.playback_context_id = 'new-context'
  h.store.acceptRefresh(structuredClone(state), 2); await flushPromises(); expect(rows(h)).toHaveLength(2)
  await pull(h); state.epoch = 'new-epoch'; state.sequence = 0; state.explicit_stop_generation = 0
  h.store.beginConnection(3); h.store.acceptInitial(structuredClone(state), 3)
  await flushPromises(); expect(rows(h)).toHaveLength(2)
  h.wrapper.unmount()
})

it('single_track_previews_first_candidate_multi_track_hides_all_candidates_without_mutation', async () => {
  const state = queueState()
  state.queue.items.push({ ...state.queue.items.find(item => item.position > 0)!, queue_item_id: 'auto-second', position: 2 })
  const h = await shellPage(Response.json(state.current_song))
  h.store.acceptRefresh(state, 1); await h.router.push('/queue'); await flushPromises()
  expect(rows(h)).toEqual(['item-a', 'item-b'])
  expect(h.store.snapshot!.queue.items).toHaveLength(5)
  state.sequence++; state.queue.items.push({ ...state.queue.items[0]!, queue_item_id: 'manual-next', position: 3, source: 'MANUAL' })
  h.store.acceptRefresh(structuredClone(state), 1); await flushPromises()
  expect(rows(h)).toEqual(['item-a', 'manual-next'])
  state.sequence++; state.queue.items = state.queue.items.filter(item => item.position >= 0)
  h.store.acceptRefresh(structuredClone(state), 1); await flushPromises()
  expect(rows(h)).toEqual(['item-a', 'manual-next'])
  state.sequence++; state.queue.items = state.queue.items.filter(item => item.queue_item_id !== 'manual-next'); state.playback!.autoplay_enabled = false
  h.store.acceptRefresh(structuredClone(state), 1); await flushPromises(); expect(rows(h)).toEqual(['item-a'])
  expect(h.network.requests.every(request => request.init?.method === 'GET')).toBe(true)
  h.wrapper.unmount()
})
it('on_page_current_transition_keeps_revealed_history_and_scroll', async () => {
  const state = queueState()
  const h = await shellPage(Response.json(state.current_song))
  h.store.acceptRefresh(state, 1); await h.router.push('/queue'); await flushPromises()
  await pull(h); await pull(h)
  const scroller = h.wrapper.get('.shell-content').element; scroller.scrollTop = 90
  state.sequence++; state.queue.revision++
  for (const item of state.queue.items) item.position--
  state.playback_observation.bound_queue_item_id = 'item-b'
  h.store.acceptRefresh(structuredClone(state), 1); await flushPromises()
  expect(rows(h)).toEqual(['played-old', 'played-recent', 'item-a', 'item-b'])
  expect(scroller.scrollTop).toBe(90)
  h.wrapper.unmount()
})

it('metadata_failure_keeps_occurrences_and_late_revision_cannot_replace_metadata', async () => {
  const state = queueState(), late = deferred<Response>()
  const h = await shellPage(late.promise, Response.json({ ...state.current_song, title: '新版本长标题' }))
  h.store.acceptRefresh(state, 1)
  await h.router.push('/queue'); await flushPromises()
  expect(h.wrapper.findAll('[data-queue-item]')).toHaveLength(2)
  state.sequence++; state.revisions.library++
  h.store.invalidate({ type: 'invalidate', protocol_version: 1, epoch: state.epoch, sequence: state.sequence, domains: ['library'], revisions: state.revisions }, 1)
  await flushPromises()
  late.resolve(Response.json({ ...state.current_song, title: '旧版本' })); await flushPromises()
  expect(h.wrapper.get('[data-queue-item="item-b"]').text()).toContain('新版本长标题')
  expect(h.wrapper.text()).not.toContain('旧版本')
  h.wrapper.unmount()
  const failed = await shellPage(Response.json({ error: { code: 'NOT_FOUND', message: 'metadata missing' } }, { status: 404 }))
  failed.store.acceptRefresh(state, 1)
  await failed.router.push('/queue'); await flushPromises()
  expect(failed.wrapper.findAll('[data-queue-item]')).toHaveLength(2)
  await failed.wrapper.get('.status-toggle').trigger('click')
  expect(failed.wrapper.get('#playback-status-details').text()).toContain('metadata missing')
  failed.wrapper.unmount()
})

it('metadata_identity_mismatch_is_top_notice_without_replacing_occurrence', async () => {
  const state = queueState()
  const h = await shellPage(Response.json({ ...state.current_song, song_id: 'other-song', title: '错误身份标题' }))
  h.store.acceptRefresh(state, 1)
  await h.router.push('/queue'); await flushPromises()
  expect(h.wrapper.findAll('[data-queue-item]')).toHaveLength(2)
  expect(h.wrapper.text()).not.toContain('错误身份标题')
  expect(h.wrapper.get('[data-testid="operation-status"]').text()).toContain('Song identity')
  h.wrapper.unmount()
})

it('missing_legacy_counter_does_not_infer_stop_from_session_or_stopped_state', async () => {
  const state = queueState()
  const h = await shellPage(Response.json({ ...state.current_song, availability_status: 'MISSING' }))
  const legacy = { ...state, epoch: 'legacy-server', explicit_stop_generation: null }
  h.store.beginConnection(2); h.store.acceptInitial(legacy, 2)
  await h.router.push('/queue'); await flushPromises()
  await pull(h); await pull(h)
  const playedRows = () => rows(h).filter(id => id.startsWith('played-'))
  expect(playedRows()).toHaveLength(2)
  expect(h.wrapper.get('[data-queue-item="item-b"]').text()).toContain('不可用')
  legacy.sequence++; legacy.history.session_id = null; legacy.playback!.state = 'STOPPED'
  h.store.acceptRefresh(legacy, 2); await flushPromises(); expect(playedRows()).toHaveLength(2)
  const known = { ...legacy, sequence: legacy.sequence + 1, explicit_stop_generation: 3 }
  h.store.acceptRefresh(known, 2); await flushPromises(); expect(playedRows()).toHaveLength(2)
  h.store.acceptRefresh({ ...known, sequence: known.sequence + 1, explicit_stop_generation: null }, 2)
  h.store.acceptRefresh({ ...known, sequence: known.sequence + 2, explicit_stop_generation: 4 }, 2)
  await flushPromises(); expect(playedRows()).toHaveLength(0)
  h.wrapper.unmount()
})
it('reorder_handle_touch_does_not_reveal_history_or_trigger_play', async () => {
  const state = queueState(); state.queue.items.find(item => item.position > 0)!.source = 'MANUAL'
  const h = await shellPage(Response.json(state.current_song))
  h.store.acceptRefresh(state, 1); await h.router.push('/queue'); await flushPromises()
  const handle = h.wrapper.get('.queue-drag')
  await handle.trigger('touchstart', { touches: [{ clientX: 20, clientY: 100 }] })
  await handle.trigger('touchmove', { touches: [{ clientX: 20, clientY: 250 }] })
  await handle.trigger('touchend', { touches: [] }); await flushPromises()
  expect(rows(h)).toEqual(['item-a', 'item-b'])
  expect(h.network.requests.every(request => request.init?.method === 'GET')).toBe(true)
  h.wrapper.unmount()
})
