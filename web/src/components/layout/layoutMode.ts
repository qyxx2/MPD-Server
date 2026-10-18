import { onMounted, onUnmounted, readonly, ref, type InjectionKey, type Ref } from 'vue'
export type LayoutMode = 'portrait' | 'landscape'
export const layoutModeKey: InjectionKey<{ mode: Readonly<Ref<LayoutMode>> }> = Symbol('layout-mode')
export function createLayoutMode(capacity: Ref<HTMLElement | null>) {
  const mode = ref<LayoutMode>('portrait')
  const density = ref<'normal' | 'compact'>('normal')
  const heightFallback = ref(false)
  let observer: ResizeObserver | undefined
  let normal: { height: number; font: number; width: number } | undefined
  let compact: { height: number; font: number; width: number } | undefined
  let fallback = false
  // This probe uses the shell's CSS height budget even in the single column.
  // Keeping the compact measurement across Player unmount prevents oscillation.
  const budget = () => capacity.value?.getBoundingClientRect()
  const update = () => {
    // Use the CSS result: zoom can round innerWidth up across the breakpoint.
    const landscape = typeof window.matchMedia === 'function'
      ? window.matchMedia('(min-width: 900px) and (orientation: landscape)').matches
      : window.innerWidth >= 900 && window.innerWidth > window.innerHeight
    if (!landscape) {
      mode.value = 'portrait'; heightFallback.value = false; return
    }
    const space = budget()
    if (!space || space.width <= 0) { mode.value = 'landscape'; return }
    const normalHeight = normal ? normal.height * space.width / normal.font : 300
    const compactHeight = compact ? compact.height * space.width / compact.font : null
    const normalWidth = normal ? Math.max(200, normal.width * space.width / normal.font) : 200
    const compactWidth = compact ? Math.max(64, compact.width * space.width / compact.font) : 64
    const maxPlayerWidth = Math.min(400, Math.max(340, window.innerWidth * .36))
    if (fallback) {
      // A little recovery headroom avoids threshold noise from browser chrome.
      if (compactHeight !== null && (space.height < compactHeight + compactWidth + 16 || compactWidth > maxPlayerWidth)) {
        heightFallback.value = true; return
      }
      fallback = false
    }
    mode.value = 'landscape'; heightFallback.value = false
    const next = space.height < normalHeight + normalWidth || normalWidth > maxPlayerWidth ? 'compact' : 'normal'
    if (density.value !== next) { density.value = next; return }
    if (next === 'compact' && compactHeight !== null && (space.height < compactHeight + compactWidth || compactWidth > maxPlayerWidth)) {
      fallback = true; mode.value = 'portrait'; heightFallback.value = true
    }
  }
  const reportInfoHeight = (height: number, width: number) => {
    if (mode.value !== 'landscape' || height <= 0) return
    const font = budget()?.width
    if (!font) return
    if (density.value === 'normal') normal = { height, font, width }
    else compact = { height, font, width }
    update()
  }
  update()
  onMounted(() => {
    window.addEventListener('resize', update)
    window.visualViewport?.addEventListener('resize', update)
    if (capacity.value && typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(update); observer.observe(capacity.value)
    }
    update()
  })
  onUnmounted(() => {
    observer?.disconnect()
    window.removeEventListener('resize', update)
    window.visualViewport?.removeEventListener('resize', update)
  })
  return { mode: readonly(mode), density: readonly(density), heightFallback: readonly(heightFallback), reportInfoHeight }
}
