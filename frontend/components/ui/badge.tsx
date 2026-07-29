import * as React from "react";
import { cn } from "@/lib/utils";

// .tag-riso is the pill tag from the design system: mono, uppercase-friendly,
// 1px token border. Colour comes from a tag-riso-* variant, never a raw class.
export function Badge({
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn("tag-riso", className)} {...props} />;
}
