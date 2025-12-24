<script setup lang="ts">
import { onMounted } from 'vue'
import MainLayout from './layouts/MainLayout.vue'
import { useThemeStore } from './stores/theme'

const themeStore = useThemeStore()

onMounted(() => {
  // 确保初始主题被正确应用
  document.documentElement.setAttribute('data-theme', themeStore.theme)
  if (themeStore.theme === 'dark') {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
})
</script>

<template>
  <MainLayout />
</template>

<style scoped>
html,
body,
#app {
  margin: 0;
  padding: 0;
}
</style>

