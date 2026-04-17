interface SpinnerProps {
  size?: "sm" | "md" | "lg"
}

export function Spinner({ size = "md" }: SpinnerProps) {
  const sizeClasses = {
    sm: "w-3 h-3",
    md: "w-4 h-4", 
    lg: "w-6 h-6"
  }

  return (
    <div className={`animate-spin rounded-full border-2 border-saffron-200 border-t-saffron-600 ${sizeClasses[size]}`} />
  )
}
