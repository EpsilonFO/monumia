import * as React from "react"
import { Slider as SliderPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

function Slider({
  className,
  ...props
}: React.ComponentProps<typeof SliderPrimitive.Root>) {
  return (
    <SliderPrimitive.Root
      data-slot="slider"
      className={cn(
        "relative flex w-full touch-none select-none items-center data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        className
      )}
      {...props}
    >
      <SliderPrimitive.Track
        data-slot="slider-track"
        className="relative h-1.5 w-full grow overflow-hidden rounded-full bg-border"
      >
        <SliderPrimitive.Range
          data-slot="slider-range"
          className="absolute h-full rounded-full"
          style={{ background: "linear-gradient(90deg, var(--accent), var(--orange-vif))" }}
        />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb
        data-slot="slider-thumb"
        className="block size-4 shrink-0 rounded-full border-2 bg-card shadow-sm transition-[color,box-shadow] outline-none focus-visible:ring-4 focus-visible:ring-[color-mix(in_srgb,var(--accent)_28%,transparent)] hover:scale-110"
        style={{ borderColor: "var(--accent)" }}
      />
    </SliderPrimitive.Root>
  )
}

export { Slider }
