import { ButtonHTMLAttributes, forwardRef } from 'react'
import clsx from 'clsx'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled}
        className={clsx(
          'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2',
          {
            'bg-brand-600 text-white hover:bg-brand-700 focus:ring-brand-500 shadow-sm': variant === 'primary',
            'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 focus:ring-brand-500': variant === 'secondary',
            'text-gray-600 hover:text-gray-900 hover:bg-gray-100 focus:ring-gray-500': variant === 'ghost',
            'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500': variant === 'danger',
            'px-3 py-1.5 text-sm': size === 'sm',
            'px-5 py-2.5 text-sm': size === 'md',
            'px-8 py-3.5 text-base': size === 'lg',
            'opacity-50 cursor-not-allowed': disabled,
          },
          className,
        )}
        {...props}
      >
        {children}
      </button>
    )
  },
)
Button.displayName = 'Button'
export default Button
