"use client";

import OpenInGoogleMaps from "@/components/OpenInGoogleMaps";
import RouteFlags from "@/components/RouteFlags";
import type { CardPlacement } from "@/lib/layout";
import type { ScoredRoute } from "@/lib/types";

interface ResultsPanelProps {
  routes: ScoredRoute[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  placement?: CardPlacement;
}

const PLACEMENT_CLASS: Record<CardPlacement, string> = {
  overlay: "absolute inset-x-4 bottom-4 z-10 rounded-xl border border-border bg-panel/85 p-4 backdrop-blur-md sm:inset-x-5 sm:p-5",
  inline: "",
};

/** The ranked alternatives for Route A: the secondary Recommendation view. */
export default function ResultsPanel({ routes, selectedIndex, onSelect, placement = "overlay" }: ResultsPanelProps) {
  if (routes.length === 0) return null;

  return (
    <section className={PLACEMENT_CLASS[placement]}>
      <div className="mb-3.5 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 className="font-display text-sm font-semibold">Recommendation</h3>
        <span className="font-mono text-[11px] text-ink-dim">
          {routes.length} route{routes.length === 1 ? "" : "s"} ranked by time, overlap, close passes and red spots
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {routes.map((r, i) => {
          const recommended = r.tier === "recommended";
          return (
            <div
              key={i}
              className={`rounded-lg border bg-panel-2 transition-shadow ${
                recommended
                  ? "border-accent shadow-[0_0_14px_3px_rgb(var(--c-accent)/0.55),0_0_32px_8px_rgb(var(--c-accent)/0.25)]"
                  : i === selectedIndex
                    ? "border-accent"
                    : "border-border hover:border-accent/60"
              } ${i === selectedIndex ? "ring-1 ring-accent" : ""}`}
            >
              <button onClick={() => onSelect(i)} className="block w-full p-3.5 pb-2 text-left">
                <div className="mb-1.5 font-mono text-[10px] uppercase tracking-wider text-ink-dim">{r.tier}</div>
                <div className="mb-2 font-body text-[14.5px] font-semibold">
                  {r.route.duration_min} min · {r.route.distance_km} km
                </div>
                <RouteFlags view={r} />
              </button>
              <div className="flex px-3.5 pb-3">
                <OpenInGoogleMaps route={r.route} label={`${r.tier} route`} />
              </div>
            </div>
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
