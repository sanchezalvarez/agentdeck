import argparse
import json
import sys
from typing import Any

from . import __version__
from .client import AgentHubConnectionError, AgentHubError, HubClient

EXIT_OK = 0
EXIT_API_ERROR = 1
EXIT_USAGE = 2
EXIT_CONNECTION = 3


def parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes", "y", "on"}:
        return True
    if lowered in {"false", "0", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"expected true/false, got '{value}'")


def parse_metadata(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"--metadata-json is not valid JSON: {exc}")
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("--metadata-json must be a JSON object")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-report",
        description="Report Claude Code / Codex agent work to the local Rembrosoft Agent Hub.",
    )
    parser.add_argument("--version", action="version", version=f"agent-report {__version__}")
    parser.add_argument("--url", help="Agent Hub URL (default: AGENT_HUB_URL or http://127.0.0.1:8765)")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds (default 15)")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_json(p: argparse.ArgumentParser) -> None:
        p.add_argument("--json", action="store_true", help="Print the raw JSON response")

    p = sub.add_parser("create", help="Create a new task")
    p.add_argument("--title", required=True)
    p.add_argument("--description")
    p.add_argument("--project", help="Project slug or numeric ID")
    p.add_argument("--agent", choices=["claude", "codex"], dest="agent")
    p.add_argument("--priority", choices=["low", "normal", "high", "critical"], default="normal")
    p.add_argument("--requested-by")
    p.add_argument("--discord-guild-id")
    p.add_argument("--discord-channel-id")
    p.add_argument("--discord-thread-id")
    add_json(p)

    p = sub.add_parser("start", help="Mark a task as started (status: running)")
    p.add_argument("--task", required=True, help="Task ID (REM-104 or numeric)")
    p.add_argument("--agent", choices=["claude", "codex"], dest="agent")
    p.add_argument("--project", help="Project slug or numeric ID")
    p.add_argument("--worker")
    p.add_argument("--process-id", type=int)
    p.add_argument("--session-id")
    p.add_argument("--working-directory")
    p.add_argument("--branch")
    p.add_argument("--worktree-path")
    p.add_argument("--start-commit")
    p.add_argument("--message")
    add_json(p)

    p = sub.add_parser("progress", help="Report a progress event")
    p.add_argument("--task", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--status", choices=[
        "queued", "starting", "running", "waiting_for_user", "waiting_for_approval",
        "testing", "blocked"])
    p.add_argument("--metadata-json", type=parse_metadata, dest="metadata")
    add_json(p)

    p = sub.add_parser("testing", help="Report tests/build state")
    p.add_argument("--task", required=True)
    p.add_argument("--kind", required=True, choices=["tests", "build"])
    p.add_argument("--status", required=True, choices=["started", "passed", "failed", "not_run"])
    p.add_argument("--message")
    add_json(p)

    p = sub.add_parser("finish", help="Finish a task (status: needs_review)")
    p.add_argument("--task", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--branch")
    p.add_argument("--commit")
    p.add_argument("--start-commit")
    p.add_argument("--tests", choices=["pending", "running", "passed", "failed", "not_run"])
    p.add_argument("--build", choices=["pending", "running", "passed", "failed", "not_run"])
    p.add_argument("--exit-code", type=int)
    add_json(p)

    p = sub.add_parser("fail", help="Mark a task as failed")
    p.add_argument("--task", required=True)
    p.add_argument("--error", required=True)
    p.add_argument("--tests", choices=["pending", "running", "passed", "failed", "not_run"])
    p.add_argument("--build", choices=["pending", "running", "passed", "failed", "not_run"])
    p.add_argument("--exit-code", type=int)
    add_json(p)

    p = sub.add_parser("block", help="Mark a task as blocked")
    p.add_argument("--task", required=True)
    p.add_argument("--reason", required=True)
    add_json(p)

    p = sub.add_parser("artifact", help="Attach an artifact to a task")
    p.add_argument("--task", required=True)
    p.add_argument("--type", required=True, dest="artifact_type", choices=[
        "log", "screenshot", "test_report", "build", "diff", "patch", "document", "other"])
    p.add_argument("--name", required=True)
    p.add_argument("--path", dest="local_path")
    p.add_argument("--url", dest="artifact_url")
    p.add_argument("--metadata-json", type=parse_metadata, dest="metadata")
    add_json(p)

    p = sub.add_parser("heartbeat", help="Send a worker heartbeat")
    p.add_argument("--worker", required=True)
    p.add_argument("--hostname")
    p.add_argument("--operating-system")
    p.add_argument("--status", choices=["online", "offline", "degraded", "unknown"], default="online")
    p.add_argument("--claude-available", type=parse_bool)
    p.add_argument("--codex-available", type=parse_bool)
    p.add_argument("--unity-available", type=parse_bool)
    p.add_argument("--unity-mcp-available", type=parse_bool)
    add_json(p)

    p = sub.add_parser("status", help="Show a task summary")
    p.add_argument("--task", required=True)
    p.add_argument("--events", type=int, default=5, help="Number of recent events to show (default 5)")
    add_json(p)

    return parser


def drop_none(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if v is not None}


def print_task_line(task: dict[str, Any]) -> None:
    project = task.get("project") or {}
    print(f"Task:     {task['public_id']}  {task['title']}")
    print(f"Status:   {task['status']}   Priority: {task['priority']}")
    if project:
        print(f"Project:  {project.get('name')} ({project.get('slug')})")


def cmd_create(client: HubClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.post("/api/tasks", drop_none({
        "title": args.title,
        "description": args.description,
        "project": args.project,
        "agent_type": args.agent,
        "priority": args.priority,
        "requested_by": args.requested_by,
        "discord_guild_id": args.discord_guild_id,
        "discord_channel_id": args.discord_channel_id,
        "discord_thread_id": args.discord_thread_id,
    }))


def cmd_start(client: HubClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.post(f"/api/tasks/{args.task}/start", drop_none({
        "agent_type": args.agent,
        "project": args.project,
        "worker": args.worker,
        "process_id": args.process_id,
        "session_id": args.session_id,
        "working_directory": args.working_directory,
        "branch": args.branch,
        "worktree_path": args.worktree_path,
        "start_commit": args.start_commit,
        "message": args.message,
    }))


def cmd_progress(client: HubClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.post(f"/api/tasks/{args.task}/progress", drop_none({
        "message": args.message,
        "status": args.status,
        "metadata": args.metadata,
    }))


def cmd_testing(client: HubClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.post(f"/api/tasks/{args.task}/testing", drop_none({
        "kind": args.kind,
        "status": args.status,
        "message": args.message,
    }))


def cmd_finish(client: HubClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.post(f"/api/tasks/{args.task}/finish", drop_none({
        "summary": args.summary,
        "branch": args.branch,
        "commit": args.commit,
        "start_commit": args.start_commit,
        "tests": args.tests,
        "build": args.build,
        "exit_code": args.exit_code,
    }))


def cmd_fail(client: HubClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.post(f"/api/tasks/{args.task}/fail", drop_none({
        "error": args.error,
        "tests": args.tests,
        "build": args.build,
        "exit_code": args.exit_code,
    }))


def cmd_block(client: HubClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.post(f"/api/tasks/{args.task}/block", {"reason": args.reason})


def cmd_artifact(client: HubClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.post(f"/api/tasks/{args.task}/artifacts", drop_none({
        "artifact_type": args.artifact_type,
        "name": args.name,
        "local_path": args.local_path,
        "url": args.artifact_url,
        "metadata": args.metadata,
    }))


def cmd_heartbeat(client: HubClient, args: argparse.Namespace) -> dict[str, Any]:
    return client.post("/api/workers/heartbeat", drop_none({
        "worker": args.worker,
        "hostname": args.hostname,
        "operating_system": args.operating_system,
        "status": args.status,
        "claude_available": args.claude_available,
        "codex_available": args.codex_available,
        "unity_available": args.unity_available,
        "unity_mcp_available": args.unity_mcp_available,
    }))


def cmd_status(client: HubClient, args: argparse.Namespace) -> dict[str, Any]:
    task = client.get(f"/api/tasks/{args.task}")
    events = client.get(f"/api/tasks/{args.task}/events",
                        params={"order": "desc", "limit": max(args.events, 1)})
    return {"task": task, "events": list(reversed(events["items"]))}


HANDLERS = {
    "create": cmd_create,
    "start": cmd_start,
    "progress": cmd_progress,
    "testing": cmd_testing,
    "finish": cmd_finish,
    "fail": cmd_fail,
    "block": cmd_block,
    "artifact": cmd_artifact,
    "heartbeat": cmd_heartbeat,
    "status": cmd_status,
}


def render(command: str, result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return
    if command == "create":
        print(f"Created task {result['public_id']}: {result['title']}")
        print(f"  status: {result['status']}, priority: {result['priority']}")
        if result.get("project"):
            print(f"  project: {result['project']['name']} ({result['project']['slug']})")
        return
    if command == "status":
        task = result["task"]
        print_task_line(task)
        if task.get("agent_type"):
            print(f"Agent:    {task['agent_type']}")
        if task.get("branch"):
            print(f"Branch:   {task['branch']}")
        print(f"Tests:    {task['tests_status']}   Build: {task['build_status']}")
        if task.get("result_summary"):
            print(f"Summary:  {task['result_summary']}")
        if task.get("error_message"):
            print(f"Error:    {task['error_message']}")
        if result["events"]:
            print("Recent events:")
            for event in result["events"]:
                message = f" — {event['message']}" if event.get("message") else ""
                print(f"  [{event['created_at']}] {event['event_type']}{message}")
        return
    if command == "heartbeat":
        print(f"Heartbeat recorded for worker '{result['name']}' "
              f"(status: {result['status']}, last seen: {result['last_seen_at']})")
        return
    if command == "artifact":
        print(f"Artifact #{result['id']} '{result['name']}' added to task {args_task_of(result)}")
        return
    # Lifecycle commands return the task
    print(f"OK — task {result['public_id']} is now '{result['status']}'")


def args_task_of(artifact: dict[str, Any]) -> str:
    return f"#{artifact.get('task_id')}"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    client = HubClient(base_url=args.url, timeout=args.timeout)
    handler = HANDLERS[args.command]
    try:
        result = handler(client, args)
    except AgentHubError as exc:
        print(f"ERROR: {exc.detail} (HTTP {exc.status_code})", file=sys.stderr)
        return EXIT_API_ERROR
    except AgentHubConnectionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_CONNECTION
    render(args.command, result, getattr(args, "json", False))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
