export type ProjectType = "web" | "unity" | "desktop" | "backend" | "other";
export type WorkerStatus = "online" | "offline" | "degraded" | "unknown";
export type AgentType = "claude" | "codex";
export type TaskStatus =
  | "queued"
  | "starting"
  | "running"
  | "waiting_for_user"
  | "waiting_for_approval"
  | "testing"
  | "needs_review"
  | "completed"
  | "blocked"
  | "failed"
  | "cancelled"
  | "rejected";
export type TaskPriority = "low" | "normal" | "high" | "critical";
export type CheckStatus = "pending" | "running" | "passed" | "failed" | "not_run";
export type ArtifactType =
  | "log"
  | "screenshot"
  | "test_report"
  | "build"
  | "diff"
  | "patch"
  | "document"
  | "other";

export interface Project {
  id: number;
  name: string;
  slug: string;
  repository_path: string | null;
  default_branch: string;
  project_type: ProjectType;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Worker {
  id: number;
  name: string;
  hostname: string | null;
  operating_system: string | null;
  status: WorkerStatus;
  last_seen_at: string | null;
  claude_available: boolean;
  codex_available: boolean;
  unity_available: boolean;
  unity_mcp_available: boolean;
  created_at: string;
  updated_at: string;
  effective_status: WorkerStatus | null;
  is_stale: boolean;
}

export interface Task {
  id: number;
  public_id: string;
  title: string;
  description: string | null;
  project_id: number | null;
  agent_type: AgentType | null;
  status: TaskStatus;
  priority: TaskPriority;
  discord_guild_id: string | null;
  discord_channel_id: string | null;
  discord_thread_id: string | null;
  requested_by: string | null;
  worker_id: number | null;
  process_id: number | null;
  session_id: string | null;
  working_directory: string | null;
  branch: string | null;
  worktree_path: string | null;
  start_commit: string | null;
  end_commit: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  last_activity_at: string;
  result_summary: string | null;
  error_message: string | null;
  tests_status: CheckStatus;
  build_status: CheckStatus;
  exit_code: number | null;
  is_archived: boolean;
  approved_at: string | null;
  rejected_at: string | null;
  review_note: string | null;
  project: Project | null;
  worker: Worker | null;
}

export interface TaskListResponse {
  items: Task[];
  total: number;
  limit: number;
  offset: number;
}

export interface TaskEvent {
  id: number;
  task_id: number;
  event_type: string;
  message: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface TaskEventListResponse {
  items: TaskEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface Artifact {
  id: number;
  task_id: number;
  artifact_type: ArtifactType;
  name: string;
  local_path: string | null;
  url: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface ProjectSummary {
  project: Project;
  running_tasks: number;
  needs_review_tasks: number;
  failed_tasks: number;
  last_completed_task_id: string | null;
  last_completed_at: string | null;
}

export interface DashboardSummary {
  running_count: number;
  waiting_for_user_count: number;
  waiting_for_approval_count: number;
  needs_review_count: number;
  failed_today_count: number;
  completed_today_count: number;
  active_tasks: Task[];
  recent_failed_tasks: Task[];
  workers: Worker[];
  projects: ProjectSummary[];
}

export interface HealthResponse {
  status: string;
  database: string;
  time_utc: string;
  version: string;
}

// --- OpenACP channel bindings ---------------------------------------------

export interface ChannelBinding {
  channel_id: string;
  agent: string;
  workspace: string;
  workspace_exists: boolean;
  /** Agent Deck project at this workspace path, resolved on read. */
  project_id: number | null;
  project_name: string | null;
}

export interface OpenAcpSession {
  id: string;
  agent: string;
  name: string;
  /** "active" | "initializing" | "finished" | "error" */
  status: string;
  /** True while the session still holds an agent process. Computed by the API. */
  active: boolean;
  workspace: string;
  project_id: number | null;
  project_name: string | null;
  created_at: string;
  last_active_at: string;
  prompt_running: boolean;
  queue_depth: number;
  dangerous_mode: boolean;
}

export interface InvalidBinding {
  channel_id: string;
  reason: string;
}

export interface ChannelBindingsResponse {
  bindings: ChannelBinding[];
  invalid_entries: InvalidBinding[];
  settings_path: string;
  revision: string;
  restart_required: boolean;
}

export interface OpenAcpAgent {
  id: string;
  name: string;
}

export interface HookStatus {
  installed: boolean | null;
  detail: string;
  checked_at: string;
}

export interface OpenAcpInstallStatus {
  cli_installed: boolean;
  cli_version: string | null;
  adapter_installed: boolean | null;
  npm_available: boolean;
  detail: string;
}

export interface OpenAcpInstallResult {
  ok: boolean;
  exit_code: number;
  output: string;
  status: OpenAcpInstallStatus;
}

export interface SettingsTransferStatus {
  live_exists: boolean;
  live_path: string;
  bundle_exists: boolean;
  bundle_path: string;
  bundle_modified: string | null;
  bundle_has_token: boolean | null;
}

export interface SettingsTransferResult {
  ok: boolean;
  action: string;
  path: string;
  has_token: boolean;
  detail: string;
}

export interface ScreenshotStatus {
  installed: boolean;
  version: string | null;
  python_path: string;
  detail: string;
}

export interface ScreenshotInstallResult {
  ok: boolean;
  exit_code: number;
  output: string;
  status: ScreenshotStatus;
}

export interface ScreenshotCaptureResult {
  ok: boolean;
  filename: string | null;
  url: string | null;
  taken_at: string | null;
  width: number;
  height: number;
  detail: string;
}

export interface RedeployResult {
  ok: boolean;
  installed: boolean | null;
  exit_code: number;
  output: string;
  restart_required: boolean;
}

export interface DaemonStatus {
  running: boolean;
  status: string;
  pid: number | null;
  mode: string | null;
  channels: string[];
  active_sessions: number;
  /** Runs in its own console window — cannot be controlled from here. */
  foreground: boolean;
  detail: string;
}

export interface DaemonActionResult {
  ok: boolean;
  action: string;
  output: string;
  status: DaemonStatus;
}

export interface SessionActionResult {
  ok: boolean;
  session_id: string;
}
