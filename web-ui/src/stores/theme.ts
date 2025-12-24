import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

export const useThemeStore = defineStore('theme', () => {
    const theme = ref<'dark' | 'light'>((localStorage.getItem('theme') as 'dark' | 'light') || 'dark')

    const toggleTheme = () => {
        theme.value = theme.value === 'dark' ? 'light' : 'dark'
    }

    const setTheme = (newTheme: 'dark' | 'light') => {
        theme.value = newTheme
    }

    // 监听变化并应用到 DOM 和本地存储
    watch(
        theme,
        (newTheme) => {
            localStorage.setItem('theme', newTheme)
            document.documentElement.setAttribute('data-theme', newTheme)
            // 同时切换 Element Plus 的 dark 模式类名（如果需要）
            if (newTheme === 'dark') {
                document.documentElement.classList.add('dark')
            } else {
                document.documentElement.classList.remove('dark')
            }
        },
        { immediate: true }
    )

    return {
        theme,
        toggleTheme,
        setTheme
    }
})
