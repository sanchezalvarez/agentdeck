"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { AvailabilityDot, WorkerStatusBadge } from "@/components/status-badges";
import { apiGet } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { useLive } from "@/lib/use-live";
import type { Worker } from "@/types/api";

export default function WorkersPage() {
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setWorkers(await apiGet<Worker[]>("/api/workers"));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load workers");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);
  useLive(refresh);

  return (
    <div className="space-y-4">
      <h1 className="riso-title animate-ink-in">Workers</h1>
      {error && <p className="text-sm text-[color:var(--destructive)]">{error}</p>}
      <Card>
        <CardContent className="p-0 pb-2">
          {workers.length === 0 ? (
            <p className="px-4 py-6 text-sm text-[color:var(--muted-foreground)]">
              No workers registered. Send a heartbeat with{" "}
              <code>agent-report heartbeat --worker &quot;Rembrosoft-Main-PC&quot;</code>.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Hostname</TableHead>
                  <TableHead>OS</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead>Last heartbeat</TableHead>
                  <TableHead>Capabilities</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {workers.map((worker) => {
                  const effective = worker.effective_status ?? worker.status;
                  return (
                    <TableRow
                      key={worker.id}
                      className={worker.is_stale ? "bg-[color:color-mix(in_srgb,var(--destructive)_10%,transparent)]/60" : undefined}
                    >
                      <TableCell className="font-medium text-[color:var(--foreground)]">{worker.name}</TableCell>
                      <TableCell className="font-mono text-xs text-[color:var(--muted-foreground)]">
                        {worker.hostname ?? "—"}
                      </TableCell>
                      <TableCell className="text-[color:var(--muted-foreground)]">
                        {worker.operating_system ?? "—"}
                      </TableCell>
                      <TableCell>
                        <WorkerStatusBadge status={effective} />
                        {worker.is_stale && (
                          <span className="ml-2 text-xs font-medium text-[color:var(--destructive)]">stale</span>
                        )}
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-[color:var(--muted-foreground)]">
                        {formatRelative(worker.last_seen_at)}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-3">
                          <AvailabilityDot available={worker.claude_available} label="Claude" />
                          <AvailabilityDot available={worker.codex_available} label="Codex" />
                          <AvailabilityDot available={worker.unity_available} label="Unity" />
                          <AvailabilityDot available={worker.unity_mcp_available} label="Unity MCP" />
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
