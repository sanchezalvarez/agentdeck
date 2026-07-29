"use client";

import { useEffect, useRef, useState } from "react";
import { API_URL } from "./api";

export type SseState = "connecting" | "live" | "polling";

/**
 * Subscribes to the Agent Hub SSE stream and calls `onUpdate` when relevant
 * events arrive. Falls back to interval polling while the stream is down.
 */
export function useLive(onUpdate: () => void, pollMs = 10000): SseState {
  const [state, setState] = useState<SseState>("connecting");
  const callbackRef = useRef(onUpdate);
  callbackRef.current = onUpdate;

  useEffect(() => {
    let closed = false;
    let source: EventSource | null = null;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    // Debounce bursts of SSE events into one refresh.
    let refreshTimer: ReturnType<typeof setTimeout> | null = null;

    const scheduleRefresh = () => {
      if (refreshTimer) return;
      refreshTimer = setTimeout(() => {
        refreshTimer = null;
        callbackRef.current();
      }, 250);
    };

    const startPolling = () => {
      if (!pollTimer) {
        pollTimer = setInterval(() => callbackRef.current(), pollMs);
      }
    };

    const stopPolling = () => {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    };

    const connect = () => {
      if (closed) return;
      source = new EventSource(`${API_URL}/api/events/stream`);
      const events = [
        "task_created",
        "task_status_changed",
        "task_progress",
        "task_finished",
        "task_failed",
        "task_approved",
        "task_rejected",
        "worker_heartbeat",
        "channel_bindings_saved",
      ];
      for (const name of events) {
        source.addEventListener(name, scheduleRefresh);
      }
      source.addEventListener("connected", () => {
        setState("live");
        stopPolling();
      });
      source.onerror = () => {
        source?.close();
        source = null;
        if (closed) return;
        setState("polling");
        startPolling();
        reconnectTimer = setTimeout(connect, 15000);
      };
    };

    connect();

    return () => {
      closed = true;
      source?.close();
      stopPolling();
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (refreshTimer) clearTimeout(refreshTimer);
    };
  }, [pollMs]);

  return state;
}
