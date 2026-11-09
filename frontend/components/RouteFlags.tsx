import { closePassSummary } from "@/lib/encounters";
import type { RouteView } from "@/lib/types";

function FlagLine({ tone, children }: { tone: "good" | "warn" | "bad"; children: React.ReactNode }) {
  const dot = { good: "bg-route-a", warn: "bg-[#F5C24B]", bad: "bg-ember" }[tone];
  return (
    <div className="flex items-center gap-1.5 text-xs text-ink-dim">
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {children}
    </div>
  );
}

/** Overlap, close passes and red spot hits for one Route A, as coloured lines. */
export default function RouteFlags({ view }: { view: RouteView }) {
  const { overlap, encounters, red_spot_hits } = view;
  const hitNames = red_spot_hits.filter((h) => h.intersects).map((h) => h.red_spot.name);
  return (
    <div className="flex flex-col gap-1">
      {overlap.percentage === 0 ? (
        <FlagLine tone="good">No overlap</FlagLine>
      ) : (
        <FlagLine tone={overlap.percentage < 10 ? "warn" : "bad"}>{overlap.distance_km} km overlap</FlagLine>
      )}
      <FlagLine tone={encounters.length === 0 ? "good" : "warn"}>{closePassSummary(encounters)}</FlagLine>
      {hitNames.length === 0 ? (
        <FlagLine tone="good">No red spots</FlagLine>
      ) : (
        <FlagLine tone="bad">Enters {hitNames.join(", ")}</FlagLine>
      )}
    </div>
  );
}
