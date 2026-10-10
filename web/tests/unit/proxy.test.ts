// @vitest-environment node
import { expect, test } from 'vitest'
import { nativeProxy } from '../../vite.config'

test('native dev and preview proxy can forward REST and WS to loopback', () => {
  expect(nativeProxy()['/api']).toEqual({ target: 'http://127.0.0.1:8000', changeOrigin: true, ws: true })
  expect(nativeProxy('http://127.0.0.1:8123')['/api'].target).toBe('http://127.0.0.1:8123')
})
