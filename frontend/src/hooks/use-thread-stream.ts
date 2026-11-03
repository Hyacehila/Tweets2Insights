"use client";
import { useEffect, useState } from "react";
import type { AgentUpdate } from "@/lib/types";

export function useThreadStream(threadId?: string) {
  const [updates, setUpdates] = useState<AgentUpdate[]>([]);
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    setUpdates([]);
    if (!threadId) return;
    const key = `t2i-stream:${threadId}`;
    const cursor = sessionStorage.getItem(key) ?? "0";
    const stream = new EventSource(`/api/threads/${threadId}/events?after=${encodeURIComponent(cursor)}`);
    stream.onopen = () => setConnected(true);
    stream.onerror = () => setConnected(false);
    const receive = (event: MessageEvent<string>) => {
      if (event.lastEventId) sessionStorage.setItem(key, event.lastEventId);
      setUpdates((old) => [...old.slice(-49), JSON.parse(event.data) as AgentUpdate]);
    };
    for (const name of ["run_started", "agent_update", "run_finished"]) stream.addEventListener(name, receive as EventListener);
    return () => { stream.close(); setConnected(false); };
  }, [threadId]);
  return { updates, connected };
}
