// vite.config.js
import { defineConfig } from 'vite'

export default defineConfig({
  root: '.', // 默认已是当前目录
  build: {
    rollupOptions: {
      input: './public/index.html'  // ✅ 显式指定入口文件
    }
  }
})
