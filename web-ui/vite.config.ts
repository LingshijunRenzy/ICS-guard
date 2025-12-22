import { fileURLToPath, URL } from 'node:url'
import path from 'node:path'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), vueDevTools()],

  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  // 开发服务器配置
  server: {
    port: 5173,
    proxy: {
      // API 请求代理到 Flask 后端
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/healthz': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      // WebSocket 代理
      '/ws': {
        target: 'ws://localhost:5000',
        ws: true,
      },
    },
  },

  // 前端路由和静态资源的基础路径，对应 Flask 中 static_url_path="/ui"
  base: '/ui/',

  // 生产构建配置：输出到 Flask 静态目录
  build: {
    outDir: path.resolve(__dirname, '../src/app/static'),
    emptyOutDir: true,
  },
})
