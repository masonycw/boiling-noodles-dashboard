import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('erp_token') || null)
  const user = ref(null)

  const isLoggedIn = computed(() => !!token.value)

  function setToken(t) {
    token.value = t
    if (t) {
      localStorage.setItem('erp_token', t)
    } else {
      localStorage.removeItem('erp_token')
    }
  }

  async function fetchMe() {
    if (!token.value) return
    try {
      const res = await fetch(`${API_BASE}/users/me`, {
        headers: { Authorization: `Bearer ${token.value}` }
      })
      if (res.ok) {
        user.value = await res.json()
      } else {
        logout()
      }
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('erp_token')
  }

  return { token, user, isLoggedIn, setToken, fetchMe, logout }
})
