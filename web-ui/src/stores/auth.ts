import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

const TOKEN_KEY = 'ics_guard_token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const permissions = ref<string[]>([])
  const permissionsLoaded = ref(false)

  const isAuthenticated = computed(() => !!token.value)

  function setToken(value: string | null) {
    token.value = value
    if (value) {
      localStorage.setItem(TOKEN_KEY, value)
    } else {
      localStorage.removeItem(TOKEN_KEY)
      permissions.value = []
      permissionsLoaded.value = false
    }
  }

  function setPermissions(perms: string[]) {
    permissions.value = perms ?? []
    permissionsLoaded.value = true
  }

  function hasPermission(code: string): boolean {
    return permissions.value.includes(code)
  }

  return {
    token,
    isAuthenticated,
    permissions,
    permissionsLoaded,
    setToken,
    setPermissions,
    hasPermission,
  }
})


