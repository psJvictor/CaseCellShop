import { useState } from 'react'
import { v4 as uuidv4 } from 'uuid'

const SESSION_KEY = 'casecell_session_id'

/**
 * Module-level singleton — resolved once per page load.
 *
 * Because useSession() is called inside every ProductCard (one per product),
 * we can't rely on useEffect (async) to read/write localStorage: all instances
 * would race, each seeing an empty localStorage, generating different UUIDs
 * and creating different carts. The item would be added to cart A while the
 * CartPage reads cart B.
 *
 * Instead we resolve the session_id synchronously at module import time so
 * every component gets the exact same string on the very first render.
 */
let _resolvedSessionId: string = (() => {
  try {
    const existing = localStorage.getItem(SESSION_KEY)
    if (existing) return existing
    const fresh = uuidv4()
    localStorage.setItem(SESSION_KEY, fresh)
    return fresh
  } catch {
    // localStorage unavailable (private browsing restrictions, etc.)
    return uuidv4()
  }
})()

/** Return the current session id, creating one if needed. */
export function getSessionId(): string {
  return _resolvedSessionId
}

/** Clear the session after checkout so the next purchase starts fresh. */
export function clearSession(): void {
  try {
    localStorage.removeItem(SESSION_KEY)
  } catch {
    // ignore
  }
  _resolvedSessionId = uuidv4()
  try {
    localStorage.setItem(SESSION_KEY, _resolvedSessionId)
  } catch {
    // ignore
  }
}

/**
 * Hook that exposes the stable session id.
 * sessionId is always a non-null string — no loading state needed.
 */
export function useSession() {
  // useState with lazy initializer: runs once per component mount,
  // but always returns the same module-level value.
  const [sessionId] = useState<string>(() => _resolvedSessionId)
  return { sessionId }
}
