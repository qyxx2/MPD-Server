import { createRouter, createWebHistory, type RouterHistory } from 'vue-router'
import PlayerView from '../views/PlayerView.vue'
import QueueView from '../views/QueueView.vue'
import LibraryView from '../views/LibraryView.vue'
import CollectionView from '../views/CollectionView.vue'
import SearchView from '../views/SearchView.vue'
import PlaylistView from '../views/PlaylistView.vue'
import FavoritesView from '../views/FavoritesView.vue'
import SettingsView from '../views/SettingsView.vue'
export function createPlayerRouter(history: RouterHistory = createWebHistory()) {
  return createRouter({ history, routes: [
    { path: '/', name: 'player', component: PlayerView },
    { path: '/queue', component: QueueView },
    { path: '/library', component: LibraryView },
    { path: '/library/search', component: SearchView },
    { path: '/library/playlists', component: PlaylistView },
    { path: '/library/playlists/:id', component: PlaylistView },
    { path: '/library/favorites', component: FavoritesView },
    { path: '/library/:kind(albums|artists|genres|years|tags)/:id', component: CollectionView },
    { path: '/settings', component: SettingsView },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ] })
}
