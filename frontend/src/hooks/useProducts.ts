import { useQuery } from '@tanstack/react-query'
import { productsApi } from '../api/products'

export function useProducts(page = 1) {
  return useQuery({
    queryKey: ['products', page],
    queryFn: () => productsApi.list(page),
    staleTime: 30_000, // 30s — prevents refetch on every navigation
  })
}
