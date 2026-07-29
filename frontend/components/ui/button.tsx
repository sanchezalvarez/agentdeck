import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

// Every button starts from .btn-tactile — never from raw utility classes.
// Sizes are the 22/26/32px buckets from DESIGN_RULES.md; controls sharing a
// horizontal row must share a bucket.
const buttonVariants = cva("btn-tactile", {
  variants: {
    variant: {
      default: "btn-tactile-orange",
      destructive: "btn-tactile-destructive",
      outline: "btn-tactile-outline",
      ghost: "btn-tactile-ghost",
      success: "btn-tactile-teal",
      info: "btn-tactile-violet",
    },
    size: {
      sm: "ctl-sm",
      default: "ctl-md",
      lg: "ctl-lg",
    },
  },
  defaultVariants: { variant: "default", size: "default" },
});

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return (
    <button className={cn(buttonVariants({ variant, size }), className)} {...props} />
  );
}
