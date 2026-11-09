"use client";

import RouteFlags from "@/components/RouteFlags";
import type { CardPlacement } from "@/lib/layout";
import type { RouteView } from "@/lib/types";

/** Route A against Route B: the primary comparison view's summary card. */
const PLACEMENT_CLASS: Record<CardPlacement, string> = {
  overlay:
    "absolute inset-x-4 bottom-4 z-10 rounded-xl border border-border bg-panel/85 p-4 backdrop-blur-md sm:inset-x-5 sm:right-auto sm:w-[340px] sm:p-5",
  inline: "",
};

export default function ComparisonSummary({
  view,
  placement = "overlay",
}: {
  view: RouteView;
  placement?: CardPlacement;
}) {
  const { route, overlap } = view;
  return (
    <section className={PLACEMENT_CLASS[placement]}>
      <div className="mb-1 font-mono text-[10px] uppercase tracking-wider text-ink-dim">Your route vs theirs</div>
      <div className="mb-2.5 font-body text-[14.5px] font-semibold">
        {route.duration_min} min · {route.distance_km} km
        {overlap.percentage > 0 && (
          <span className="ml-2 font-mono text-[11.5px] font-normal text-overlap">{overlap.percentage}% shared</span>
        )}
      </div>
      <RouteFlags view={view} />
    </section>
  );
}
