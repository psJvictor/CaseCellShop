import { useState } from 'react'
import type { CartItem as CartItemType } from '../types'
import { LoadingSpinner } from './LoadingSpinner'
import { useCart } from '../hooks/useCart'

export function CartItemRow({ item }: { item: CartItemType }) {
  const { removeItem } = useCart()
  const [error, setError] = useState<string | null>(null)

  const handleRemove = async () => {
    try {
      await removeItem.mutateAsync(item.product_id)
    } catch (e: unknown) {
      const err = e as { detail?: string }
      setError(err.detail || 'Erro ao remover item')
    }
  }

  const subtotal = (parseFloat(item.unit_price) * item.quantity).toFixed(2).replace('.', ',')

  return (
    <div className="flex items-center gap-4 rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex-1">
        <p className="font-medium text-gray-900">{item.product_name}</p>
        <p className="text-sm text-gray-500">
          {item.quantity}x R$ {parseFloat(item.unit_price).toFixed(2).replace('.', ',')}
        </p>
        {item.expires_at && (
          <p className="text-xs text-amber-600 mt-1">
            Reserva expira em breve
          </p>
        )}
        {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
      </div>
      <div className="text-right">
        <p className="font-semibold text-gray-900">R$ {subtotal}</p>
        <button
          onClick={handleRemove}
          disabled={removeItem.isPending}
          className="mt-1 text-red-500 hover:text-red-700 disabled:opacity-50"
          aria-label="Remover item"
        >
          {removeItem.isPending ? <LoadingSpinner size="sm" label="" /> : '🗑'}
        </button>
      </div>
    </div>
  )
}
