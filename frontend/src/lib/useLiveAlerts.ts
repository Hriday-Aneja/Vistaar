"use client";
import { useEffect, useRef, useState } from "react";
import { wsUrl } from "@/lib/api";

export type LiveAlert = {
  event: "alert";
  kind: "pulse" | "sales_drop";
  id: number | null;
  title: string;
  action: string;
  why: string;
  created_at: string;
};

export const POLL_MS = 30_000;

/**
 * Live Pulse / sales-drop alerts. Opens /ws/alerts and calls onAlert for each pushed alert.
 * If the socket cannot connect, closes, or the server says Redis is unavailable, the page falls back to
 * polling: onPoll runs every 30 s (re-read the existing alerts API) and the socket is retried on each tick.
 * While the socket is open there is no polling.
 */
export function useLiveAlerts(onAlert: (a: LiveAlert) => void, onPoll: () => void) {
  const [mode, setMode] = useState<"connecting" | "live" | "polling">("connecting");
  const alertRef = useRef(onAlert);
  const pollRef = useRef(onPoll);
  alertRef.current = onAlert;
  pollRef.current = onPoll;

  useEffect(() => {
    let stopped = false;
    let ws: WebSocket | null = null;

    function connect() {
      if (stopped || (ws && ws.readyState <= WebSocket.OPEN)) return;
      let socket: WebSocket;
      try { socket = new WebSocket(wsUrl("/ws/alerts")); }
      catch { setMode("polling"); return; }
      ws = socket;
      socket.onmessage = (m) => {
        let d: any;
        try { d = JSON.parse(m.data); } catch { return; }
        if (d.event === "connected") setMode("live");
        else if (d.event === "alert") alertRef.current(d as LiveAlert);
        else if (d.event === "unavailable") setMode("polling");
      };
      const lost = () => { if (!stopped && ws === socket) { ws = null; setMode("polling"); } };
      socket.onerror = lost;
      socket.onclose = lost;
    }

    connect();
    const timer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) return;  // live: the server pushes, no need to poll
      pollRef.current();
      connect();
    }, POLL_MS);

    return () => { stopped = true; clearInterval(timer); ws?.close(); };
  }, []);

  return { mode };
}
