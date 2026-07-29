"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { apiGet, apiPatch, apiPost } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { useLive } from "@/lib/use-live";
import type { DashboardSummary, Project, ProjectSummary, ProjectType } from "@/types/api";

interface ProjectForm {
  name: string;
  slug: string;
  repository_path: string;
  default_branch: string;
  project_type: ProjectType;
  is_active: boolean;
}

const EMPTY_FORM: ProjectForm = {
  name: "", slug: "", repository_path: "", default_branch: "main",
  project_type: "other", is_active: true,
};

export default function ProjectsPage() {
  const [summaries, setSummaries] = useState<ProjectSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Project | "new" | null>(null);
  const [form, setForm] = useState<ProjectForm>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const summary = await apiGet<DashboardSummary>("/api/dashboard/summary");
      setSummaries(summary.projects);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);
  useLive(refresh);

  const openNew = () => {
    setForm(EMPTY_FORM);
    setFormError(null);
    setEditing("new");
  };

  const openEdit = (project: Project) => {
    setForm({
      name: project.name,
      slug: project.slug,
      repository_path: project.repository_path ?? "",
      default_branch: project.default_branch,
      project_type: project.project_type,
      is_active: project.is_active,
    });
    setFormError(null);
    setEditing(project);
  };

  const save = async () => {
    setBusy(true);
    setFormError(null);
    const body = {
      name: form.name.trim(),
      slug: form.slug.trim() || undefined,
      repository_path: form.repository_path.trim() || null,
      default_branch: form.default_branch.trim() || "main",
      project_type: form.project_type,
      is_active: form.is_active,
    };
    try {
      if (editing === "new") {
        await apiPost("/api/projects", body);
      } else if (editing) {
        await apiPatch(`/api/projects/${editing.id}`, body);
      }
      setEditing(null);
      await refresh();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="riso-title animate-ink-in">Projects</h1>
        <Button size="sm" onClick={openNew}>New project</Button>
      </div>

      {error && <p className="text-sm text-[color:var(--destructive)]">{error}</p>}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {summaries.map(({ project, ...stats }) => (
          <Card key={project.id} className={project.is_active ? "" : "opacity-60"}>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>{project.name}</CardTitle>
              <div className="flex items-center gap-2">
                <Badge className="tag-riso-muted">{project.project_type}</Badge>
                {!project.is_active && (
                  <Badge className="tag-riso-muted">inactive</Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p className="font-mono text-xs text-[color:var(--muted-foreground)]">{project.slug}</p>
              {project.repository_path && (
                <p className="break-all font-mono text-xs text-[color:var(--muted-foreground)]">
                  {project.repository_path}
                </p>
              )}
              <p className="text-xs text-[color:var(--muted-foreground)]">
                Default branch: <span className="font-mono">{project.default_branch}</span>
              </p>
              <div className="flex gap-4 text-xs">
                <span className="text-[color:var(--accent-violet)]">{stats.running_tasks} running</span>
                <span className="text-[color:var(--accent-orange)]">
                  {stats.needs_review_tasks} needs review
                </span>
                <span className="text-[color:var(--destructive)]">{stats.failed_tasks} failed</span>
              </div>
              <p className="text-xs text-[color:var(--muted-foreground)]">
                Last completed:{" "}
                {stats.last_completed_task_id
                  ? `${stats.last_completed_task_id} (${formatRelative(stats.last_completed_at)})`
                  : "—"}
              </p>
              <Button variant="outline" size="sm" onClick={() => openEdit(project)}>
                Edit
              </Button>
            </CardContent>
          </Card>
        ))}
        {summaries.length === 0 && !error && (
          <p className="text-sm text-[color:var(--muted-foreground)]">No projects yet.</p>
        )}
      </div>

      <Dialog
        open={editing !== null}
        onClose={() => !busy && setEditing(null)}
        title={editing === "new" ? "New project" : `Edit ${form.name}`}
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-[color:var(--muted-foreground)]">Name</label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[color:var(--muted-foreground)]">
              Slug {editing === "new" && "(optional — derived from name)"}
            </label>
            <Input value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[color:var(--muted-foreground)]">Repository path</label>
            <Input
              placeholder="D:\Projects\MyProject"
              value={form.repository_path}
              onChange={(e) => setForm({ ...form, repository_path: e.target.value })}
            />
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="mb-1 block text-xs font-medium text-[color:var(--muted-foreground)]">Default branch</label>
              <Input
                value={form.default_branch}
                onChange={(e) => setForm({ ...form, default_branch: e.target.value })}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-[color:var(--muted-foreground)]">Type</label>
              <Select
                value={form.project_type}
                onChange={(e) => setForm({ ...form, project_type: e.target.value as ProjectType })}
              >
                {["web", "unity", "desktop", "backend", "other"].map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </Select>
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm text-[color:var(--foreground)]">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            Active
          </label>
          {formError && <p className="text-sm text-[color:var(--destructive)]">{formError}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" disabled={busy} onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button size="sm" disabled={busy || !form.name.trim()} onClick={save}>
              {busy ? "Saving…" : "Save"}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
