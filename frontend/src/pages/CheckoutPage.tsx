import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useCheckout } from '../hooks/useCheckout'
import { useCart } from '../hooks/useCart'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorBanner } from '../components/ErrorBanner'
import type { Order, CheckoutFormData } from '../types'

export function CheckoutPage() {
  const checkout = useCheckout()
  const { cartQuery } = useCart()
  const [form, setForm] = useState<CheckoutFormData>({
    customer_name: '',
    customer_email: '',
    customer_address: '',
  })
  const [completedOrder, setCompletedOrder] = useState<Order | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      const order = await checkout.mutateAsync(form)
      setCompletedOrder(order)
    } catch (err: unknown) {
      const apiErr = err as { detail?: string }
      setError(apiErr.detail || 'Erro ao processar pedido. Tente novamente.')
    }
  }

  if (completedOrder) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-8">
        <div className="rounded-xl border border-green-200 bg-green-50 p-8 text-center">
          <div className="text-5xl mb-4">✅</div>
          <h1 className="text-2xl font-bold text-green-800">Pedido Confirmado!</h1>
          <p className="text-green-700 mt-2">Obrigado, {completedOrder.customer_name}!</p>
          <p className="text-sm text-gray-500 mt-1">Pedido #{completedOrder.order_id.slice(0, 8).toUpperCase()}</p>

          <div className="mt-6 rounded-lg border border-green-200 bg-white p-4 text-left">
            <h2 className="font-semibold text-gray-700 mb-3">Itens do pedido</h2>
            {completedOrder.items.map((item, i) => (
              <div key={i} className="flex justify-between text-sm py-1">
                <span className="text-gray-700">{item.quantity}x {item.product_name}</span>
                <span className="text-gray-900 font-medium">
                  R$ {(parseFloat(item.unit_price) * item.quantity).toFixed(2).replace('.', ',')}
                </span>
              </div>
            ))}
            <div className="mt-3 border-t pt-3 flex justify-between font-bold">
              <span>Total</span>
              <span>R$ {parseFloat(completedOrder.total_amount).toFixed(2).replace('.', ',')}</span>
            </div>
          </div>

          <Link to="/" className="mt-6 inline-block rounded-lg bg-blue-600 px-6 py-2 text-white font-medium hover:bg-blue-700">
            Continuar Comprando
          </Link>
        </div>
      </main>
    )
  }

  const cart = cartQuery.data

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Finalizar Compra</h1>

      <div className="grid gap-6 md:grid-cols-5">
        <form onSubmit={handleSubmit} className="md:col-span-3 flex flex-col gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nome completo</label>
            <input
              type="text"
              required
              minLength={2}
              value={form.customer_name}
              onChange={e => setForm(f => ({ ...f, customer_name: e.target.value }))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              placeholder="João Silva"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">E-mail</label>
            <input
              type="email"
              required
              value={form.customer_email}
              onChange={e => setForm(f => ({ ...f, customer_email: e.target.value }))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              placeholder="joao@email.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Endereço de entrega</label>
            <textarea
              required
              minLength={5}
              rows={3}
              value={form.customer_address}
              onChange={e => setForm(f => ({ ...f, customer_address: e.target.value }))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none resize-none"
              placeholder="Rua X, 123, Bairro, Cidade - SP, 01000-000"
            />
          </div>

          {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

          <button
            type="submit"
            disabled={checkout.isPending}
            className="w-full rounded-lg bg-blue-600 py-3 text-white font-semibold hover:bg-blue-700 disabled:opacity-70 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {checkout.isPending ? (
              <>
                <LoadingSpinner size="sm" label="" />
                Processando pedido...
              </>
            ) : (
              'Confirmar Pedido'
            )}
          </button>

          <p className="text-xs text-gray-500 text-center">
            Ao confirmar, você concorda com os termos de uso. Pagamento não é necessário neste MVP.
          </p>
        </form>

        {cart && cart.items.length > 0 && (
          <div className="md:col-span-2">
            <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
              <h2 className="font-semibold text-gray-700 mb-3">Resumo do pedido</h2>
              {cart.items.map((item) => (
                <div key={item.cart_item_id} className="flex justify-between text-sm py-1">
                  <span className="text-gray-700 truncate">{item.quantity}x {item.product_name}</span>
                  <span className="text-gray-900 font-medium ml-2">
                    R$ {(parseFloat(item.unit_price) * item.quantity).toFixed(2).replace('.', ',')}
                  </span>
                </div>
              ))}
              <div className="mt-3 border-t pt-3 flex justify-between font-bold">
                <span>Total</span>
                <span>R$ {parseFloat(cart.total_amount).toFixed(2).replace('.', ',')}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  )
}
