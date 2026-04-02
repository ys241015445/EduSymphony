import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // 与常见本机习惯一致：前端 3000，后端 3002；勿让 Vite 自动抢到 3002
    port: 3000,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:3002',
        changeOrigin: true,
      },
      '/socket.io': {
        target: 'http://127.0.0.1:3002',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
