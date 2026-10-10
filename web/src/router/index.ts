import { createRouter, createWebHistory, type RouterHistory } from 'vue-router'
import PlayerView from '../views/PlayerView.vue'
export function createPlayerRouter(history: RouterHistory = createWebHistory()) {
  return createRouter({ history, routes: [
    { path: '/', name: 'player', component: PlayerView },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ] })
}
