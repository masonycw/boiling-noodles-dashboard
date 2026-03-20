<script setup>
defineProps({
  user: { type: Object, default: null },
  size: { type: String, default: 'sm' }  // 'sm' = list | 'md' = detail
})
</script>

<template>
  <span v-if="!user" class="text-gray-600">—</span>
  <span v-else-if="size === 'sm'" class="inline-flex items-center gap-1 text-xs">
    <span class="font-mono text-gray-500">{{ user.username }}</span>
    <span class="text-gray-400">{{ user.name }}</span>
  </span>
  <span v-else class="text-xs">
    <span class="block text-gray-500">👤 <span class="font-mono">{{ user.username }}</span></span>
    <span class="block text-gray-200 font-medium mt-0.5">{{ user.name }}</span>
  </span>
</template>
