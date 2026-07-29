import * as React from "react";
import { cn } from "@/lib/utils";

// .card-riso brings the offset ink shadow and grain. Variants (-orange,
// -violet) change the shadow ink; -press makes the card interactive.
export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("card-riso", className)} {...props} />;
}

// 12px gaps between header/body/footer, 16px body padding — DESIGN_RULES.md.
export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1 p-4 pb-3", className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn("font-display text-base text-[color:var(--foreground)]", className)}
      {...props}
    />
  );
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-4 pt-0", className)} {...props} />;
}
