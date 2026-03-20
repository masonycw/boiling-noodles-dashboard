<script setup>
defineProps({
  user: { type: Object, default: null },
  size: { type: String, default: 'sm' }  // 'sm' = list | 'md' = detail
})
</script>

<template>
  <span v-if="!user" class="text-slate-400">未知</span>
  <span v-else-if="size === 'sm'" class="inline-flex items-center gap-1 text-xs text-slate-500">
    <span class="font-mono">{{ user.username }}</span>
    <span class="text-slate-700 font-medium">{{ user.name }}</span>
  </span>
  <span v-else class="text-xs">
    <span class="block text-slate-400">👤 <span class="font-mono">{{ user.username }}</span></span>
    <span class="block text-slate-800 font-semibold mt-0.5">{{ user.name }}</span>
  </span>
</template>
