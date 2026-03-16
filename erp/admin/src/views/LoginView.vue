<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const username = ref('')
const password = ref('')
const isLoading = ref(false)
const error = ref('')

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

async function handleLogin() {
  isLoading.value = true
  error.value = ''
  try {
    const formData = new URLSearchParams()
    formData.append('username', username.value)
    formData.append('password', password.value)

    const res = await fetch(`${API_BASE}/auth/login/access-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData
    })

    if (!res.ok) { error.value = '帳號或密碼錯誤'; return }

    const data = await res.json()
    auth.setToken(data.access_token)
    await auth.fetchMe()

    if (!auth.isAdmin) {
      auth.logout()
      error.value = '僅限管理員登入後台'
      return
    }
    router.push({ name: 'dashboard' })
  } catch {
    error.value = '連線失敗，請檢查後端服務'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-[#0f1117] flex items-center justify-center px-4">
    <div class="w-full max-w-sm">
      <!-- Header -->
      <div class="text-center mb-10">
        <div class="text-5xl mb-3">🍜</div>
        <h1 class="text-3xl font-extrabold text-white">滾麵 ERP</h1>
        <p class="text-gray-500 text-sm mt-1">管理後台登入</p>
      </div>

      <!-- Card -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl p-8">
        <form @submit.prevent="handleLogin" class="space-y-5">
          <div>
            <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">帳號</label>
            <input
              v-model="username"
              type="text" required autocomplete="username"
              placeholder="管理員帳號"
              class="w-full bg-[#111827] border border-[#374151] rounded-xl px-4 py-3 text-white placeholder-gray-600 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
            />
          </div>

          <div>
            <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">密碼</label>
            <input
              v-model="password"
              type="password" required autocomplete="current-password"
              placeholder="••••••••"
              class="w-full bg-[#111827] border border-[#374151] rounded-xl px-4 py-3 text-white placeholder-gray-600 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
            />
          </div>

          <div v-if="error" class="text-red-400 text-sm text-center font-medium">{{ error }}</div>

          <button
            type="submit"
            :disabled="isLoading"
            class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span v-if="isLoading" class="flex items-center justify-center gap-2">
              <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              登入中…
            </span>
            <span v-else>登入後台</span>
          </button>
        </form>
      </div>

      <p class="text-center text-gray-600 text-xs mt-6">© 2026 滾麵智慧報表系統</p>
    </div>
  </div>
</template>
