import * as React from "react";
import { cn } from "@/lib/utils";

// .input-riso mirrors .btn-tactile: 1.5px border, 4px radius, 11px mono.
// ctl-md keeps it in the same height bucket as buttons standing next to it.
export function Input({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("input-riso ctl-md w-full", className)} {...props} />;
}
