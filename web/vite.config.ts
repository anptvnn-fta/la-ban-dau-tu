import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

// La Bàn Đầu Tư — frontend build.
// Output bundles to ../static so the FastAPI backend serves them as the SPA.
// Dev server proxies /api to the backend on :8000.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: path.resolve(import.meta.dirname, '../static'),
    emptyOutDir: true,
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('react-dom') || id.includes('/react/') || id.includes('react-router') || id.includes('scheduler'))
            return 'vendor-react'
          if (id.includes('lightweight-charts')) return 'vendor-charts'
          if (id.includes('recharts') || id.includes('/d3-') || id.includes('victory')) return 'vendor-recharts'
          if (id.includes('react-markdown') || id.includes('remark') || id.includes('micromark') || id.includes('mdast') || id.includes('hast'))
            return 'vendor-markdown'
          if (id.includes('@tanstack')) return 'vendor-table'
          return undefined
        },
      },
    },
  },
})
