import { useState } from 'react'
import type { Product } from '../types'
import { StockBadge } from './StockBadge'
import { LoadingSpinner } from './LoadingSpinner'
import { ErrorBanner } from './ErrorBanner'
import { useCart } from '../hooks/useCart'

interface ProductCardProps {
  product: Product
}

export function ProductCard({ product }: ProductCardProps) {
  const { addItem } = useCart()
  const [error, setError] = useState<string | null>(null)
  const [added, setAdded] = useState(false)

  const handleAddToCart = async () => {
    setError(null)
    try {
      await addItem.mutateAsync({ productId: product.id, quantity: 1 })
      setAdded(true)
      setTimeout(() => setAdded(false), 2000)
    } catch (e: unknown) {
      const err = e as { detail?: string }
      setError(err.detail || 'Erro ao adicionar ao carrinho')
    }
  }

  const isOutOfStock = product.stock_available === 0
  const isPending = addItem.isPending

  return (
    <div className="flex flex-col rounded-xl border border-gray-200 bg-white shadow-sm transition-shadow hover:shadow-md overflow-hidden">
      <div className="relative">
        <img
          src={product.image_url || 'https://placehold.co/400x400/e5e7eb/9ca3af?text=Sem+Foto'}
          alt={product.name}
          className="h-48 w-full object-cover"
        />
        <div className="absolute top-2 right-2">
          <StockBadge available={product.stock_available} />
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-2 p-4">
        <h3 className="font-semibold text-gray-900 leading-tight">{product.name}</h3>
        {product.model_compat && (
          <p className="text-xs text-gray-500">{product.model_compat}</p>
        )}
        {product.description && (
          <p className="text-sm text-gray-600 line-clamp-2">{product.description}</p>
        )}

        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        <div className="mt-auto flex items-center justify-between pt-2">
          <span className="text-lg font-bold text-gray-900">
            R$ {parseFloat(product.price).toFixed(2).replace('.', ',')}
          </span>

          <button
            onClick={handleAddToCart}
            disabled={isOutOfStock || isPending}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all
              ${isOutOfStock
                ? 'cursor-not-allowed bg-gray-100 text-gray-400'
                : added
                ? 'bg-green-500 text-white'
                : 'bg-blue-600 text-white hover:bg-blue-700 active:scale-95 disabled:opacity-70'
              }`}
          >
            {isPending ? (
              <LoadingSpinner size="sm" label="" />
            ) : added ? (
              '✓ Adicionado'
            ) : isOutOfStock ? (
              'Indisponível'
            ) : (
              'Adicionar'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
