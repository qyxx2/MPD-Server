import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export function nativeProxy(target = 'http://127.0.0.1:8000') {
  return { '/api': { target, changeOrigin: true, ws: true } }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxy = nativeProxy(process.env.API_PROXY_TARGET ?? env.API_PROXY_TARGET)
  return {
    plugins: [vue()],
    server: { host: '0.0.0.0', port: 5173, proxy },
    preview: { host: '0.0.0.0', port: 5173, proxy },
  }
})
