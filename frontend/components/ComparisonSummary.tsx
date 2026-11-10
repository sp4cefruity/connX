"use client";

import type { ReactNode } from "react";
import RouteFlags from "@/components/RouteFlags";
import type { CardPlacement } from "@/lib/layout";
import type { ComparisonView, RouteResult } from "@/lib/types";

/** Route A against Route B: the primary comparison view's summary card. */
const PLACEMENT_CLASS: Record<CardPlacement, string> = {
  overlay:
    "absolute inset-x-4 bottom-4 z-10 rounded-xl border border-border bg-panel/85 p-4 backdrop-blur-md sm:inset-x-5 sm:right-auto sm:w-[340px] sm:p-5",
  inline: "",
};

/** The two routes' rows differ only in their role colour. */
const TONE = {
  routeA: { text: "text-route-a", dot: "bg-route-a" },
  routeB: { text: "text-route-b", dot: "bg-route-b" },
} as const;

function RouteStat({
  route,
  tone,
  children,
  className = "",
}: {
  route: RouteResult;
  tone: keyof typeof TONE;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex items-center gap-2 font-body text-[14.5px] font-semibold ${TONE[tone].text} ${className}`}>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${TONE[tone].dot}`} />
      <span>
        {route.duration_min} min · {route.distance_km} km
      </span>
      {children}
    </div>
  );
}

export default function ComparisonSummary({
  view,
  placement = "overlay",
}: {
  view: ComparisonView;
  placement?: CardPlacement;
}) {
  const { route, comparison_route, overlap } = view;
  return (
    <section className={PLACEMENT_CLASS[placement]}>
      <div className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-dim">Your route vs theirs</div>
      <RouteStat route={route} tone="routeA" className="mb-1">
        {overlap.percentage > 0 && (
          <span className="ml-1 font-mono text-[11.5px] font-normal text-overlap">{overlap.percentage}% shared</span>
        )}
      </RouteStat>
      <RouteStat route={comparison_route} tone="routeB" className="mb-2.5" />
      <RouteFlags view={view} />
    </section>
  );
}
