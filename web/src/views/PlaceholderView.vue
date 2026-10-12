<script setup lang="ts">
defineProps<{ title: string }>()
</script>
<template><section class="placeholder-view" :aria-label="title"></section></template>
<style scoped>.placeholder-view { flex: 1; min-width: 0; }</style>
