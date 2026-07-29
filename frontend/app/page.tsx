"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { WorkerCard } from "@/components/worker-card";
import { apiGet } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { useLive } from "@/lib/use-live";
import type { DaemonStatus, DashboardSummary, OpenAcpSession } from "@/types/api";

/** Sessions in these states are doing something or waiting to; the rest is history. */
const LIVE_STATES = ["active", "initializing"];

const STATUS_STYLES: Record<string, string> = {
  active: "tag-riso-teal",
  initializing: "tag-riso-violet",
  error: "tag-riso-destructive",
  finished: "tag-riso-muted",
};

function count(sessions: OpenAcpSession[], status: string) {
  return sessions.filter((s) => s.status === status).length;
}

export default function OverviewPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [sessions, setSessions] = useState<OpenAcpSession[]>([]);
  const [daemon, setDaemon] = useState<DaemonStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [summaryData, sessionData, daemonData] = await Promise.all([
        apiGet<DashboardSummary>("/api/dashboard/summary"),
        apiGet<OpenAcpSession[]>("/api/openacp/sessions"),
        apiGet<DaemonStatus>("/api/openacp/daemon-status"),
      ]);
      setSummary(summaryData);
      setSessions(sessionData);
      setDaemon(daemonData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);
  const liveState = useLive(refresh);

  if (error && !summary) {
    return (
      <p className="text-sm text-[color:var(--destructive)]">
        Could not load the dashboard: {error}. Is the backend running on port 8765?
      </p>
    );
  }
  if (!summary) {
    return <p className="text-sm text-[color:var(--muted-foreground)]">Loading…</p>;
  }

  const live = sessions.filter((s) => LIVE_STATES.includes(s.status));
  const cards = [
    { label: "Active", value: count(sessions, "active"), accent: "text-[color:var(--accent-teal)]" },
    { label: "Starting", value: count(sessions, "initializing"), accent: "text-[color:var(--accent-violet)]" },
    { label: "Errors", value: count(sessions, "error"), accent: "text-[color:var(--destructive)]" },
    { label: "Sessions total", value: sessions.length, accent: "text-[color:var(--foreground)]" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="riso-title animate-ink-in">Overview</h1>
        <span className="text-xs text-[color:var(--muted-foreground)]">
          {liveState === "live" ? "● live" : liveState === "polling" ? "○ polling" : "…"}
        </span>
      </div>

      {daemon && !daemon.running && (
        <p className="rounded border border-[color:color-mix(in_srgb,var(--accent-gold)_28%,transparent)] bg-[color:color-mix(in_srgb,var(--accent-gold)_12%,transparent)] px-3 py-2 text-sm text-[color:var(--accent-gold)]">
          OpenACP is not running, so there is nothing to report. Sessions live inside OpenACP —
          Agent Hub keeps no copy of them.
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {cards.map((card, index) => (
          <Card
            key={card.label}
            className="animate-card-in"
            style={{ animationDelay: `calc(${index} * 40ms)` }}
          >
            <CardContent className="p-4">
              <p className="font-mono-ui text-[10px] uppercase tracking-[0.06em] text-[color:var(--muted-foreground)]">
                {card.label}
              </p>
              <p className={`font-display mt-1 text-2xl ${card.accent}`}>{card.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Sessions</CardTitle>
          <span className="text-xs text-[color:var(--muted-foreground)]">
            {live.length} live of {sessions.length}
          </span>
        </CardHeader>
        <CardContent className="p-0 pb-2">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Project</TableHead>
                  <TableHead>Agent</TableHead>
                  <TableHead>Thread</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last activity</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sessions.map((session, index) => (
                  <TableRow
                    key={session.id}
                    className="animate-row-in"
                    style={{ animationDelay: `calc(${index} * 15ms)` }}
                  >
                    <TableCell className="whitespace-nowrap">
                      {session.project_name ?? (
                        <span
                          className="font-mono text-xs text-[color:var(--muted-foreground)]"
                          title={session.workspace}
                        >
                          {session.workspace || "—"}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-[color:var(--muted-foreground)]">
                      {session.agent}
                    </TableCell>
                    <TableCell className="max-w-md truncate" title={session.name}>
                      {session.name || <span className="text-[color:var(--muted-foreground)]">unnamed</span>}
                      {session.dangerous_mode && (
                        <Badge className="ml-2 tag-riso-destructive">bypass</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge className={STATUS_STYLES[session.status] ?? "tag-riso-muted"}>
                        {session.status}
                      </Badge>
                      {session.queue_depth > 0 && (
                        <span className="ml-2 text-xs text-[color:var(--muted-foreground)]">
                          queue {session.queue_depth}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs text-[color:var(--muted-foreground)]">
                      {formatRelative(session.last_active_at || null)}
                    </TableCell>
                  </TableRow>
                ))}
                {sessions.length === 0 && (
                  <TableRow>
                    <TableCell className="text-sm text-[color:var(--muted-foreground)]">
                      No sessions. Write in a thread under a bound Discord channel to start one.
                    </TableCell>
                    <TableCell />
                    <TableCell />
                    <TableCell />
                    <TableCell />
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <div>
        <h2 className="riso-section-label mb-3">Workers</h2>
        {summary.workers.length === 0 ? (
          <p className="text-sm text-[color:var(--muted-foreground)]">
            No workers yet — send a heartbeat with <code>agent-report heartbeat</code>.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {summary.workers.map((worker) => (
              <WorkerCard key={worker.id} worker={worker} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
