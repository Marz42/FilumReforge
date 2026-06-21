import baseConfig from './playwright.config.ts'

export default {
  ...baseConfig,
  testMatch: undefined,
  testIgnore: ['live/**'],
}
