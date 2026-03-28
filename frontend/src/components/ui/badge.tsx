import * as React from "react"

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline"
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const baseClasses = "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold"
  
  const variantClasses = {
    default: "border-transparent bg-purple-600 text-white hover:bg-purple-700",
    secondary: "border-transparent bg-gray-700 text-gray-300 hover:bg-gray-600",
    destructive: "border-transparent bg-red-600 text-white hover:bg-red-700",
    outline: "border-gray-600 text-gray-300"
  }
  
  return (
    <div 
      className={`${baseClasses} ${variantClasses[variant]} ${className || ''}`} 
      {...props} 
    />
  )
}

export { Badge }
