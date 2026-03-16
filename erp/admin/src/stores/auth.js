import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('erp_admin_token') || null)
  const user = ref(null)

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  function setToken(t) {
    token.value = t
    if (t) localStorage.setItem('erp_admin_token', t)
    else localStorage.removeItem('erp_admin_token')
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
    localStorage.removeItem('erp_admin_token')
  }

  return { token, user, isLoggedIn, isAdmin, setToken, fetchMe, logout }
})
