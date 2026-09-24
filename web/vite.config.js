import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import stylex from '@stylexjs/unplugin/vite'

export default defineConfig({
  plugins: [
    react(),
    stylex({ useCSSLayers: true }),
  ],
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000' },
  },
})
