import { useEffect, useRef } from 'react'
import clsx from 'clsx'

interface Props {
  text: string
  isStreaming: boolean
  className?: string
  maxHeight?: string
}

export default function StreamingText({ text, isStreaming, className, maxHeight = '200px' }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isStreaming && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [text, isStreaming])

  return (
    <div
      ref={containerRef}
      className={clsx('overflow-y-auto text-sm leading-relaxed whitespace-pre-wrap', className)}
      style={{ maxHeight }}
    >
      {text}
      {isStreaming && (
        <span className="inline-block w-2 h-4 ml-0.5 bg-brand-500 animate-pulse rounded-sm align-text-bottom" />
      )}
    </div>
  )
}
