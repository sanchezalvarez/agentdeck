import * as React from "react";
import { cn } from "@/lib/utils";

// A native <select> styled as a tactile control. DESIGN_RULES.md: name-bearing
// dropdowns get min-width 200px so the trigger never ends up narrower than its
// options and the layout stops jittering on selection change.
export function Select({
  className,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn("btn-tactile ctl-md min-w-[200px] justify-between", className)}
      {...props}
    />
  );
}
