import { startLiveStack } from './compose-env.mjs'

export default async function globalSetup() {
  await startLiveStack()
}