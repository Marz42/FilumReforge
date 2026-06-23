import { liveConfig, startLiveStack, waitForURL } from './compose-env.mjs'

export default async function globalSetup() {
  if (process.env.PLAYWRIGHT_LIVE_SKIP_STACK === '1') {
    const baseURL = process.env.PLAYWRIGHT_LIVE_BASE_URL || liveConfig.baseURL
    await waitForURL(`${baseURL}/login`, 'frontend login page')
    return
  }
  await startLiveStack()
}