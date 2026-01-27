import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8060,
    // NOTE: Proxy configuration for development server
    // The proxy is used when running `npm run dev` locally
    // For LAN access on 192.168.1.16, the frontend at 192.168.1.16:8060
    // will make direct API calls to the backend at 192.168.1.16:8061
    // (not through the dev server proxy, which only works on localhost)
    // The VITE_API_BASE_URL env var handles both dev and production scenarios
    proxy: {
      '/api': {
        target: 'http://192.168.1.16:8061',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/api')
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true
  },
  resolve: {
    alias: {
      '@components': path.resolve(__dirname, './src/components'),
      '@pages': path.resolve(__dirname, './src/pages'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@utils': path.resolve(__dirname, './src/utils'),
      '@types': path.resolve(__dirname, './src/types'),
      '@store': path.resolve(__dirname, './src/store'),
      '@styles': path.resolve(__dirname, './src/styles')
    }
  }
})
