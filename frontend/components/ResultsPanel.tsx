"use client";

import type { ScoredRoute } from "@/lib/types";

interface ResultsPanelProps {
  routes: ScoredRoute[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  overlapSummary?: { distanceKm: number; percentage: number } | null;
  redSpotCount?: number;
  /** "overlay" floats over the bottom of the map (desktop); "inline" sits in the bottom sheet (phones). */
  placement?: "overlay" | "inline";
}

const PLACEMENT_CLASS = {
  overlay: "absolute inset-x-4 bottom-4 z-10 rounded-xl border border-border bg-panel/85 p-4 backdrop-blur-md sm:inset-x-5 sm:p-5",
  inline: "",
};

function FlagLine({ tone, children }: { tone: "good" | "warn" | "bad"; children: React.ReactNode }) {
  const dot = { good: "bg-route-a", warn: "bg-[#F5C24B]", bad: "bg-ember" }[tone];
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
  placement = "overlay",
}: ResultsPanelProps) {
  if (routes.length === 0) return null;

  return (
    <section className={PLACEMENT_CLASS[placement]}>
      <div className="mb-3.5 flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <h3 className="font-display text-sm font-semibold">{routes.length} routes compared</h3>
        {overlapSummary && (
          <span className="font-mono text-[11.5px] text-ember">
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
                  ? "border-route-a shadow-[0_0_0_1px_#5EE6C4]"
                  : "border-border hover:border-route-a/60"
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
                  <FlagLine tone="good">No overlap</FlagLine>
                ) : r.overlap.percentage < 10 ? (
                  <FlagLine tone="warn">{r.overlap.distance_km} km overlap</FlagLine>
                ) : (
                  <FlagLine tone="bad">{r.overlap.distance_km} km overlap</FlagLine>
                )}
                {hitNames.length === 0 ? (
                  <FlagLine tone="good">No red spots</FlagLine>
                ) : (
                  <FlagLine tone="bad">Enters {hitNames.join(", ")}</FlagLine>
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
