import { fileURLToPath } from 'node:url'
import { mergeConfig, defineConfig, configDefaults } from 'vitest/config'
import { createViteConfig } from './vite.config'

export default mergeConfig(
  createViteConfig('test'),
  defineConfig({
    test: {
      environment: 'jsdom',
      exclude: [...configDefaults.exclude, 'e2e/**'],
      root: fileURLToPath(new URL('./', import.meta.url)),
      // W13-C: prefer shared mount helper under tests/helpers/mountApp.ts
      coverage: {
        provider: 'v8',
        reporter: ['text', 'json-summary'],
        include: ['src/**/*.{ts,vue}'],
        exclude: ['src/**/*.test.ts', 'src/**/*.spec.ts', 'e2e/**'],
      },
    },
  }),
)
