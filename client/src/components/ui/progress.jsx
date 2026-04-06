import * as React from "react"
import { cn } from "@/lib/utils"

const Progress = React.forwardRef(({ className, value = 0, ...props }, ref) => {
  const safeValue = Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0

  return (
    <div
      ref={ref}
      className={cn("relative h-4 w-full overflow-hidden rounded-full bg-secondary", className)}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={safeValue}
      {...props}
    >
      <div
        className="h-full w-full flex-1 bg-primary transition-all"
        style={{ transform: `translateX(-${100 - safeValue}%)` }}
      />
    </div>
  )
})

Progress.displayName = "Progress"

export { Progress }
