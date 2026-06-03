import { Link } from 'react-router-dom'
import { useCart } from '../hooks/useCart'

export function Navbar() {
  const { cartQuery } = useCart()
  const itemCount = cartQuery.data?.items?.length ?? 0

  return (
    <nav className="sticky top-0 z-10 border-b border-gray-200 bg-white shadow-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link to="/" className="text-xl font-bold text-blue-600">CaseCellShop</Link>
        <Link to="/cart" className="relative flex items-center gap-2 rounded-lg px-3 py-2 text-gray-700 hover:bg-gray-100">
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
          </svg>
          <span className="text-sm font-medium">Carrinho</span>
          {itemCount > 0 && (
            <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white">
              {itemCount}
            </span>
          )}
        </Link>
      </div>
    </nav>
  )
}
