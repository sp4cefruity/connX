"use client";

import { useEffect, useState } from "react";
import { pingBackend } from "@/lib/api";

const SHOW_AFTER_MS = 2500; // an awake backend answers well inside this
const RETRY_EVERY_MS = 3000;
const MAX_TRIES = 30;

/**
 * Wakes the hosted backend, which sleeps when idle. `silent` (landing page)
 * only sends the ping, so the server is usually up by the time the visitor
 * opens the planner; otherwise a small notice shows while it is still waking.
 */
export default function BackendWake({ silent = false }: { silent?: boolean }) {
  const [waking, setWaking] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const slow = setTimeout(() => {
      if (!cancelled) setWaking(true);
    }, SHOW_AFTER_MS);

    (async () => {
      for (let i = 0; i < MAX_TRIES && !cancelled; i++) {
        if (await pingBackend()) break;
        await new Promise((r) => setTimeout(r, RETRY_EVERY_MS));
      }
      clearTimeout(slow);
      if (!cancelled) setWaking(false);
    })();

    return () => {
      cancelled = true;
      clearTimeout(slow);
    };
  }, []);

  if (silent || !waking) return null;
  return (
    <div
      role="status"
      className="fixed left-1/2 top-14 z-50 flex -translate-x-1/2 items-center gap-2 whitespace-nowrap rounded-full border border-border bg-panel/90 px-3 py-1.5 font-mono text-[11px] text-ink-dim backdrop-blur-md"
    >
      <svg className="h-3 w-3 animate-spin" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" opacity="0.3" />
        <path d="M8 2a6 6 0 0 1 6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      Waking up the server, up to a minute…
    </div>
  );
}
