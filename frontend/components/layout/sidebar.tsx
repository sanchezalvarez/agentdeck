"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/tasks", label: "Tasks" },
  { href: "/projects", label: "Projects" },
  { href: "/workers", label: "Workers" },
  { href: "/openacp", label: "OpenACP" },
  { href: "/system", label: "System" },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="surface-noise-flat animate-column-in flex w-52 shrink-0 flex-col border-r border-[color:var(--border-strong)] bg-[color:var(--background-2)]">
      {/* The print registration strip: the three inks in thirds. */}
      <div className="h-[3px]" style={{ background: "var(--riso-strip)" }} aria-hidden />
      <div className="flex h-[53px] items-center border-b border-[color:var(--border)] px-4">
        <Link href="/" className="font-display text-sm text-[color:var(--foreground)]">
          Rembrosoft
          <span className="font-mono-ui block text-[10px] uppercase tracking-[0.08em] text-[color:var(--muted-foreground)]">
            Agent Hub
          </span>
        </Link>
      </div>
      <nav className="flex flex-col gap-1 p-3">
        {NAV.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "font-mono-ui rounded px-3 py-2 text-[11px] uppercase tracking-[0.06em] transition-all",
                active
                  ? "border-l-[3px] border-[color:var(--accent-orange)] bg-[color:color-mix(in_srgb,var(--accent-orange)_12%,transparent)] text-[color:var(--accent-orange)]"
                  : "border-l-[3px] border-transparent text-[color:var(--muted-foreground)] hover:bg-[color:var(--background-3)] hover:text-[color:var(--foreground)]",
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto p-4 text-[10px] leading-relaxed text-[color:var(--muted-foreground)]">
        Agents run via Discord / OpenACP. Agent Hub records their work and edits
        channel bindings — it never starts or stops them.
      </div>
    </aside>
  );
}
