"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { SessionStatusBadge } from "@/components/status-badges";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { apiGet, apiPatch, apiPost } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import type {
  ChannelBindingsResponse,
  DaemonActionResult,
  DaemonStatus,
  HookStatus,
  OpenAcpAgent,
  OpenAcpAgentInstallResult,
  OpenAcpInstallResult,
  OpenAcpInstallStatus,
  OpenAcpSession,
  Project,
  RedeployResult,
  SessionActionResult,
  SettingsTransferResult,
  SettingsTransferStatus,
} from "@/types/api";

type DaemonAction = "restart" | "stop";

const SNOWFLAKE = /^\d{17,20}$/;

/** Sentinel for the "not one of my projects" option in the workspace dropdown. */
const CUSTOM = "__custom__";

interface BindingRow {
  key: string;
  channel_id: string;
  agent: string;
  workspace: string;
  /** Only meaningful for rows loaded from disk. */
  workspace_exists: boolean | null;
  /** Project this workspace belongs to, null when it is a free-form path. */
  project_id: number | null;
  /** True once the user opts out of the project list for this row. */
  custom: boolean;
}

let rowCounter = 0;
const nextKey = () => `row-${(rowCounter += 1)}`;

function toRows(response: ChannelBindingsResponse): BindingRow[] {
  return response.bindings.map((b) => ({
    key: nextKey(),
    channel_id: b.channel_id,
    agent: b.agent,
    workspace: b.workspace,
    workspace_exists: b.workspace_exists,
    project_id: b.project_id,
    // A saved path that matches no project can only be edited as free text.
    custom: b.project_id === null,
  }));
}

function rowProblem(row: BindingRow, rows: BindingRow[]): string | null {
  if (!SNOWFLAKE.test(row.channel_id.trim())) {
    return "Channel ID must be 17-20 digits";
  }
  if (rows.filter((r) => r.channel_id.trim() === row.channel_id.trim()).length > 1) {
    return "Duplicate channel ID";
  }
  if (!row.agent.trim()) return "Agent is required";
  if (!row.workspace.trim()) return "Pick a project or enter a custom path";
  return null;
}

