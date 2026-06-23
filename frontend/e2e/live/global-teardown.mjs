import { stopLiveStack } from './compose-env.mjs'

export default async function globalTeardown() {
  if (process.env.PLAYWRIGHT_LIVE_SKIP_STACK === '1') {
    return
  }
  await stopLiveStack()
}