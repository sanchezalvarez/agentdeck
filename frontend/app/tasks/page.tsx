"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { TaskTable } from "@/components/task-table";
import { apiGet } from "@/lib/api";
import { useLive } from "@/lib/use-live";
import type { Project, TaskListResponse } from "@/types/api";

const PAGE_SIZE = 25;

const STATUSES = [
  "queued", "starting", "running", "waiting_for_user", "waiting_for_approval",
  "testing", "needs_review", "completed", "blocked", "failed", "cancelled", "rejected",
];

interface Filters {
  search: string;
  project: string;
  agent_type: string;
  status: string;
  priority: string;
  requested_by: string;
  created_from: string;
  created_to: string;
  is_archived: boolean;
}

const EMPTY_FILTERS: Filters = {
  search: "", project: "", agent_type: "", status: "", priority: "",
  requested_by: "", created_from: "", created_to: "", is_archived: false,
};

export default function TasksPage() {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [page, setPage] = useState(0);
  const [data, setData] = useState<TaskListResponse | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<Project[]>("/api/projects").then(setProjects).catch(() => {});
  }, []);

  const refresh = useCallback(async () => {
    const params = new URLSearchParams();
    if (filters.search) params.set("search", filters.search);
    if (filters.project) params.set("project", filters.project);
    if (filters.agent_type) params.set("agent_type", filters.agent_type);
    if (filters.status) params.set("status", filters.status);
    if (filters.priority) params.set("priority", filters.priority);
    if (filters.requested_by) params.set("requested_by", filters.requested_by);
    if (filters.created_from) params.set("created_from", filters.created_from);
    if (filters.created_to) params.set("created_to", filters.created_to);
    params.set("is_archived", String(filters.is_archived));
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(page * PAGE_SIZE));
    try {
      setData(await apiGet<TaskListResponse>(`/api/tasks?${params.toString()}`));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tasks");
    }
  }, [filters, page]);

  useEffect(() => {
    refresh();
  }, [refresh]);
  useLive(refresh);

  const update = (patch: Partial<Filters>) => {
    setFilters((prev) => ({ ...prev, ...patch }));
    setPage(0);
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="space-y-4">
      <h1 className="riso-title animate-ink-in">Tasks</h1>

      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 p-4">
          <div className="w-56">
            <label className="mb-1 block text-xs font-medium text-[color:var(--muted-foreground)]">Search</label>
            <Input
              placeholder="ID, title, description…"
              value={filters.search}
              onChange={(event) => update({ search: event.target.value })}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[color:var(--muted-foreground)]">Project</label>
            <Select value={filters.project} onChange={(e) => update({ project: e.target.value })}>
              <option value="">All</option>
              {projects.map((p) => (
                <option key={p.id} value={p.slug}>{p.name}</option>
              ))}
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[color:var(--muted-foreground)]">Agent</label>
            <Select value={filters.agent_type} onChange={(e) => update({ agent_type: e.target.value })}>
              <option value="">All</option>
              <option value="claude">claude</option>
              <option value="codex">codex</option>
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[color:var(--muted-foreground)]">Status</label>
            <Select value={filters.status} onChange={(e) => update({ status: e.target.value })}>
              <option value="">All</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
              ))}
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[color:var(--muted-foreground)]">Priority</label>
            <Select value={filters.priority} onChange={(e) => update({ priority: e.target.value })}>
              <option value="">All</option>
              <option value="low">low</option>
              <option value="normal">normal</option>
              <option value="high">high</option>
              <option value="critical">critical</option>
            </Select>
          </div>
          <div className="w-36">
            <label className="mb-1 block text-xs font-medium text-[color:var(--muted-foreground)]">Requested by</label>
            <Input
              value={filters.requested_by}
              onChange={(event) => update({ requested_by: event.target.value })}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[color:var(--muted-foreground)]">From</label>
            <Input
              type="date"
              value={filters.created_from}
              onChange={(event) => update({ created_from: event.target.value })}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[color:var(--muted-foreground)]">To</label>
            <Input
              type="date"
              value={filters.created_to}
              onChange={(event) => update({ created_to: event.target.value })}
            />
          </div>
          <label className="flex h-9 items-center gap-2 text-sm text-[color:var(--foreground)]">
            <input
              type="checkbox"
              checked={filters.is_archived}
              onChange={(event) => update({ is_archived: event.target.checked })}
            />
            Archived
          </label>
          <Button variant="outline" size="sm" onClick={() => update(EMPTY_FILTERS)}>
            Reset
          </Button>
        </CardContent>
      </Card>

      {error && <p className="text-sm text-[color:var(--destructive)]">{error}</p>}

      <Card>
        <CardContent className="p-0 pb-2">
          <TaskTable tasks={data?.items ?? []} emptyMessage="No tasks match the filters." />
        </CardContent>
      </Card>

      <div className="flex items-center justify-between text-sm text-[color:var(--muted-foreground)]">
        <span>
          {data ? `${data.total} task${data.total === 1 ? "" : "s"}` : ""}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            Previous
          </Button>
          <span>
            Page {page + 1} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page + 1 >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
