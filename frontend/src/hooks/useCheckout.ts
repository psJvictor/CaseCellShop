import { useRef } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { v4 as uuidv4 } from 'uuid'
import { ordersApi } from '../api/orders'
import type { CheckoutFormData } from '../types'
import { useSession, clearSession } from './useSession'

export function useCheckout() {
  // Stable idempotency key for this checkout attempt.
  // If user retries after network failure, same key is sent → backend returns existing order.
  const idempotencyKey = useRef(uuidv4())
  const qc = useQueryClient()
  const { sessionId } = useSession()

  const mutation = useMutation({
    mutationFn: (formData: CheckoutFormData) =>
      ordersApi.checkout({
        ...formData,
        idempotency_key: idempotencyKey.current,
        session_id: sessionId,
      }),
    onSuccess: () => {
      // Wipe the cart cache and rotate the session so the next purchase starts fresh
      qc.removeQueries({ queryKey: ['cart'] })
      clearSession()
      idempotencyKey.current = uuidv4()
    },
  })

  return mutation
}
