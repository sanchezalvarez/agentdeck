"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import {
  AgentBadge,
  CheckBadge,
  PriorityBadge,
  TaskStatusBadge,
} from "@/components/status-badges";
import { apiPost, apiGet } from "@/lib/api";
import { formatDateTime, formatDuration, statusLabel } from "@/lib/format";
import { useLive } from "@/lib/use-live";
import type { Artifact, Task, TaskEventListResponse } from "@/types/api";

type Action = "approve" | "reject" | "archive" | null;

function Field({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-[color:var(--muted-foreground)]">{label}</dt>
      <dd className={`mt-0.5 text-sm text-[color:var(--foreground)] break-all ${mono ? "font-mono text-xs" : ""}`}>
        {value ?? "—"}
      </dd>
    </div>
  );
}

export default function TaskDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const [task, setTask] = useState<Task | null>(null);
  const [events, setEvents] = useState<TaskEventListResponse | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [action, setAction] = useState<Action>(null);
  const [note, setNote] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [taskBody, eventsBody, artifactsBody] = await Promise.all([
        apiGet<Task>(`/api/tasks/${id}`),
        apiGet<TaskEventListResponse>(`/api/tasks/${id}/events?limit=500`),
        apiGet<Artifact[]>(`/api/tasks/${id}/artifacts`),
      ]);
      setTask(taskBody);
      setEvents(eventsBody);
      setArtifacts(artifactsBody);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load task");
    }
  }, [id]);

  useEffect(() => {
    refresh();
  }, [refresh]);
  useLive(refresh);

  const runAction = async () => {
    if (!task || !action) return;
    setBusy(true);
    setActionError(null);
    try {
      if (action === "approve") {
        await apiPost(`/api/tasks/${task.public_id}/approve`,
          note.trim() ? { review_note: note.trim() } : {});
      } else if (action === "reject") {
        await apiPost(`/api/tasks/${task.public_id}/reject`, { review_note: note.trim() });
      } else {
        await apiPost(`/api/tasks/${task.public_id}/archive`);
      }
      setAction(null);
      setNote("");
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  };

  if (error && !task) {
    return <p className="text-sm text-[color:var(--destructive)]">Could not load task: {error}</p>;
  }
  if (!task) {
    return <p className="text-sm text-[color:var(--muted-foreground)]">Loading…</p>;
  }

  const reviewable = task.status === "needs_review" || task.status === "waiting_for_approval";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <button
            onClick={() => router.push("/tasks")}
            className="text-xs text-[color:var(--muted-foreground)] hover:text-[color:var(--foreground)]"
          >
            ← All tasks
          </button>
          <h1 className="riso-title animate-ink-in mt-1 flex flex-wrap items-center gap-3">
            <span className="font-mono">{task.public_id}</span>
            {task.title}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <TaskStatusBadge status={task.status} />
            <PriorityBadge priority={task.priority} />
            <AgentBadge agent={task.agent_type} />
            {task.is_archived && <Badge className="tag-riso-muted">archived</Badge>}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="success" size="sm" disabled={!reviewable} onClick={() => setAction("approve")}>
            Approve
          </Button>
          <Button variant="destructive" size="sm" disabled={!reviewable} onClick={() => setAction("reject")}>
            Reject
          </Button>
          <Button variant="outline" size="sm" disabled={task.is_archived} onClick={() => setAction("archive")}>
            Archive
          </Button>
        </div>
      </div>

      {task.description && (
        <Card>
          <CardHeader><CardTitle>Description</CardTitle></CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap text-sm text-[color:var(--foreground)]">{task.description}</p>
          </CardContent>
        </Card>
      )}

      {(task.result_summary || task.error_message || task.review_note) && (
        <Card>
          <CardHeader><CardTitle>Result</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {task.result_summary && (
              <p className="whitespace-pre-wrap text-sm text-[color:var(--foreground)]">{task.result_summary}</p>
            )}
            {task.error_message && (
              <p className="whitespace-pre-wrap rounded-md bg-[color:color-mix(in_srgb,var(--destructive)_10%,transparent)] p-3 text-sm text-red-800">
                {task.error_message}
              </p>
            )}
            {task.review_note && (
              <p className="rounded-md bg-[color:color-mix(in_srgb,var(--accent-gold)_12%,transparent)] p-3 text-sm text-amber-900">
                <span className="font-medium">Review note:</span> {task.review_note}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <Card className="xl:col-span-1">
          <CardHeader><CardTitle>Details</CardTitle></CardHeader>
          <CardContent>
            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Project" value={task.project ? `${task.project.name} (${task.project.slug})` : null} />
              <Field label="Requested by" value={task.requested_by} />
              <Field label="Worker" value={task.worker?.name ?? null} />
              <Field label="Agent session" value={task.session_id} mono />
              <Field label="Process ID" value={task.process_id} mono />
              <Field label="Exit code" value={task.exit_code} mono />
              <Field label="Created" value={formatDateTime(task.created_at)} />
              <Field label="Started" value={formatDateTime(task.started_at)} />
              <Field label="Finished" value={formatDateTime(task.finished_at)} />
              <Field label="Duration" value={formatDuration(task.started_at, task.finished_at)} />
              <Field label="Approved" value={formatDateTime(task.approved_at)} />
              <Field label="Rejected" value={formatDateTime(task.rejected_at)} />
              <Field label="Tests" value={<CheckBadge status={task.tests_status} />} />
              <Field label="Build" value={<CheckBadge status={task.build_status} />} />
              <Field label="Branch" value={task.branch} mono />
              <Field label="Start commit" value={task.start_commit} mono />
              <Field label="End commit" value={task.end_commit} mono />
              <Field label="Working directory" value={task.working_directory} mono />
              <Field label="Worktree path" value={task.worktree_path} mono />
              <Field label="Discord guild" value={task.discord_guild_id} mono />
              <Field label="Discord channel" value={task.discord_channel_id} mono />
              <Field label="Discord thread" value={task.discord_thread_id} mono />
            </dl>
          </CardContent>
        </Card>

        <div className="space-y-5 xl:col-span-2">
          <Card>
            <CardHeader><CardTitle>Timeline</CardTitle></CardHeader>
            <CardContent>
              {!events || events.items.length === 0 ? (
                <p className="text-sm text-[color:var(--muted-foreground)]">No events.</p>
              ) : (
                <ol className="space-y-3">
                  {events.items.map((event) => (
                    <li key={event.id} className="flex gap-3 text-sm">
                      <span className="w-32 shrink-0 whitespace-nowrap font-mono text-xs text-[color:var(--muted-foreground)]">
                        {formatDateTime(event.created_at)}
                      </span>
                      <div className="min-w-0">
                        <Badge className="tag-riso-muted">
                          {statusLabel(event.event_type)}
                        </Badge>
                        {event.message && (
                          <p className="mt-1 whitespace-pre-wrap text-[color:var(--foreground)]">{event.message}</p>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Artifacts</CardTitle></CardHeader>
            <CardContent>
              {artifacts.length === 0 ? (
                <p className="text-sm text-[color:var(--muted-foreground)]">No artifacts.</p>
              ) : (
                <ul className="space-y-2">
                  {artifacts.map((artifact) => (
                    <li key={artifact.id} className="rounded-md border border-[color:var(--border)] p-3 text-sm">
                      <div className="flex items-center gap-2">
                        <Badge className="tag-riso-muted">
                          {statusLabel(artifact.artifact_type)}
                        </Badge>
                        <span className="font-medium text-[color:var(--foreground)]">{artifact.name}</span>
                      </div>
                      {artifact.local_path && (
                        <p className="mt-1 break-all font-mono text-xs text-[color:var(--muted-foreground)]">
                          {artifact.local_path}
                        </p>
                      )}
                      {artifact.url && (
                        <a
                          href={artifact.url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-1 block break-all text-xs text-[color:var(--accent-violet)] hover:underline"
                        >
                          {artifact.url}
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <Dialog
        open={action !== null}
        onClose={() => !busy && setAction(null)}
        title={
          action === "approve" ? `Approve ${task.public_id}?`
            : action === "reject" ? `Reject ${task.public_id}?`
              : `Archive ${task.public_id}?`
        }
      >
        {action === "approve" && (
          <div className="space-y-3">
            <p className="text-sm text-[color:var(--muted-foreground)]">
              The task will be marked as <strong>completed</strong>.
            </p>
            <Textarea
              placeholder="Optional review note…"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </div>
        )}
        {action === "reject" && (
          <div className="space-y-3">
            <p className="text-sm text-[color:var(--muted-foreground)]">
              The task will be marked as <strong>rejected</strong>. A review note is required.
            </p>
            <Textarea
              placeholder="Why is this being rejected? (required)"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </div>
        )}
        {action === "archive" && (
          <p className="text-sm text-[color:var(--muted-foreground)]">
            The task will be hidden from default listings. This does not delete anything.
          </p>
        )}
        {actionError && <p className="mt-2 text-sm text-[color:var(--destructive)]">{actionError}</p>}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" size="sm" disabled={busy} onClick={() => setAction(null)}>
            Cancel
          </Button>
          <Button
            size="sm"
            variant={action === "reject" ? "destructive" : action === "approve" ? "success" : "default"}
            disabled={busy || (action === "reject" && note.trim().length < 3)}
            onClick={runAction}
          >
            {busy ? "Working…" : "Confirm"}
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
