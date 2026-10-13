<script setup lang="ts">
import { inject } from 'vue'
import { routerKey } from 'vue-router'
const router = inject(routerKey, null)
const items = [
  { path: '/', label: '正在播放', icon: 'M8 5l11 7-11 7z' },
  { path: '/queue', label: 'Queue', icon: 'M5 6h14M5 12h14M5 18h9' },
  { path: '/library', label: '音乐库', icon: 'M4 4h5v16H4zM11 4h4v16h-4zM17 5l3-1 4 15-3 1z' },
  { path: '/settings', label: '设置', icon: 'M4 7h16M4 17h16M8 4v6m8 4v6' },
]
function selected(path: string) { const current = router?.currentRoute.value.path ?? '/'; return path === '/' ? current === '/' : current === path || current.startsWith(`${path}/`) }
</script>
<template>
  <nav class="bottom-navigation" aria-label="主导航"><a v-for="item in items" :key="item.path" :href="item.path" :aria-label="item.label" :aria-current="selected(item.path) ? 'page' : undefined" @click="router && ($event.preventDefault(), router.push(item.path))"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="item.icon" /></svg><span>{{ item.label }}</span></a></nav>
</template>
<style scoped>
.bottom-navigation { height: var(--app-bottom-bar-height); display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); flex-shrink: 0; width: 100%; }
.bottom-navigation a { min-width: 44px; min-height: 44px; display: flex; flex-direction: column; gap: .3rem; align-items: center; justify-content: center; text-decoration: none; color: var(--text-secondary); font-size: .75rem; line-height: 1.5; }
.bottom-navigation a[aria-current] { color: var(--accent); font-weight: 650; }
</style>
