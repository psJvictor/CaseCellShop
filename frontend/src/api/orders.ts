import { apiClient } from './client'
import type { Order, CheckoutFormData } from '../types'

export const ordersApi = {
  checkout: (data: CheckoutFormData & { idempotency_key: string; session_id: string }): Promise<Order> =>
    apiClient.post('/api/orders/checkout', data).then(r => r.data),
  get: (orderId: string): Promise<Order> =>
    apiClient.get(`/api/orders/${orderId}`).then(r => r.data),
}
