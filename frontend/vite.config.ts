import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

export function createViteConfig(mode: string) {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = env.VITE_DEV_API_PROXY_TARGET || 'http://127.0.0.1:8000'
  const apiProxy = {
    '/api': {
      target: proxyTarget,
      changeOrigin: true,
    },
  }

  return {
    plugins: [
      vue(),
      vueDevTools(),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks(id: string) {
            if (!id.includes('node_modules')) {
              return undefined
            }
            if (id.includes('element-plus') || id.includes('@element-plus')) {
              return 'element-plus'
            }
            if (
              id.includes('/vue/') ||
              id.includes('\\vue\\') ||
              id.includes('vue-router') ||
              id.includes('/pinia/') ||
              id.includes('\\pinia\\')
            ) {
              return 'vue-vendor'
            }
            if (id.includes('mammoth') || id.includes('xlsx') || id.includes('markdown-it')) {
              return 'doc-preview'
            }
            return 'vendor'
          },
        },
      },
    },
    server: {
      proxy: apiProxy,
    },
    preview: {
      proxy: apiProxy,
    },
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => createViteConfig(mode))
