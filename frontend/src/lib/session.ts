import type { TokenResponse } from '../types'

const SESSION_KEY = 'jarvis.session'

export function readSession(): TokenResponse | null {
  const value = sessionStorage.getItem(SESSION_KEY)
  if (!value) return null

  try {
    return JSON.parse(value) as TokenResponse
  } catch {
    sessionStorage.removeItem(SESSION_KEY)
    return null
  }
}

export function saveSession(tokens: TokenResponse): void {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(tokens))
}

export function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY)
}
