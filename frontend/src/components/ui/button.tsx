import * as React from "react"

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, ...props }, ref) => {
    return (
      <button
        className={`
          inline-flex items-center justify-center rounded-md text-sm font-medium
          transition-colors focus-visible:outline-none
          disabled:pointer-events-none disabled:opacity-50
          bg-purple-600 text-white hover:bg-purple-700
          h-10 px-4 py-2
          ${className || ''}
        `}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button }
