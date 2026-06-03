import { Link } from 'react-router-dom'
import { useCart } from '../hooks/useCart'
import { CartItemRow } from '../components/CartItem'
import { LoadingSpinner } from '../components/LoadingSpinner'

export function CartPage() {
  const { cartQuery } = useCart()

  if (cartQuery.isLoading) {
    return (
      <div className="flex justify-center py-20">
        <LoadingSpinner size="lg" label="Carregando carrinho..." />
      </div>
    )
  }

  const cart = cartQuery.data

  if (!cart || cart.items.length === 0) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-8 text-center">
        <div className="rounded-xl border border-dashed border-gray-300 py-16">
          <p className="text-4xl mb-4">🛒</p>
          <h2 className="text-xl font-semibold text-gray-700">Seu carrinho está vazio</h2>
          <p className="text-gray-500 mt-2 mb-6">Adicione produtos para continuar</p>
          <Link to="/" className="rounded-lg bg-blue-600 px-6 py-2 text-white font-medium hover:bg-blue-700">
            Ver Produtos
          </Link>
        </div>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Meu Carrinho</h1>

      <div className="flex flex-col gap-3 mb-6">
        {cart.items.map((item) => (
          <CartItemRow key={item.cart_item_id} item={item} />
        ))}
      </div>

      <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
        <div className="flex justify-between items-center mb-4">
          <span className="text-lg font-semibold text-gray-700">Total</span>
          <span className="text-2xl font-bold text-gray-900">
            R$ {parseFloat(cart.total_amount).toFixed(2).replace('.', ',')}
          </span>
        </div>
        <Link
          to="/checkout"
          className="block w-full rounded-lg bg-blue-600 py-3 text-center text-white font-semibold hover:bg-blue-700"
        >
          Finalizar Compra
        </Link>
        <Link to="/" className="block mt-3 text-center text-sm text-blue-600 hover:underline">
          Continuar comprando
        </Link>
      </div>
    </main>
  )
}
