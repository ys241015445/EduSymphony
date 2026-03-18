import { InputHTMLAttributes, forwardRef } from 'react'
import clsx from 'clsx'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className, ...props }, ref) => {
    return (
      <div className="space-y-1.5">
        {label && <label className="block text-sm font-medium text-gray-700">{label}</label>}
        <input
          ref={ref}
          className={clsx(
            'w-full px-4 py-2.5 rounded-lg border text-sm transition-colors duration-200',
            'focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500',
            'placeholder:text-gray-400',
            error ? 'border-red-300 bg-red-50' : 'border-gray-300 bg-white',
            className,
          )}
          {...props}
        />
        {error && <p className="text-xs text-red-500">{error}</p>}
      </div>
    )
  },
)
Input.displayName = 'Input'
export default Input
