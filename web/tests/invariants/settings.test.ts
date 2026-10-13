import { expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { libraryPage } from '../support/library'
import { playerState, fixture } from '../support/player'
import { deferred } from '../support/transport'
import info from '../fixtures/settings.json'

it('about_and_output_are_distinct_authorities', async () => {
  const h = await libraryPage('/settings', path => path === '/api/system/mpd' ? Promise.resolve(Response.json(info)) : undefined)
  expect(h.wrapper.find('[data-mpd-info]').exists()).toBe(true)
  expect(h.wrapper.get('[data-mpd-info]').text()).toContain('0.23.5')
  expect(h.wrapper.get('[data-mpd-stat="songs"]').text()).toBe('0')
  expect(h.wrapper.get('[data-mpd-stat="albums"]').text()).toBe('—')
  expect(h.wrapper.get('[data-mpd-stat="db_playtime"]').text()).toContain('123')
  expect(h.wrapper.get('[data-mpd-stat="playtime"]').text()).toContain('7')
  expect(h.wrapper.get('[data-testid="confirmed-output"]').text()).toContain('已启用')
  expect(h.wrapper.find('[data-output-request]').exists()).toBe(false)
  expect(h.wrapper.get('[data-client-stream]').attributes('disabled')).toBeDefined()
  expect(h.requests.filter(r => r.init?.method !== 'GET')).toHaveLength(0)
  await h.wrapper.get('.status-toggle').trigger('click')
  expect(h.wrapper.get('.status-details').text()).toContain('PLAYER_COMMAND_ERROR')
  expect(h.wrapper.get('[data-mpd-info]').text()).not.toContain('rejected')
  h.wrapper.unmount()
})
it('output_unknown_survives_navigation_without_inline_notice', async () => {
  let attempts = 0
  const s = playerState(); s.sequence++; s.output.states[0]!.status = 'INACTIVE'
  const h = await libraryPage('/settings', (path, init) => {
    if (path === '/api/system/mpd') return Promise.resolve(Response.json(info))
    if (init?.method === 'PUT') return ++attempts === 1 ? Promise.reject(new TypeError('lost ACK')) : Promise.resolve(Response.json(fixture.rest_output))
    if (path === '/api/state' && attempts > 1) return Promise.resolve(Response.json(s))
  })
  await h.wrapper.get('[data-output-switch]').trigger('click'); await flushPromises()
  expect(h.wrapper.get('[data-testid="confirmed-output"]').text()).toContain('已启用')
  expect(h.wrapper.get('[data-output-switch]').attributes('disabled')).toBeDefined()
  await h.router.push('/library'); await flushPromises()
  expect(h.tasks.entries.value.find(r => r.intent.path === '/api/system/output')?.state).toBe('unknown')
  await h.tasks.entries.value.find(r => r.intent.path === '/api/system/output')!.retry!(); await flushPromises()
  const writes = h.requests.filter(r => r.init?.method === 'PUT')
  expect(writes).toHaveLength(2)
  expect(writes[0]!.init!.body).toBe(writes[1]!.init!.body)
  expect(new Headers(writes[0]!.init!.headers).get('Idempotency-Key')).toBe(new Headers(writes[1]!.init!.headers).get('Idempotency-Key'))
  await h.router.push('/'); await flushPromises()
  expect(h.wrapper.get('[data-testid="output-fact"]').text()).toContain('未启用')
  h.wrapper.unmount()
})
it('confirmed_output_read_failure_recovers_by_read_only_and_pending_survives_route', async () => {
  const reply = deferred<Response>(); let reads = 0
  const h = await libraryPage('/settings', (path, init) => {
    if (path === '/api/system/mpd') return Promise.resolve(Response.json(info))
    if (init?.method === 'PUT') return reply.promise
    if (path === '/api/state') return ++reads === 1 ? Promise.reject(new TypeError('read failed')) : Promise.resolve(Response.json(playerState()))
  })
  await h.wrapper.get('[data-output-switch]').trigger('click')
  await h.router.push('/library'); await flushPromises()
  reply.resolve(Response.json(fixture.rest_output)); await flushPromises()
  const record = h.tasks.entries.value.find(r => r.intent.path === '/api/system/output')!
  expect(record.state).toBe('confirmed'); expect(record.readFailed).toBe(true)
  await record.read(); await flushPromises()
  expect(h.tasks.entries.value.find(r => r.intent.path === '/api/system/output')!.readFailed).toBe(false)
  expect(h.requests.filter(r => r.init?.method === 'PUT')).toHaveLength(1)
  h.wrapper.unmount()
})
it('mpd_old_epoch_and_old_request_do_not_install_late_about_facts', async () => {
  const late = deferred<Response>(); let calls = 0
  const h = await libraryPage('/settings', path => path === '/api/system/mpd' ? ++calls === 1 ? late.promise : Promise.resolve(Response.json({ ...info, version: 'new' })) : undefined)
  h.store.beginConnection(2); const s = playerState(); s.epoch = 'new'; h.store.acceptInitial(s, 2)
  await flushPromises(); late.resolve(Response.json(info)); await flushPromises()
  expect(h.wrapper.get('[data-mpd-info]').text()).toContain('new')
  expect(h.wrapper.get('[data-mpd-info]').text()).not.toContain('0.23.5')
  h.store.markDisconnected(); await flushPromises()
  expect(h.wrapper.get('[data-output-switch]').attributes('disabled')).toBeDefined()
  expect(h.wrapper.get('[data-mpd-info]').attributes('data-stale')).toBe('true')
  h.wrapper.unmount()
})
it('library_tabs_are_the_only_playlist_and_favorite_entry_and_keep_selection', async () => {
  const h = await libraryPage('/library', path => path === '/api/playlists' ? Promise.resolve(Response.json({ items: [], count: 0 })) : undefined)
  expect(h.wrapper.findAll('.library-search-link')).toHaveLength(1)
  const tabs = h.wrapper.findAll('[data-library-kind]').map(t => t.attributes('data-library-kind'))
  expect(tabs).toEqual(['songs', 'albums', 'artists', 'favorites', 'playlists', 'genres', 'years', 'tags'])
  await h.wrapper.get('[data-library-kind="playlists"]').trigger('click'); await flushPromises()
  expect(h.router.currentRoute.value.path).toBe('/library/playlists')
  expect(h.wrapper.get('[data-library-kind="playlists"]').attributes('aria-pressed')).toBe('true')
  await h.wrapper.get('[data-library-kind="favorites"]').trigger('click'); await flushPromises()
  expect(h.router.currentRoute.value.path).toBe('/library/favorites')
  expect(h.wrapper.get('[data-library-kind="favorites"]').attributes('aria-pressed')).toBe('true')
  await h.wrapper.get('[data-library-kind="years"]').trigger('click'); await flushPromises()
  expect(h.router.currentRoute.value.query.kind).toBe('years')
  h.wrapper.unmount()
})
it('saved_mpd_address_remains_distinct_from_active_and_survives_unknown_retry', async () => {
  const active = { host: 'old.example', port: 6600 }, saved = { host: 'new.example', port: 6601 }
  let writes = 0
  const h = await libraryPage('/settings', (path, init) => {
    if (path === '/api/system/mpd') return Promise.resolve(Response.json(info))
    if (path === '/api/system/mpd/connection') {
      if (init?.method === 'PUT') return ++writes === 1 ? Promise.reject(new TypeError('lost ACK')) : Promise.resolve(Response.json({ active, saved, restart_required: true }))
      return Promise.resolve(Response.json({ active, saved: writes > 1 ? saved : null, restart_required: writes > 1 }))
    }
  })
  expect(h.wrapper.get('[data-mpd-active]').text()).toContain('old.example')
  await h.wrapper.get('[name="mpd-host"]').setValue('new.example')
  await h.wrapper.get('[name="mpd-port"]').setValue('6601')
  expect(h.wrapper.get('[data-save-mpd]').attributes('disabled')).toBeUndefined()
  await h.wrapper.get('.settings-form').trigger('submit'); await flushPromises()
  await h.router.push('/library'); await flushPromises()
  await h.tasks.entries.value.find(r => r.intent.path.endsWith('/connection'))!.retry!(); await flushPromises()
  await h.router.push('/settings'); await flushPromises()
  expect(h.wrapper.get('[data-mpd-active]').text()).toContain('old.example')
  expect(h.wrapper.get('[data-mpd-saved]').text()).toContain('new.example')
  await h.wrapper.get('.status-toggle').trigger('click')
  expect(h.wrapper.get('.status-details').text()).toContain('服务重启后生效')
  const requests = h.requests.filter(r => r.init?.method === 'PUT')
  expect(requests).toHaveLength(2); expect(requests[0]!.init!.body).toBe(requests[1]!.init!.body)
  expect(new Headers(requests[0]!.init!.headers).get('Idempotency-Key')).toBe(new Headers(requests[1]!.init!.headers).get('Idempotency-Key'))
  h.store.markDisconnected(); await flushPromises()
  expect(h.wrapper.get('[data-save-mpd]').attributes('disabled')).toBeDefined()
  h.wrapper.unmount()
})
it('mpd_connection_new_epoch_clears_old_active_and_restart_notice_until_read', async () => {
  let reads = 0
  const h = await libraryPage('/settings', path => path === '/api/system/mpd/connection' ? ++reads === 1 ? Promise.resolve(Response.json({ active: { host: 'old.example', port: 6600 }, saved: { host: 'new.example', port: 6601 }, restart_required: true })) : Promise.reject(new Error('new server config read failed')) : undefined)
  expect(h.wrapper.get('[data-mpd-active]').text()).toContain('old.example')
  h.store.markDisconnected(); await flushPromises()
  expect(h.wrapper.get('[aria-label="MPD 接入"]').attributes('data-stale')).toBe('true')
  h.store.beginConnection(2); const s = playerState(); s.epoch = 'restarted'; h.store.acceptInitial(s, 2); await flushPromises()
  expect(h.wrapper.get('[data-mpd-active]').text()).toBe('—')
  expect(h.wrapper.get('.status-details').text()).not.toContain('MPD 地址已保存 · 服务重启后生效')
  expect(h.wrapper.get('[data-save-mpd]').attributes('disabled')).toBeDefined()
  h.wrapper.unmount()
})
it('dac_switch_follows_confirmed_state_while_sending_explicit_boolean_targets', async () => {
  const reply = deferred<Response>(); let writes = 0
  const h = await libraryPage('/settings', (path, init) => {
    if (init?.method === 'PUT' && path === '/api/system/output') return ++writes === 1 ? reply.promise : Promise.resolve(Response.json(fixture.rest_output))
    if (path === '/api/state') { const s = playerState(); s.sequence += writes; s.output.states[0]!.status = writes === 1 ? 'INACTIVE' : 'ACTIVE'; return Promise.resolve(Response.json(s)) }
  })
  expect(h.wrapper.get('[data-output-switch]').attributes('role')).toBe('switch')
  expect(h.wrapper.get('[data-output-switch]').attributes('aria-checked')).toBe('true')
  await h.wrapper.get('[data-output-switch]').trigger('click')
  expect(h.wrapper.get('[data-output-switch]').attributes('aria-checked')).toBe('true')
  expect(h.wrapper.get('[data-output-switch]').attributes('disabled')).toBeDefined()
  reply.resolve(Response.json(fixture.rest_output)); await flushPromises()
  expect(h.wrapper.get('[data-output-switch]').attributes('aria-checked')).toBe('false')
  await h.wrapper.get('[data-output-switch]').trigger('click'); await flushPromises()
  expect(h.wrapper.get('[data-output-switch]').attributes('aria-checked')).toBe('true')
  const requests = h.requests.filter(r => r.init?.method === 'PUT')
  expect(requests.map(r => JSON.parse(String(r.init?.body)))).toEqual([{ mode: 'NAS_DAC', enabled: false }, { mode: 'NAS_DAC', enabled: true }])
  const unknown = playerState(); unknown.sequence += 3; unknown.output_observation.freshness = 'unknown'; unknown.output_observation.observed_at = null
  h.store.acceptRefresh(unknown, 1); await flushPromises()
  expect(h.wrapper.get('[data-output-switch]').attributes('aria-checked')).toBeUndefined()
  expect(h.wrapper.get('[data-output-switch]').attributes('disabled')).toBeDefined()
  h.wrapper.unmount()
})
it('ipv6_host_and_five_digit_port_save_separately_and_render_unambiguously', async () => {
  const active = { host: '::1', port: 6600 }, saved = { host: '2001:db8:1234:5678:90ab:cdef:1234:5678', port: 16600 }; let updated = false
  const h = await libraryPage('/settings', (path, init) => {
    if (path === '/api/system/mpd/connection') {
      if (init?.method === 'PUT') updated = true
      return Promise.resolve(Response.json({ active, saved: updated ? saved : null, restart_required: updated }))
    }
  })
  expect(h.wrapper.get('[data-mpd-active]').text()).toBe('[::1]:6600')
  await h.wrapper.get('[name="mpd-host"]').setValue(saved.host)
  await h.wrapper.get('[name="mpd-port"]').setValue(String(saved.port))
  expect(h.wrapper.get('[data-save-mpd]').attributes('disabled')).toBeUndefined()
  await h.wrapper.get('.settings-form').trigger('submit'); await flushPromises()
  const request = h.requests.find(r => r.init?.method === 'PUT')!
  expect(JSON.parse(String(request.init?.body))).toEqual(saved)
  expect(h.wrapper.get('[data-mpd-saved]').text()).toBe(`[${saved.host}]:16600`)
  h.wrapper.unmount()
})
