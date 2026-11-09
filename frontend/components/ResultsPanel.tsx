"use client";

import RouteFlags from "@/components/RouteFlags";
import type { ScoredRoute } from "@/lib/types";

interface ResultsPanelProps {
  routes: ScoredRoute[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}

/** The ranked alternatives for Route A: the secondary Recommendation view. */
export default function ResultsPanel({ routes, selectedIndex, onSelect }: ResultsPanelProps) {
  if (routes.length === 0) return null;

  return (
    <section className="absolute inset-x-4 bottom-4 z-10 rounded-xl border border-border bg-panel/85 p-4 backdrop-blur-md sm:inset-x-5 sm:p-5">
      <div className="mb-3.5 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 className="font-display text-sm font-semibold">Recommendation</h3>
        <span className="font-mono text-[11px] text-ink-dim">
          {routes.length} route{routes.length === 1 ? "" : "s"} ranked by time, overlap, close passes and red spots
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {routes.map((r, i) => (
          <button
            key={i}
            onClick={() => onSelect(i)}
            className={`rounded-lg border p-3.5 text-left transition-colors ${
              i === selectedIndex
                ? "border-route-a shadow-[0_0_0_1px_#5EE6C4]"
                : "border-border hover:border-route-a/60"
            } bg-panel-2`}
          >
            <div className="mb-1.5 font-mono text-[10px] uppercase tracking-wider text-ink-dim">{r.tier}</div>
            <div className="mb-2 font-body text-[14.5px] font-semibold">
              {r.route.duration_min} min · {r.route.distance_km} km
            </div>
            <RouteFlags view={r} />
          </button>
        ))}
      </div>

      {routes[selectedIndex] && (
        <div className="mt-3.5 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border pt-3 font-mono text-[11px] text-ink-dim">
          {routes[selectedIndex].explanation.map((line, i) => (
            <span key={i}>· {line}</span>
          ))}
        </div>
      )}
    </section>
  );
}
