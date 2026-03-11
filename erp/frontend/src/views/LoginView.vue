<script setup>
import { ref } from 'vue'

const username = ref('')
const password = ref('')
const rememberMe = ref(true)
const isLoading = ref(false)
const error = ref('')

const emit = defineEmits(['login-success'])

const handleLogin = async () => {
  isLoading.value = true
  error.value = ''
  
  setTimeout(() => {
    if (username.value === 'admin' && password.value === 'adminpassword123') {
      emit('login-success')
    } else {
      error.value = '帳號或密碼錯誤'
    }
    isLoading.value = false
  }, 1000)
}
</script>

<template>
  <div class="min-h-screen bg-slate-900 flex flex-col justify-center items-center px-6 py-12">
    <div class="w-full max-w-sm">
      <!-- Logo / Header -->
      <div class="text-center mb-10">
        <h1 class="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-rose-500 mb-2">
          滾麵 ERP
        </h1>
        <p class="text-slate-400 font-medium">智慧物料與進銷存管理系統</p>
      </div>

      <!-- Login Card -->
      <div class="bg-slate-800/50 backdrop-blur-xl border border-slate-700/50 p-8 rounded-3xl shadow-2xl">
        <form @submit.prevent="handleLogin" class="space-y-6">
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">使用者帳號</label>
            <input 
              v-model="username"
              type="text" 
              required
              class="w-full bg-slate-900/50 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-orange-500/50 transition-all"
              placeholder="請輸入帳號"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">密碼</label>
            <input 
              v-model="password"
              type="password" 
              required
              class="w-full bg-slate-900/50 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-orange-500/50 transition-all"
              placeholder="請輸入密碼"
            />
          </div>

          <div class="flex items-center justify-between">
            <label class="flex items-center cursor-pointer group">
              <input 
                v-model="rememberMe"
                type="checkbox" 
                class="hidden peer"
              />
              <div class="w-5 h-5 border-2 border-slate-600 rounded flex items-center justify-center peer-checked:bg-orange-500 peer-checked:border-orange-500 transition-all">
                <svg v-if="rememberMe" class="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span class="ml-2 text-sm text-slate-400 group-hover:text-slate-300 transition-colors">記住裝置 (免洗密碼)</span>
            </label>
          </div>

          <div v-if="error" class="text-rose-500 text-sm font-medium text-center animate-pulse">
            {{ error }}
          </div>

          <button 
            type="submit"
            :disabled="isLoading"
            class="w-full bg-gradient-to-r from-orange-500 to-rose-600 hover:from-orange-400 hover:to-rose-500 text-white font-bold py-3 rounded-xl shadow-lg shadow-orange-900/20 transform transition-all active:scale-95 disabled:opacity-50"
          >
            <span v-if="isLoading" class="flex items-center justify-center">
              <svg class="animate-spin h-5 w-5 mr-3 text-white" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              登入中...
            </span>
            <span v-else>登入系統</span>
          </button>
        </form>
      </div>

      <!-- Footer -->
      <p class="text-center mt-8 text-slate-500 text-xs">
        &copy; 2026 滾麵智慧報表系統. All rights reserved.
      </p>
    </div>
  </div>
</template>