export default function OpenAcpPage() {
  const [rows, setRows] = useState<BindingRow[]>([]);
  const [original, setOriginal] = useState<ChannelBindingsResponse | null>(null);
  const [agents, setAgents] = useState<OpenAcpAgent[]>([]);
  const [agentCatalog, setAgentCatalog] = useState<OpenAcpAgent[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [hook, setHook] = useState<HookStatus | null>(null);
  const [install, setInstall] = useState<OpenAcpInstallStatus | null>(null);
  const [installing, setInstalling] = useState(false);
  const [installOutput, setInstallOutput] = useState<string | null>(null);
  const [agentInstallBusy, setAgentInstallBusy] = useState<string | null>(null);
  const [agentInstallOutput, setAgentInstallOutput] = useState<string | null>(null);
  const [transfer, setTransfer] = useState<SettingsTransferStatus | null>(null);
  const [transferBusy, setTransferBusy] = useState<"export" | "import" | null>(null);
  const [transferMsg, setTransferMsg] = useState<string | null>(null);
  const [redeployOutput, setRedeployOutput] = useState<string | null>(null);
  const [daemon, setDaemon] = useState<DaemonStatus | null>(null);
  const [daemonAction, setDaemonAction] = useState<DaemonAction | null>(null);
  const [daemonBusy, setDaemonBusy] = useState(false);
  const [daemonOutput, setDaemonOutput] = useState<string | null>(null);
  const [sessions, setSessions] = useState<OpenAcpSession[]>([]);
  const [killTarget, setKillTarget] = useState<OpenAcpSession | null>(null);
  const [killBusy, setKillBusy] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [redeploying, setRedeploying] = useState(false);
  const [saved, setSaved] = useState(false);

  const refresh = useCallback(async () => {
    // Every card loads on its own. On a freshly copied PC the OpenACP endpoints
    // answer 503 until settings.json exists, and one shared Promise.all would
    // take the project list down with them — leaving the binding form with an
    // empty project dropdown and no way to tell why.
    const failures: string[] = [];
    const load = async <T,>(label: string, path: string, apply: (value: T) => void) => {
      try {
        apply(await apiGet<T>(path));
      } catch (err) {
        failures.push(`${label}: ${err instanceof Error ? err.message : "request failed"}`);
      }
    };

    await Promise.all([
      load<ChannelBindingsResponse>(
        "Channel bindings",
        "/api/openacp/channel-bindings",
        (bindings) => {
          setOriginal(bindings);
          setRows(toRows(bindings));
        },
      ),
      load<OpenAcpAgent[]>("Agents", "/api/openacp/agents", setAgents),
      load<OpenAcpAgent[]>("Agent catalog", "/api/openacp/agents/catalog", setAgentCatalog),
      load<HookStatus>("Hook status", "/api/openacp/hook-status", setHook),
      load<DaemonStatus>("OpenACP server", "/api/openacp/daemon-status", setDaemon),
      load<Project[]>("Projects", "/api/projects", setProjects),
      load<OpenAcpSession[]>("Sessions", "/api/openacp/sessions", setSessions),
      load<OpenAcpInstallStatus>("Install status", "/api/openacp/install-status", setInstall),
      load<SettingsTransferStatus>(
        "Settings bundle",
        "/api/openacp/settings/transfer-status",
        setTransfer,
      ),
    ]);

    setError(failures.length > 0 ? failures.join(" · ") : null);
    setFormError(null);
    setSaved(false);
  }, []);

  // Deliberately not using useLive here: an unrelated task event would discard
  // in-progress edits. Refresh is manual.
  useEffect(() => {
    refresh();
  }, [refresh]);

  const updateRow = (key: string, patch: Partial<BindingRow>) => {
    setRows((current) =>
      current.map((row) => (row.key === key ? { ...row, ...patch } : row)),
    );
    setSaved(false);
  };

  const addRow = () => {
    setRows((current) => [
      ...current,
      {
        key: nextKey(),
        channel_id: "",
        agent: agents[0]?.id ?? "claude",
        workspace: "",
        workspace_exists: null,
        project_id: null,
        custom: false,
      },
    ]);
    setSaved(false);
  };

  const removeRow = (key: string) => {
    setRows((current) => current.filter((row) => row.key !== key));
    setSaved(false);
  };

  const problems = rows.map((row) => rowProblem(row, rows));
  const allValid = problems.every((p) => p === null);

  const save = async () => {
    if (!allValid) return;
    setBusy(true);
    setFormError(null);
    try {
      const response = await apiPatch<ChannelBindingsResponse>(
        "/api/openacp/channel-bindings",
        {
          bindings: rows.map((row) => ({
            channel_id: row.channel_id.trim(),
            agent: row.agent.trim(),
            workspace: row.workspace.trim(),
          })),
          revision: original?.revision ?? null,
        },
      );
      setOriginal(response);
      setRows(toRows(response));
      setSaved(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Save failed";
      setFormError(
        message.includes("changed on disk")
          ? "The settings file changed on disk. Click Refresh to reload — your edits will be lost."
          : message,
      );
    } finally {
      setBusy(false);
    }
  };

  const installOpenAcp = async () => {
    setInstalling(true);
    setFormError(null);
    setInstallOutput(null);
    try {
      const result = await apiPost<OpenAcpInstallResult>("/api/openacp/install");
      setInstall(result.status);
      setInstallOutput(result.output);
      // The daemon/hook cards read "not found on PATH" until now — refresh them
      // so a successful install lights them up without a manual reload.
      if (result.ok) await refresh();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "OpenACP install failed");
    } finally {
      setInstalling(false);
    }
  };

  const installAgent = async (agentId: string) => {
    setAgentInstallBusy(agentId);
    setFormError(null);
    setAgentInstallOutput(null);
    try {
      const result = await apiPost<OpenAcpAgentInstallResult>(
        `/api/openacp/agents/${agentId}/install`,
      );
      setAgentInstallOutput(`${agentId}: ${result.output}`);
      if (result.ok) await refresh();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : `Install ${agentId} failed`);
    } finally {
      setAgentInstallBusy(null);
    }
  };

  const runTransfer = async (action: "export" | "import") => {
    setTransferBusy(action);
    setFormError(null);
    setTransferMsg(null);
    try {
      const result = await apiPost<SettingsTransferResult>(`/api/openacp/settings/${action}`);
      setTransferMsg(result.detail);
      const status = await apiGet<SettingsTransferStatus>("/api/openacp/settings/transfer-status");
      setTransfer(status);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : `Settings ${action} failed`);
    } finally {
      setTransferBusy(null);
    }
  };

  const redeploy = async () => {
    setRedeploying(true);
    setFormError(null);
    setRedeployOutput(null);
    try {
      const result = await apiPost<RedeployResult>("/api/openacp/redeploy");
      setRedeployOutput(result.output);
      const hookStatus = await apiGet<HookStatus>("/api/openacp/hook-status");
      setHook(hookStatus);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Redeploy failed");
    } finally {
      setRedeploying(false);
    }
  };

  const runDaemonAction = async () => {
    if (!daemonAction) return;
    setDaemonBusy(true);
    setFormError(null);
    setDaemonOutput(null);
    try {
      const result = await apiPost<DaemonActionResult>(
        `/api/openacp/daemon/${daemonAction}`,
      );
      setDaemon(result.status);
      setDaemonOutput(result.output);
      setDaemonAction(null);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : `OpenACP ${daemonAction} failed`);
      setDaemonAction(null);
    } finally {
      setDaemonBusy(false);
    }
  };

  const killSession = async () => {
    if (!killTarget) return;
    setKillBusy(true);
    setFormError(null);
    try {
      await apiPost<SessionActionResult>(`/api/openacp/sessions/${killTarget.id}/cancel`);
      const [sessionList, daemonStatus] = await Promise.all([
        apiGet<OpenAcpSession[]>("/api/openacp/sessions"),
        apiGet<DaemonStatus>("/api/openacp/daemon-status"),
      ]);
      setSessions(sessionList);
      setDaemon(daemonStatus);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Session kill failed");
    } finally {
      setKillTarget(null);
      setKillBusy(false);
    }
  };

  const runningSessions = sessions.filter((s) => s.active);

  const daemonBadge = () => {
    if (!daemon) return <Badge className="tag-riso-muted">checking…</Badge>;
    if (daemon.running) return <Badge className="tag-riso-teal">running</Badge>;
    if (daemon.status === "offline") return <Badge className="tag-riso-muted">stopped</Badge>;
    return <Badge className="tag-riso-gold">unknown</Badge>;
  };

  const installBadge = () => {
    if (!install) return <Badge className="tag-riso-muted">checking…</Badge>;
    if (install.cli_installed) return <Badge className="tag-riso-teal">installed</Badge>;
    if (!install.npm_available) return <Badge className="tag-riso-gold">no npm</Badge>;
    return <Badge className="tag-riso-destructive">not installed</Badge>;
  };

  const hookBadge = () => {
    if (!hook) return <Badge className="tag-riso-muted">checking…</Badge>;
    if (hook.installed === true) return <Badge className="tag-riso-teal">installed</Badge>;
    if (hook.installed === false) return <Badge className="tag-riso-destructive">not installed</Badge>;
    return <Badge className="tag-riso-muted">unknown</Badge>;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="riso-title animate-ink-in">OpenACP channel bindings</h1>
        <Button variant="outline" size="sm" disabled={busy || redeploying} onClick={refresh}>
          Refresh
        </Button>
      </div>

      {error && <p className="text-sm text-[color:var(--destructive)]">{error}</p>}

      <p className="rounded border border-[color:color-mix(in_srgb,var(--accent-gold)_28%,transparent)] bg-[color:color-mix(in_srgb,var(--accent-gold)_12%,transparent)] px-3 py-2 text-sm text-[color:var(--accent-gold)]">
        Changes are written to OpenACP&apos;s <span className="font-mono text-xs">settings.json</span>.
        <strong> OpenACP must be restarted manually</strong> for them to take effect — Agent Deck
        never starts or stops it.
      </p>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>OpenACP installation</CardTitle>
          {installBadge()}
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p className="text-[color:var(--muted-foreground)]">{install?.detail ?? "Checking OpenACP installation…"}</p>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-[color:var(--muted-foreground)]">
            <span>
              CLI version:{" "}
              <span className="font-mono">{install?.cli_version ?? "—"}</span>
            </span>
            <span>
              Discord adapter:{" "}
              <span className="font-mono">
                {install?.adapter_installed === true
                  ? "installed"
                  : install?.adapter_installed === false
                    ? "missing"
                    : "unknown"}
              </span>
            </span>
          </div>
          <p className="text-xs text-[color:var(--muted-foreground)]">
            Installs <span className="font-mono">@openacp/cli</span> and{" "}
            <span className="font-mono">@openacp/discord-adapter</span> globally via npm — use this
            on a freshly copied PC. It does <strong>not</strong> set up the OpenACP workspace or the
            Discord bot token; those stay manual. After installing, configure the workspace, then
            start OpenACP with <span className="font-mono">scripts\start-openacp.ps1</span>.
          </p>
          {install && !install.npm_available && (
            <p className="rounded border border-[color:color-mix(in_srgb,var(--accent-gold)_28%,transparent)] bg-[color:color-mix(in_srgb,var(--accent-gold)_12%,transparent)] px-3 py-2 text-xs text-[color:var(--accent-gold)]">
              npm was not found on the backend&apos;s PATH — install Node.js 20+ first, then restart
              the Agent Deck backend.
            </p>
          )}
          <Button
            variant="outline"
            size="sm"
            disabled={installing || busy || (install ? !install.npm_available : false)}
            onClick={installOpenAcp}
          >
            {installing
              ? "Installing…"
              : install?.cli_installed
                ? "Reinstall / update"
                : "Install OpenACP"}
          </Button>
          {installing && (
            <p className="text-xs text-[color:var(--muted-foreground)]">
              npm is downloading — this can take a few minutes on a fresh PC.
            </p>
          )}
          {installOutput && (
            <pre className="overflow-x-auto rounded bg-[color:var(--background-3)] p-2 text-xs text-[color:var(--foreground)]">
              {installOutput}
            </pre>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Agent CLIs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p className="text-xs text-[color:var(--muted-foreground)]">
            Installs an agent plugin through <span className="font-mono">openacp agents install</span> —
            this is what fills the Agent dropdown above. Restart OpenACP afterwards to pick it up.
          </p>
          <div className="flex flex-wrap gap-2">
            {agentCatalog.map((catalogAgent) => {
              const installed = agents.some((a) => a.id === catalogAgent.id);
              return (
                <Button
                  key={catalogAgent.id}
                  variant="outline"
                  size="sm"
                  disabled={installed || agentInstallBusy !== null}
                  onClick={() => installAgent(catalogAgent.id)}
                >
                  {installed
                    ? `${catalogAgent.name} ✓`
                    : agentInstallBusy === catalogAgent.id
                      ? "Installing…"
                      : `Install ${catalogAgent.name}`}
                </Button>
              );
            })}
          </div>
          {agentInstallOutput && (
            <pre className="overflow-x-auto rounded bg-[color:var(--background-3)] p-2 text-xs text-[color:var(--foreground)]">
              {agentInstallOutput}
            </pre>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Move config to another PC (settings.json)</CardTitle>
          <Badge className={transfer?.bundle_exists ? "tag-riso-teal" : "tag-riso-muted"}>
            {transfer?.bundle_exists ? "bundle ready" : "no bundle"}
          </Badge>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p className="text-xs text-[color:var(--muted-foreground)]">
            Full copy incl. the bot token; the bundle folder is gitignored. Copy the whole{" "}
            <span className="font-mono">C:\agent-deck</span> folder to your other PC.
          </p>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-[color:var(--muted-foreground)]">
            <span>
              Bundle:{" "}
              <span className="font-mono">
                {transfer?.bundle_exists ? "present" : "—"}
                {transfer?.bundle_has_token ? " (with token)" : ""}
              </span>
            </span>
            <span>
              Updated:{" "}
              <span className="font-mono">
                {transfer?.bundle_modified ? formatRelative(transfer.bundle_modified) : "—"}
              </span>
            </span>
          </div>
          {transfer?.bundle_path && (
            <p className="font-mono text-xs text-[color:var(--muted-foreground)]">{transfer.bundle_path}</p>
          )}
          <p className="text-xs text-[color:var(--muted-foreground)]">
            <strong>Copy here</strong> writes the live settings into the repo folder (do this on this
            PC). <strong>Apply bundle</strong> writes the bundle onto this PC&apos;s live workspace
            (do this on the new PC, then restart OpenACP). The previous live file is kept as{" "}
            <span className="font-mono">.pre-import.bak</span>.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={transferBusy !== null || !transfer?.live_exists}
              onClick={() => runTransfer("export")}
            >
              {transferBusy === "export" ? "Copying…" : "Copy settings.json here"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={transferBusy !== null || !transfer?.bundle_exists}
              onClick={() => runTransfer("import")}
            >
              {transferBusy === "import" ? "Applying…" : "Apply bundle to this PC"}
            </Button>
          </div>
          {transferMsg && <p className="text-sm text-[color:var(--accent-teal)]">{transferMsg}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>OpenACP server</CardTitle>
          {daemonBadge()}
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {daemon?.detail && <p className="text-[color:var(--accent-gold)]">{daemon.detail}</p>}
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-[color:var(--muted-foreground)]">
            <span>PID: <span className="font-mono">{daemon?.pid ?? "—"}</span></span>
            <span>Mode: <span className="font-mono">{daemon?.mode ?? "—"}</span></span>
            <span>
              Channels:{" "}
              <span className="font-mono">
                {daemon?.channels.length ? daemon.channels.join(", ") : "—"}
              </span>
            </span>
            <span>Active sessions: <span className="font-mono">{daemon?.active_sessions ?? 0}</span></span>
          </div>
          <p className="text-xs text-[color:var(--muted-foreground)]">
            Restart OpenACP to apply saved channel bindings.
            {daemon?.foreground
              ? " It runs in its own console window: that window is closed and a new one opens in its place."
              : ""}{" "}
            Agent Deck cannot restart its own backend or dashboard — use{" "}
            <span className="font-mono">agent-deck.bat stop</span> for those.
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={daemonBusy || busy}
              onClick={() => setDaemonAction("restart")}
            >
              {daemonBusy && daemonAction === "restart" ? "Restarting…" : "Restart OpenACP"}
            </Button>
            <Button
              variant="destructive"
              size="sm"
              disabled={daemonBusy || busy || !daemon?.running}
              onClick={() => setDaemonAction("stop")}
            >
              Stop OpenACP
            </Button>
          </div>
          {daemonOutput && (
            <pre className="overflow-x-auto rounded bg-[color:var(--background-3)] p-2 text-xs text-[color:var(--foreground)]">
              {daemonOutput}
            </pre>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Agent sessions</CardTitle>
          <Badge className={runningSessions.length > 0 ? "tag-riso-teal" : "tag-riso-muted"}>
            {runningSessions.length} running
          </Badge>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p className="text-xs text-[color:var(--muted-foreground)]">
            Deleting a Discord thread does <strong>not</strong> stop its session — OpenACP is
            never told about the deletion. Kill leftover sessions here.
          </p>
          {runningSessions.length === 0 ? (
            <p className="text-sm text-[color:var(--muted-foreground)]">
              No running sessions.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Agent</TableHead>
                    <TableHead>Thread</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Last active</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {runningSessions.map((s) => (
                    <TableRow key={s.id}>
                      <TableCell className="font-mono text-xs">{s.agent}</TableCell>
                      <TableCell className="max-w-[24rem] truncate text-xs" title={s.name || s.id}>
                        {s.name || <span className="font-mono text-[color:var(--muted-foreground)]">{s.id}</span>}
                      </TableCell>
                      <TableCell>
                        <SessionStatusBadge status={s.status} />
                      </TableCell>
                      <TableCell className="text-xs text-[color:var(--muted-foreground)]">
                        {formatRelative(s.last_active_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="destructive"
                          size="sm"
                          disabled={killBusy}
                          onClick={() => setKillTarget(s)}
                        >
                          Kill
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          {sessions.length > runningSessions.length && (
            <p className="text-xs text-[color:var(--muted-foreground)]">
              {sessions.length - runningSessions.length} finished/cancelled{" "}
              {sessions.length - runningSessions.length === 1 ? "session" : "sessions"} not shown —
              they hold no agent process.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Adapter hook</CardTitle>
          {hookBadge()}
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p className="text-[color:var(--muted-foreground)]">{hook?.detail ?? "Checking hook status…"}</p>
          <p className="text-xs text-[color:var(--muted-foreground)]">
            The hook is removed whenever the Discord adapter is reinstalled or updated. Redeploy
            re-applies it, then restart OpenACP.
          </p>
          <Button variant="outline" size="sm" disabled={redeploying || busy} onClick={redeploy}>
            {redeploying ? "Redeploying…" : "Redeploy hook"}
          </Button>
          {redeployOutput && (
            <pre className="overflow-x-auto rounded bg-[color:var(--background-3)] p-2 text-xs text-[color:var(--foreground)]">
              {redeployOutput}
            </pre>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Project channels</CardTitle>
          <Button variant="outline" size="sm" disabled={busy} onClick={addRow}>
            Add binding
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-[color:var(--muted-foreground)]">
            One Discord channel = one project. Every thread inside it becomes a separate session
            using the fixed agent and workspace below. A project is selectable only once it has a
            <strong> repository path</strong> — set one on the Projects page, or pick{" "}
            <span className="font-mono">Custom path…</span> to type a folder by hand.
          </p>

          {original && original.invalid_entries.length > 0 && (
            <div className="rounded border border-[color:color-mix(in_srgb,var(--destructive)_28%,transparent)] bg-[color:color-mix(in_srgb,var(--destructive)_10%,transparent)] px-3 py-2 text-sm text-[color:var(--destructive)]">
              <p className="font-medium">
                These entries in settings.json are invalid and will be removed when you save:
              </p>
              <ul className="mt-1 list-inside list-disc text-xs">
                {original.invalid_entries.map((entry) => (
                  <li key={entry.channel_id}>
                    <span className="font-mono">{entry.channel_id}</span> — {entry.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Channel ID</TableHead>
                  <TableHead>Agent</TableHead>
                  <TableHead>Project / workspace</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row, index) => {
                  const problem = problems[index];
                  return (
                    <TableRow key={row.key}>
                      <TableCell>
                        <Input
                          className={`font-mono text-xs ${problem ? "border-[color:var(--destructive)]" : ""}`}
                          placeholder="1528342771117588630"
                          value={row.channel_id}
                          onChange={(e) => updateRow(row.key, { channel_id: e.target.value })}
                        />
                      </TableCell>
                      <TableCell>
                        <Select
                          value={row.agent}
                          onChange={(e) => updateRow(row.key, { agent: e.target.value })}
                        >
                          {/* Keep a manually configured agent selectable even if it
                              is not installed, so saving does not silently change it. */}
                          {!agents.some((a) => a.id === row.agent) && row.agent && (
                            <option value={row.agent}>{row.agent}</option>
                          )}
                          {agents.map((agent) => (
                            <option key={agent.id} value={agent.id}>
                              {agent.name}
                            </option>
                          ))}
                        </Select>
                      </TableCell>
                      <TableCell>
                        <Select
                          className={problem && !row.workspace.trim() ? "border-[color:var(--destructive)]" : ""}
                          value={
                            row.custom ? CUSTOM : row.project_id !== null ? String(row.project_id) : ""
                          }
                          onChange={(e) => {
                            const choice = e.target.value;
                            if (choice === CUSTOM) {
                              // Keep whatever path was there — it is the likeliest
                              // starting point for hand-editing.
                              updateRow(row.key, { custom: true, project_id: null });
                              return;
                            }
                            const project = projects.find((p) => String(p.id) === choice);
                            updateRow(row.key, {
                              custom: false,
                              project_id: project?.id ?? null,
                              workspace: project?.repository_path ?? "",
                              workspace_exists: null,
                            });
                          }}
                        >
                          <option value="">Select a project…</option>
                          {/* A project without a repository path has no workspace to
                              bind to. Show it disabled rather than hiding it — an
                              absent project reads as a bug, not as missing input. */}
                          {projects.map((project) => (
                            <option
                              key={project.id}
                              value={String(project.id)}
                              disabled={!project.repository_path}
                            >
                              {project.name}
                              {project.is_active ? "" : " (inactive)"}
                              {project.repository_path ? "" : " — no repository path"}
                            </option>
                          ))}
                          <option value={CUSTOM}>Custom path…</option>
                        </Select>
                        {row.custom ? (
                          <Input
                            className={`mt-1 font-mono text-xs ${
                              problem && !row.workspace.trim() ? "border-[color:var(--destructive)]" : ""
                            }`}
                            placeholder="D:\Projects\CrowForge"
                            value={row.workspace}
                            onChange={(e) =>
                              updateRow(row.key, {
                                workspace: e.target.value,
                                workspace_exists: null,
                              })
                            }
                          />
                        ) : (
                          row.workspace && (
                            <p className="mt-1 font-mono text-xs text-[color:var(--muted-foreground)]">{row.workspace}</p>
                          )
                        )}
                        {row.workspace_exists === false && (
                          <p className="mt-1 text-xs text-[color:var(--accent-gold)]">
                            Directory not found — saving will fail until it exists.
                          </p>
                        )}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={busy}
                          onClick={() => removeRow(row.key)}
                        >
                          Remove
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
                {rows.length === 0 && (
                  <TableRow>
                    <TableCell className="text-sm text-[color:var(--muted-foreground)]">
                      No project channels configured.
                    </TableCell>
                    <TableCell />
                    <TableCell />
                    <TableCell />
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>

          {problems.some((p) => p !== null) && (
            <ul className="list-inside list-disc text-sm text-[color:var(--destructive)]">
              {problems
                .map((problem, index) => ({ problem, row: rows[index] }))
                .filter((entry) => entry.problem !== null)
                .map((entry) => (
                  <li key={entry.row.key}>
                    {entry.row.channel_id || "(empty)"}: {entry.problem}
                  </li>
                ))}
            </ul>
          )}

          {formError && <p className="text-sm text-[color:var(--destructive)]">{formError}</p>}
          {saved && (
            <p className="text-sm text-[color:var(--accent-teal)]">
              Saved. Restart OpenACP for the change to take effect.
            </p>
          )}

          <div className="flex items-center justify-between">
            <p className="font-mono text-xs text-[color:var(--muted-foreground)]">{original?.settings_path}</p>
            <Button size="sm" disabled={busy || !allValid} onClick={save}>
              {busy ? "Saving…" : "Save"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Dialog
        open={killTarget !== null}
        onClose={() => !killBusy && setKillTarget(null)}
        title="Kill session?"
      >
        <div className="space-y-3 text-sm">
          <p className="text-[color:var(--foreground)]">
            Session{" "}
            <span className="font-mono text-xs">{killTarget?.name || killTarget?.id}</span>{" "}
            ({killTarget?.agent}) will be cancelled. Any work it has in progress is lost.
          </p>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={killBusy}
              onClick={() => setKillTarget(null)}
            >
              Cancel
            </Button>
            <Button variant="destructive" size="sm" disabled={killBusy} onClick={killSession}>
              {killBusy ? "Killing…" : "Kill session"}
            </Button>
          </div>
        </div>
      </Dialog>

      <Dialog
        open={daemonAction !== null}
        onClose={() => !daemonBusy && setDaemonAction(null)}
        title={daemonAction === "stop" ? "Stop OpenACP?" : "Restart OpenACP?"}
      >
        <div className="space-y-3 text-sm">
          <p className="text-[color:var(--foreground)]">
            {daemonAction === "stop"
              ? "OpenACP will be stopped. Discord will stop responding until you start it again."
              : "OpenACP will be restarted so saved channel bindings take effect. It runs in the foreground, so a new console window will open — closing that window stops OpenACP."}
          </p>
          {daemon && daemon.active_sessions > 0 ? (
            <p className="rounded border border-[color:color-mix(in_srgb,var(--destructive)_28%,transparent)] bg-[color:color-mix(in_srgb,var(--destructive)_10%,transparent)] px-3 py-2 text-[color:var(--destructive)]">
              This terminates <strong>{daemon.active_sessions}</strong>{" "}
              running agent {daemon.active_sessions === 1 ? "session" : "sessions"}. Any work in
              progress is lost.
            </p>
          ) : (
            <p className="text-xs text-[color:var(--muted-foreground)]">No agent sessions are currently running.</p>
          )}
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={daemonBusy}
              onClick={() => setDaemonAction(null)}
            >
              Cancel
            </Button>
            <Button
              variant={daemonAction === "stop" ? "destructive" : "default"}
              size="sm"
              disabled={daemonBusy}
              onClick={runDaemonAction}
            >
              {daemonBusy ? "Working…" : daemonAction === "stop" ? "Stop" : "Restart"}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
