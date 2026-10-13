import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory } from 'vue-router'
import { afterEach, expect, it, vi } from 'vitest'
import App from '../../src/App.vue'
import AppShell from '../../src/components/layout/AppShell.vue'
import { createPlayerRouter } from '../../src/router'
import fixture from '../fixtures/wire.json'
import { type PlayerStore } from '../../src/stores/player'

afterEach(() => vi.unstubAllGlobals())

it('real App starts, reconnects and stops with browser timer receivers', async () => {
  vi.useFakeTimers()
  const schedule = globalThis.setTimeout, cancel = globalThis.clearTimeout
  // jsdom/fake timers accept arbitrary receivers; native browser timers do not.
  // Model that boundary while mounting the actual production composition root.
  const assertReceiver = (receiver: unknown) => {
    if (receiver !== undefined && receiver !== window) throw new TypeError('Illegal invocation')
  }
  vi.stubGlobal('setTimeout', function (this: unknown, ...args: Parameters<typeof setTimeout>) {
    assertReceiver(this)
    return schedule(...args)
  })
  vi.stubGlobal('clearTimeout', function (this: unknown, ...args: Parameters<typeof clearTimeout>) {
    assertReceiver(this)
    return cancel(...args)
  })
  vi.spyOn(Math, 'random').mockReturnValue(0)
  const sockets: Socket[] = []
  class Socket {
    listeners = new Map<string, Set<(event: { data?: string }) => void>>()
    closed = false
    constructor(readonly url: string) { sockets.push(this) }
    addEventListener(type: string, listener: (event: { data?: string }) => void) {
      const listeners = this.listeners.get(type) ?? new Set()
      listeners.add(listener); this.listeners.set(type, listeners)
    }
    removeEventListener(type: string, listener: (event: { data?: string }) => void) {
      this.listeners.get(type)?.delete(listener)
    }
    close() { this.closed = true }
    initial() {
      const state = structuredClone(fixture.snapshot)
      this.listeners.get('message')?.forEach(listener => listener({ data: JSON.stringify({
        type: 'snapshot', protocol_version: 1, epoch: state.epoch, sequence: state.sequence, state,
      }) }))
    }
    disconnect() { this.listeners.get('close')?.forEach(listener => listener({})) }
  }
  vi.stubGlobal('WebSocket', Socket)
  vi.stubGlobal('fetch', async () => Response.json({ song_ids: [] }))
  const errors: unknown[] = []
  const router = createPlayerRouter(createMemoryHistory())
  await router.push('/'); await router.isReady()
  const wrapper = mount(App, { global: { plugins: [router], config: { errorHandler: error => errors.push(error) } } })
  let unmounted = false
  try {
    await flushPromises()
    expect(errors).toEqual([])
    expect(sockets).toHaveLength(1)
    const store = wrapper.getComponent(AppShell).props('store') as PlayerStore
    expect(store.writable).toBe(false)
    sockets[0]!.initial(); await flushPromises()
    expect(store.writable).toBe(true)
    expect(errors).toEqual([])
    sockets[0]!.disconnect()
    expect(store.writable).toBe(false)
    expect(sockets[0]!.closed).toBe(true)
    await vi.advanceTimersByTimeAsync(500)
    expect(sockets).toHaveLength(2)
    expect(store.writable).toBe(false)
    wrapper.unmount() // Dispose the second socket's pending initial deadline.
    unmounted = true
    expect(sockets[1]!.closed).toBe(true)
    expect(errors).toEqual([])
    expect(vi.getTimerCount()).toBe(0)
  } finally {
    if (!unmounted) wrapper.unmount()
  }
})
