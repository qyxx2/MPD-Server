<script setup lang="ts">
defineProps<{ name: 'songs' | 'albums' | 'artists' | 'genres' | 'years' | 'tags' | 'playlists' | 'favorites' | 'back' | 'play' | 'shuffle' }>()
const paths = {
  songs: 'M9 18V5l11-2v13M9 8l11-2M9 18c0 1.7-1.8 3-4 3s-3-1-3-2.5S4 16 6 16s3 .5 3 2Zm11-2c0 1.7-1.8 3-4 3s-3-1-3-2.5S15 14 17 14s3 .5 3 2Z',
  albums: 'M4 3h16v18H4zM16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Zm-4 0h.01',
  artists: 'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM4 21v-2a8 8 0 0 1 16 0v2',
  genres: 'M4 9v6M8 5v14M12 2v20M16 5v14M20 9v6',
  years: 'M4 5h16v16H4zM4 10h16M8 3v4M16 3v4M8 14h2M14 14h2M8 17h2',
  tags: 'M3 3h8l10 10-8 8L3 11zM7 7h.01',
  playlists: 'M4 5h16M4 10h16M4 15h9M17 13v8M13 17h8',
  favorites: 'M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z',
  back: 'M15 5l-7 7 7 7',
  play: 'M8 4l13 8-13 8z',
  shuffle: 'M3 5h3c5 0 7 14 12 14h3M17 15l4 4-4 4M3 19h3c2 0 4-3 5-5M13 9c2-3 3-4 5-4h3M17 1l4 4-4 4',
}
</script>
<template><svg class="library-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path :d="paths[name]" /></svg></template>
