let accessToken: string | null = null

let unauthorizedHandler: (() => void) | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(nextAccessToken: string): void {
  accessToken = nextAccessToken
}

export function clearAuthSession(): void {
  accessToken = null
}

export function setUnauthorizedHandler(handler: () => void): void {
  unauthorizedHandler = handler
}

export function notifyUnauthorized(): void {
  unauthorizedHandler?.()
}
