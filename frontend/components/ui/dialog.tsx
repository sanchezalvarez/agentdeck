"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  className?: string;
}

// DESIGN_RULES.md: flex-centered, max-height 85vh with internal scroll, 20px
// content padding, footer right-aligned with 8px gaps (see the callers).
export function Dialog({ open, onClose, title, children, className }: DialogProps) {
  React.useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[color:color-mix(in_srgb,var(--foreground)_45%,transparent)] p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          "card-riso card-riso-orange animate-card-in max-h-[85vh] w-full max-w-md overflow-y-auto p-5",
          className,
        )}
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="font-display mb-3 text-base text-[color:var(--foreground)]">{title}</h2>
        {children}
      </div>
    </div>
  );
}
