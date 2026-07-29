"use client";

import { useRouter } from "next/navigation";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AgentBadge,
  CheckBadge,
  PriorityBadge,
  TaskStatusBadge,
} from "@/components/status-badges";
import { formatDateTime, formatDuration, formatRelative } from "@/lib/format";
import type { Task } from "@/types/api";

interface TaskTableProps {
  tasks: Task[];
  variant?: "full" | "compact";
  emptyMessage?: string;
}

export function TaskTable({ tasks, variant = "full", emptyMessage = "No tasks." }: TaskTableProps) {
  const router = useRouter();

  if (tasks.length === 0) {
    return <p className="px-3 py-6 text-sm text-[color:var(--muted-foreground)]">{emptyMessage}</p>;
  }

  const full = variant === "full";

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>ID</TableHead>
          <TableHead>Title</TableHead>
          <TableHead>Project</TableHead>
          <TableHead>Agent</TableHead>
          <TableHead>Status</TableHead>
          {full && <TableHead>Priority</TableHead>}
          {full && <TableHead>Started</TableHead>}
          <TableHead>Duration</TableHead>
          {full && <TableHead>Tests</TableHead>}
          {full && <TableHead>Build</TableHead>}
          {full && <TableHead>Requested by</TableHead>}
          {!full && <TableHead>Last activity</TableHead>}
        </TableRow>
      </TableHeader>
      <TableBody>
        {tasks.map((task) => (
          <TableRow
            key={task.id}
            className="cursor-pointer hover:bg-[color:var(--background-3)]"
            onClick={() => router.push(`/tasks/${task.public_id}`)}
          >
            <TableCell className="font-mono text-xs font-semibold text-[color:var(--foreground)]">
              {task.public_id}
            </TableCell>
            <TableCell className="max-w-72 truncate font-medium text-[color:var(--foreground)]">
              {task.title}
            </TableCell>
            <TableCell className="text-[color:var(--muted-foreground)]">{task.project?.name ?? "—"}</TableCell>
            <TableCell><AgentBadge agent={task.agent_type} /></TableCell>
            <TableCell><TaskStatusBadge status={task.status} /></TableCell>
            {full && <TableCell><PriorityBadge priority={task.priority} /></TableCell>}
            {full && (
              <TableCell className="whitespace-nowrap text-[color:var(--muted-foreground)]">
                {formatDateTime(task.started_at)}
              </TableCell>
            )}
            <TableCell className="whitespace-nowrap text-[color:var(--muted-foreground)]">
              {formatDuration(task.started_at, task.finished_at)}
            </TableCell>
            {full && <TableCell><CheckBadge status={task.tests_status} /></TableCell>}
            {full && <TableCell><CheckBadge status={task.build_status} /></TableCell>}
            {full && <TableCell className="text-[color:var(--muted-foreground)]">{task.requested_by ?? "—"}</TableCell>}
            {!full && (
              <TableCell className="whitespace-nowrap text-[color:var(--muted-foreground)]">
                {formatRelative(task.last_activity_at)}
              </TableCell>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
