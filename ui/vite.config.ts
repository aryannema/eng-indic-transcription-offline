import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/transcribe/',
  build: {
    outDir: '../www/dist',
    emptyOutDir: true,
  },
})
