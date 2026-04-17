import { clsx } from "clsx"

interface BadgeProps {
  variant: "green" | "saffron" | "muted"
  children: React.ReactNode
}

export function Badge({ variant, children }: BadgeProps) {
  const variantClasses = {
    green: "bg-green-100 text-green-800 border-green-200",
    saffron: "bg-saffron-100 text-saffron-800 border-saffron-200", 
    muted: "bg-gray-100 text-gray-700 border-gray-200"
  }

  return (
    <span className={clsx(
      "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border",
      variantClasses[variant]
    )}>
      {children}
    </span>
  )
}
