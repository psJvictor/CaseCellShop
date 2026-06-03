import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { cartApi } from '../api/cart'
import { useSession } from './useSession'

export function useCart() {
  const { sessionId } = useSession()
  const qc = useQueryClient()

  const cartQuery = useQuery({
    queryKey: ['cart', sessionId],
    queryFn: () => cartApi.get(sessionId),
    retry: false,
  })

  const addItem = useMutation({
    mutationFn: ({ productId, quantity }: { productId: string; quantity: number }) =>
      cartApi.addItem(sessionId, productId, quantity),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cart', sessionId] }),
  })

  const removeItem = useMutation({
    mutationFn: (productId: string) => cartApi.removeItem(sessionId, productId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cart', sessionId] }),
  })

  return { cartQuery, addItem, removeItem }
}
