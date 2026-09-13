let accessToken: string | null = null
let epoch = 0
let controller = new AbortController()
let unauthorizedHandler: (() => void) | null = null
const listeners = new Set<() => void>()

export function getSessionEpoch(): number { return epoch }
export function getSessionSignal(): AbortSignal { return controller.signal }
export function isCurrentSession(value: number): boolean { return value === epoch }
export function onSessionChange(listener: () => void): () => void {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}
export function getAccessToken(): string | null { return accessToken }
export function setAccessToken(next: string): void { accessToken = next }
export function clearAuthSession(): void {
  const previous = controller
  epoch += 1
  accessToken = null
  controller = new AbortController()
  previous.abort()
  listeners.forEach((listener) => listener())
}
export function setUnauthorizedHandler(handler: () => void): void { unauthorizedHandler = handler }
export function notifyUnauthorized(): void { unauthorizedHandler?.() }
