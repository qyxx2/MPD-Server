<script setup lang="ts">
import FavoriteIcon from '../library/FavoriteIcon.vue'
import type { DeepReadonly } from 'vue'
import type { QueueItem, Song } from '../../types/api'
defineProps<{ item: QueueItem; song: DeepReadonly<Song> | null; icon?: string | null; disabled?: boolean; menuOpen?: boolean }>()
defineEmits<{ play: []; more: [event: MouseEvent]; dragStart: [event: PointerEvent]; dragMove: [event: PointerEvent]; dragEnd: [event: PointerEvent]; dragCancel: [] }>()
</script>
<template>
  <li class="queue-occurrence" :data-queue-item="item.queue_item_id">
    <button type="button" class="queue-play" :disabled="disabled" :aria-label="`播放 ${song?.title || item.song_id}，${song?.artists.join(' / ') || '—'}，${item.source === 'MANUAL' ? '手动' : 'AutoPlay'}，条目 ${item.queue_item_id}`" @click="$emit('play')">
      <span class="queue-identity"><span class="queue-title"><span v-if="icon" data-playback-icon class="queue-playback-icon" :aria-label="icon === 'paused' ? '已暂停' : '正在播放'">{{ icon === 'paused' ? 'Ⅱ' : '▶' }}</span>{{ song?.title || '—' }}</span><span class="queue-artist">{{ song?.artists.join(' / ') || '—' }}</span></span>
      <FavoriteIcon :song-id="item.song_id" /><span class="queue-source">{{ item.source === 'MANUAL' ? '手动' : 'AutoPlay' }}<span v-if="song && song.availability_status !== 'AVAILABLE'" class="queue-unavailable">不可用</span></span>
    </button>
    <button type="button" class="queue-more" :disabled="disabled" :aria-expanded="menuOpen" :aria-label="`更多操作 ${song?.title || item.song_id}，条目 ${item.queue_item_id}`" @click="$emit('more', $event)">⋯</button>
    <button v-if="item.position > 0" type="button" class="queue-drag" :disabled="disabled" :aria-label="`长按排序 ${song?.title || item.song_id}，条目 ${item.queue_item_id}`" @pointerdown="$emit('dragStart', $event)" @pointermove="$emit('dragMove', $event)" @pointerup="$emit('dragEnd', $event)" @pointercancel="$emit('dragCancel')" @lostpointercapture="$emit('dragCancel')">≡</button>
  </li>
</template>
