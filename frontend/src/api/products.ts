import { apiClient } from './client'
import type { Product, ProductListResponse } from '../types'

export const productsApi = {
  list: (page = 1, pageSize = 20): Promise<ProductListResponse> =>
    apiClient.get(`/api/products?page=${page}&page_size=${pageSize}`).then(r => r.data),
  get: (id: string): Promise<Product> =>
    apiClient.get(`/api/products/${id}`).then(r => r.data),
}
