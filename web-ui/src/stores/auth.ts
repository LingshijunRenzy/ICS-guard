import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

const TOKEN_KEY = 'ics_guard_token'

export const useAuthStore = defineStore('auth', () => {
    const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))

    const isAuthenticated = computed(() => !!token.value)

    function setToken(value: string | null) {
        token.value = value
        if (value) {
            localStorage.setItem(TOKEN_KEY, value)
        } else {
            localStorage.removeItem(TOKEN_KEY)
        }
    }

    return {
        token,
        isAuthenticated,
        setToken,
    }
})


