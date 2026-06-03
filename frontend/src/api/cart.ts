import { apiClient } from './client'
import type { CartDetail } from '../types'

export const cartApi = {
  create: (sessionId?: string) =>
    apiClient.post('/api/cart', { session_id: sessionId }).then(r => r.data as { cart_id: string; session_id: string }),

  get: (sessionId: string): Promise<CartDetail | null> =>
    apiClient
      .get(`/api/cart/${sessionId}`)
      .then(r => r.data as CartDetail)
      .catch(err => {
        // 404 = cart not yet created on backend (user hasn't added any item).
        // Treat as empty cart, not as an error.
        if (err?.status === 404) return null
        throw err
      }),

  addItem: (sessionId: string, productId: string, quantity: number) =>
    apiClient.post(`/api/cart/${sessionId}/items`, { product_id: productId, quantity }).then(r => r.data),

  removeItem: (sessionId: string, productId: string) =>
    apiClient.delete(`/api/cart/${sessionId}/items/${productId}`),
}
