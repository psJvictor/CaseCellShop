export function StockBadge({ available }: { available: number }) {
  if (available === 0) {
    return <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">Sem estoque</span>
  }
  if (available <= 3) {
    return <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">Últimas {available} unidades</span>
  }
  return <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">Em estoque</span>
}
