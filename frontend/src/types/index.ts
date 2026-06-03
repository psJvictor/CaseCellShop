export interface Product {
  id: string
  erp_id: string
  name: string
  description: string | null
  price: string  // comes as string from API (Decimal)
  image_url: string | null
  model_compat: string | null
  stock_available: number
  last_synced_at: string
}

export interface ProductListResponse {
  items: Product[]
  total: number
  page: number
  page_size: number
}

export interface CartItem {
  cart_item_id: string
  product_id: string
  product_name: string
  quantity: number
  unit_price: string
  reservation_id: string | null
  expires_at: string | null
}

export interface CartDetail {
  cart_id: string
  session_id: string
  items: CartItem[]
  total_amount: string
}

export interface OrderItem {
  product_name: string
  quantity: number
  unit_price: string
}

export interface Order {
  order_id: string
  status: string
  customer_name: string
  customer_email: string
  total_amount: string
  items: OrderItem[]
  created_at: string
}

export interface CheckoutFormData {
  customer_name: string
  customer_email: string
  customer_address: string
}

export interface ApiError {
  detail: string
  available?: number
}
