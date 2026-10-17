import { beforeEach, afterEach, vi } from 'vitest'

// Existing UI contracts describe the protected portrait presentation.
// Responsive tests explicitly override this baseline before mounting the shell.
beforeEach(() => {
  if (typeof window !== 'undefined') { vi.stubGlobal('innerWidth', 390); vi.stubGlobal('innerHeight', 844) }
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

// Node-only proxy tests have no DOM; jsdom tests replace only bitmap decoding.
if (typeof HTMLImageElement !== 'undefined') Object.defineProperty(HTMLImageElement.prototype, 'decode', { configurable: true, value: async function () {} })
