import { afterEach, vi } from 'vitest'

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

// Node-only proxy tests have no DOM; jsdom tests replace only bitmap decoding.
if (typeof HTMLImageElement !== 'undefined') Object.defineProperty(HTMLImageElement.prototype, 'decode', { configurable: true, value: async function () {} })
