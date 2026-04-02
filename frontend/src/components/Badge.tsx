interface BadgeProps {
  children: React.ReactNode
  variant?: 'admit' | 'observe' | 'discharge' | 'unknown' | 'edited' | 'ai' | 'neutral'
}

const variantClass: Record<string, string> = {
  admit: 'bg-red-100 text-red-800 border border-red-200',
  observe: 'bg-yellow-100 text-yellow-800 border border-yellow-200',
  discharge: 'bg-green-100 text-green-800 border border-green-200',
  unknown: 'bg-gray-100 text-gray-600 border border-gray-200',
  edited: 'bg-amber-100 text-amber-800 border border-amber-300',
  ai: 'bg-blue-50 text-blue-700 border border-blue-200',
  neutral: 'bg-slate-100 text-slate-600 border border-slate-200',
}

export function Badge({ children, variant = 'neutral' }: BadgeProps) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${variantClass[variant]}`}>
      {children}
    </span>
  )
}
