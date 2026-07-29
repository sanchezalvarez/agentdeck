"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { API_URL, apiGet, apiPost } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import type {
  ScreenshotCaptureResult,
  ScreenshotInstallResult,
  ScreenshotStatus,
} from "@/types/api";

export default function SystemPage() {
  const [shot, setShot] = useState<ScreenshotStatus | null>(null);
  const [installing, setInstalling] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [installOutput, setInstallOutput] = useState<string | null>(null);
  const [capture, setCapture] = useState<ScreenshotCaptureResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const status = await apiGet<ScreenshotStatus>("/api/system/screenshot/status");
      setShot(status);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load system status");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const installMss = async () => {
    setInstalling(true);
    setError(null);
    setInstallOutput(null);
    try {
      const result = await apiPost<ScreenshotInstallResult>("/api/system/screenshot/install");
      setShot(result.status);
      setInstallOutput(result.output);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Screenshot library install failed");
    } finally {
      setInstalling(false);
    }
  };

  const takeScreenshot = async () => {
    setCapturing(true);
    setError(null);
    try {
      const result = await apiPost<ScreenshotCaptureResult>("/api/system/screenshot/capture");
      setCapture(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Screenshot capture failed");
    } finally {
      setCapturing(false);
    }
  };

  const shotBadge = () => {
    if (!shot) return <Badge className="tag-riso-muted">checking…</Badge>;
    if (shot.installed) return <Badge className="tag-riso-teal">installed</Badge>;
    return <Badge className="tag-riso-destructive">not installed</Badge>;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="riso-title animate-ink-in">System</h1>
        <Button variant="outline" size="sm" disabled={installing || capturing} onClick={refresh}>
          Refresh
        </Button>
      </div>

      {error && <p className="text-sm text-[color:var(--destructive)]">{error}</p>}

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Screenshots (Python / mss)</CardTitle>
          {shotBadge()}
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p className="text-[color:var(--muted-foreground)]">{shot?.detail ?? "Checking screenshot library…"}</p>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-[color:var(--muted-foreground)]">
            <span>
              mss version: <span className="font-mono">{shot?.version ?? "—"}</span>
            </span>
          </div>
          <p className="text-xs text-[color:var(--muted-foreground)]">
            Installs the <span className="font-mono">mss</span> screenshot library into the backend
            venv (like <span className="font-mono">pip install mss</span>). Capture grabs the
            <strong> primary monitor of the PC the backend runs on</strong> and saves a PNG.
          </p>

          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={installing || capturing}
              onClick={installMss}
            >
              {installing
                ? "Installing…"
                : shot?.installed
                  ? "Reinstall / update"
                  : "Install mss"}
            </Button>
            <Button
              size="sm"
              disabled={capturing || installing || !shot?.installed}
              onClick={takeScreenshot}
            >
              {capturing ? "Capturing…" : "Capture screenshot"}
            </Button>
          </div>

          {installOutput && (
            <pre className="overflow-x-auto rounded bg-[color:var(--background-3)] p-2 text-xs text-[color:var(--foreground)]">
              {installOutput}
            </pre>
          )}

          {capture?.ok && capture.url && (
            <div className="space-y-2">
              <p className="text-xs text-[color:var(--muted-foreground)]">
                {capture.width}×{capture.height}
                {capture.taken_at ? ` · ${formatRelative(capture.taken_at)}` : ""} ·{" "}
                <span className="font-mono">{capture.filename}</span>
              </p>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`${API_URL}${capture.url}`}
                alt="Latest screenshot"
                className="max-w-full rounded border border-[color:var(--border-strong)]"
              />
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Prerequisites (Python / Node)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="text-[color:var(--muted-foreground)]">
            Python and Node cannot be installed from here — this dashboard is itself a Python +
            Node app, so they must exist before it can run.
          </p>
          <p className="text-xs text-[color:var(--muted-foreground)]">
            On a fresh PC, double-click{" "}
            <span className="font-mono">install-agent-deck-prerequisites.bat</span> in the repository
            root. It installs Python 3.12+, Node 20+ and PowerShell 7 via winget, then runs setup.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
