import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { pdfAssets } from './pdfAssets'

export default defineConfig({
  plugins: [vue(), pdfAssets()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
