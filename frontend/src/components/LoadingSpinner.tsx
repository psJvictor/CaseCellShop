export function LoadingSpinner({ size = 'md', label = 'Carregando...' }: { size?: 'sm' | 'md' | 'lg'; label?: string }) {
  const sizeClass = { sm: 'h-4 w-4', md: 'h-8 w-8', lg: 'h-12 w-12' }[size]
  return (
    <div className="flex flex-col items-center gap-2">
      <div className={`animate-spin rounded-full border-2 border-gray-300 border-t-blue-600 ${sizeClass}`} />
      {label && <p className="text-sm text-gray-500">{label}</p>}
    </div>
  )
}
