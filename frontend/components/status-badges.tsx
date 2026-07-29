import { Badge } from "@/components/ui/badge";
import { statusLabel } from "@/lib/format";
import type {
  AgentType,
  CheckStatus,
  TaskPriority,
  TaskStatus,
  WorkerStatus,
} from "@/types/api";

// The palette is four inks, so every status maps onto one of them rather than
// getting its own hue: orange = in progress, teal = done/confirmed,
// violet = informational, gold = waiting/warning, destructive = failed.
const TASK_STATUS_STYLES: Record<TaskStatus, string> = {
  queued: "tag-riso-muted",
  starting: "tag-riso-violet",
  running: "tag-riso-orange",
  waiting_for_user: "tag-riso-gold",
  waiting_for_approval: "tag-riso-gold",
  testing: "tag-riso-violet",
  needs_review: "tag-riso-gold",
  completed: "tag-riso-teal",
  blocked: "tag-riso-gold",
  failed: "tag-riso-destructive",
  cancelled: "tag-riso-muted",
  rejected: "tag-riso-destructive",
};

export function TaskStatusBadge({ status }: { status: TaskStatus }) {
  return <Badge className={TASK_STATUS_STYLES[status]}>{statusLabel(status)}</Badge>;
}

export function AgentBadge({ agent }: { agent: AgentType | null }) {
  if (!agent) return <span className="text-[color:var(--muted-foreground)]">—</span>;
  return (
    <Badge className={agent === "claude" ? "tag-riso-orange" : "tag-riso-teal"}>
      {agent}
    </Badge>
  );
}

const CHECK_STYLES: Record<CheckStatus, string> = {
  pending: "tag-riso-muted",
  running: "tag-riso-orange",
  passed: "tag-riso-teal",
  failed: "tag-riso-destructive",
  not_run: "tag-riso-muted",
};

export function CheckBadge({ status }: { status: CheckStatus }) {
  return <Badge className={CHECK_STYLES[status]}>{statusLabel(status)}</Badge>;
}

const PRIORITY_STYLES: Record<TaskPriority, string> = {
  low: "tag-riso-muted",
  normal: "tag-riso-muted",
  high: "tag-riso-gold",
  critical: "tag-riso-destructive",
};

export function PriorityBadge({ priority }: { priority: TaskPriority }) {
  return <Badge className={PRIORITY_STYLES[priority]}>{priority}</Badge>;
}

const WORKER_STYLES: Record<WorkerStatus, string> = {
  online: "tag-riso-teal",
  offline: "tag-riso-destructive",
  degraded: "tag-riso-gold",
  unknown: "tag-riso-muted",
};

export function WorkerStatusBadge({ status }: { status: WorkerStatus }) {
  return <Badge className={WORKER_STYLES[status]}>{status}</Badge>;
}

// OpenACP session states come straight from its API as free-form strings, so
// unlike the others this map needs a fallback rather than a Record<Union, …>.
const SESSION_STYLES: Record<string, string> = {
  active: "tag-riso-teal",
  initializing: "tag-riso-gold",
  error: "tag-riso-destructive",
};

export function SessionStatusBadge({ status }: { status: string }) {
  return <Badge className={SESSION_STYLES[status] ?? "tag-riso-muted"}>{status}</Badge>;
}

export function AvailabilityDot({ available, label }: { available: boolean; label: string }) {
  return (
    <span className="font-mono-ui inline-flex items-center gap-1.5 text-[11px] text-[color:var(--muted-foreground)]">
      <span
        className="h-2 w-2 rounded-full"
        style={{
          background: available ? "var(--accent-teal)" : "var(--background-3)",
          boxShadow: available ? "1px 1px 0 var(--riso-teal)" : "none",
        }}
        aria-hidden
      />
      {label}
    </span>
  );
}
