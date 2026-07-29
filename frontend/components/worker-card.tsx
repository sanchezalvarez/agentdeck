import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AvailabilityDot, WorkerStatusBadge } from "@/components/status-badges";
import { formatRelative } from "@/lib/format";
import type { Worker } from "@/types/api";

export function WorkerCard({ worker }: { worker: Worker }) {
  const effective = worker.effective_status ?? worker.status;
  const stale = worker.is_stale;
  return (
    // A stale worker gets the orange ink rather than a red surface — the
    // palette carries the warning, the card keeps its shape.
    <Card className={`animate-card-in ${stale ? "card-riso-orange" : ""}`}>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>{worker.name}</CardTitle>
        <WorkerStatusBadge status={effective} />
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <AvailabilityDot available={worker.claude_available} label="Claude" />
          <AvailabilityDot available={worker.codex_available} label="Codex" />
          <AvailabilityDot available={worker.unity_available} label="Unity" />
          <AvailabilityDot available={worker.unity_mcp_available} label="Unity MCP" />
        </div>
        <p className="font-mono-ui text-[10px] text-[color:var(--muted-foreground)]">
          Last heartbeat: {formatRelative(worker.last_seen_at)}
          {stale && <span className="ml-1 text-[color:var(--accent-gold)]">(stale)</span>}
        </p>
      </CardContent>
    </Card>
  );
}
