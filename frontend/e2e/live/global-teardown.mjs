import { stopLiveStack } from './compose-env.mjs'

export default async function globalTeardown() {
  await stopLiveStack()
}