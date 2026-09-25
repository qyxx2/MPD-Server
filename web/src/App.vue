<template>
  <main class="shell">
    <section class="glass-card" aria-labelledby="app-title">
      <p class="eyebrow">MUSIC SERVER</p>
      <h1 id="app-title">MPD-Server</h1>
      <p class="subtitle">Vue 3 / FastAPI development shell</p>
      <div class="status" role="status">
        <span class="status-dot" aria-hidden="true"></span>
        <span>Frontend shell ready</span>
      </div>
    </section>
  </main>
</template>

<style>
:root {
  font-family:
    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI",
    sans-serif;
  color: #f4f7fb;
  background: #070b12;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
}

* {
  box-sizing: border-box;
}

html,
body,
#app {
  min-height: 100%;
  margin: 0;
}

body {
  min-width: 320px;
  background:
    radial-gradient(circle at 15% 20%, rgba(80, 110, 180, 0.24), transparent 34%),
    radial-gradient(circle at 82% 78%, rgba(120, 70, 170, 0.2), transparent 32%),
    #070b12;
}

button,
input,
textarea,
select {
  font: inherit;
}

.shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}

.glass-card {
  width: min(680px, 100%);
  padding: 44px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 28px;
  background: rgba(18, 24, 36, 0.72);
  box-shadow:
    0 24px 80px rgba(0, 0, 0, 0.42),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(20px);
}

.eyebrow {
  margin: 0 0 12px;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  opacity: 0.58;
}

h1 {
  margin: 0;
  font-size: clamp(2.4rem, 8vw, 4.8rem);
  line-height: 0.98;
  letter-spacing: -0.05em;
}

.subtitle {
  margin: 20px 0 0;
  color: rgba(244, 247, 251, 0.68);
  font-size: 1rem;
}

.status {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-top: 28px;
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(244, 247, 251, 0.82);
  font-size: 0.9rem;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    transition: none !important;
    animation: none !important;
  }
}

@media (max-width: 640px) {
  .glass-card {
    padding: 30px;
    border-radius: 22px;
  }
}
</style>
