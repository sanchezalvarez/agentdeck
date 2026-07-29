"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import type { HealthResponse, Worker } from "@/types/api";

function Indicator({ ok, label }: { ok: boolean | null; label: string }) {
  const ink =
    ok === null ? "var(--background-3)" : ok ? "var(--accent-teal)" : "var(--destructive)";
  return (
    <span className="font-mono-ui inline-flex items-center gap-1.5 text-[11px] uppercase tracking-[0.04em] text-[color:var(--muted-foreground)]">
      <span
        className="h-2.5 w-2.5 rounded-full"
        style={{ background: ink, boxShadow: `1.5px 1.5px 0 color-mix(in srgb, ${ink} 30%, transparent)` }}
        aria-hidden
      />
      {label}
    </span>
  );
}

export function Topbar() {
  const [health, setHealth] = useState<boolean | null>(null);
  const [version, setVersion] = useState<string>("");
  const [workersOnline, setWorkersOnline] = useState<boolean | null>(null);

  const refresh = useCallback(async () => {
    try {
      const body = await apiGet<HealthResponse>("/api/health");
      setHealth(body.status === "ok");
      setVersion(body.version);
    } catch {
      setHealth(false);
    }
    try {
      const workers = await apiGet<Worker[]>("/api/workers");
      setWorkersOnline(
        workers.length > 0 &&
          workers.some((w) => w.effective_status === "online"),
      );
    } catch {
      setWorkersOnline(null);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 30000);
    return () => clearInterval(timer);
  }, [refresh]);

  return (
    <header className="surface-noise-flat flex h-14 shrink-0 items-center justify-between border-b border-[color:var(--border-strong)] bg-[color:var(--background-2)] px-6">
      <div className="riso-section-label">Local agent monitoring</div>
      <div className="flex items-center gap-5">
        <Indicator ok={health} label={health === false ? "Backend offline" : "Backend"} />
        <Indicator
          ok={workersOnline}
          label={workersOnline === false ? "No worker online" : "Workers"}
        />
        {version && (
          <span className="font-mono-ui text-[10px] text-[color:var(--muted-foreground)]">
            v{version}
          </span>
        )}
      </div>
    </header>
  );
}
