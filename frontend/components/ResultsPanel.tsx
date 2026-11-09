"use client";

import type { ScoredRoute } from "@/lib/types";

interface ResultsPanelProps {
  routes: ScoredRoute[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  overlapSummary?: { distanceKm: number; percentage: number } | null;
  redSpotCount?: number;
}

function FlagLine({ tone, children }: { tone: "none" | "overlap" | "redZone"; children: React.ReactNode }) {
  const dot = { none: "bg-ink-dim", overlap: "bg-overlap", redZone: "bg-red-zone" }[tone];
  return (
    <div className="flex items-center gap-1.5 text-xs text-ink-dim">
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {children}
    </div>
  );
}

export default function ResultsPanel({
  routes,
  selectedIndex,
  onSelect,
  overlapSummary,
  redSpotCount,
}: ResultsPanelProps) {
  if (routes.length === 0) return null;

  return (
    <section className="absolute inset-x-4 bottom-4 z-10 rounded-xl border border-border bg-panel/85 p-4 backdrop-blur-md sm:inset-x-5 sm:p-5">
      <div className="mb-3.5 flex items-center justify-between">
        <h3 className="font-display text-sm font-semibold">{routes.length} routes compared</h3>
        {overlapSummary && (
          <span className="font-mono text-[11.5px] text-overlap">
            {overlapSummary.distanceKm} km overlap
            {typeof redSpotCount === "number" ? ` · ${redSpotCount} red spot${redSpotCount === 1 ? "" : "s"} flagged` : ""}
          </span>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {routes.map((r, i) => {
          const hitNames = r.red_spot_hits.filter((h) => h.intersects).map((h) => h.red_spot.name);
          return (
            <button
              key={i}
              onClick={() => onSelect(i)}
              className={`rounded-lg border p-3.5 text-left transition-colors ${
                i === selectedIndex
                  ? "border-accent shadow-[0_0_0_1px_rgb(var(--c-accent))]"
                  : "border-border hover:border-accent/60"
              } bg-panel-2`}
            >
              <div className="mb-1.5 font-mono text-[10px] uppercase tracking-wider text-ink-dim">
                {r.tier}
              </div>
              <div className="mb-2 font-body text-[14.5px] font-semibold">
                {r.route.duration_min} min · {r.route.distance_km} km
              </div>
              <div className="flex flex-col gap-1">
                {r.overlap.percentage === 0 ? (
                  <FlagLine tone="none">No overlap</FlagLine>
                ) : (
                  <FlagLine tone="overlap">{r.overlap.distance_km} km overlap</FlagLine>
                )}
                {hitNames.length === 0 ? (
                  <FlagLine tone="none">No red spots</FlagLine>
                ) : (
                  <FlagLine tone="redZone">Enters {hitNames.join(", ")}</FlagLine>
                )}
              </div>
            </button>
          );
        })}
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
