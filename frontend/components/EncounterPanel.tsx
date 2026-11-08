"use client";

import { formatAlong, formatGap } from "@/lib/encounters";
import type { Encounter } from "@/lib/types";

interface EncounterPanelProps {
  /** Encounters of the selected route, already ordered along Route A. */
  encounters: Encounter[];
  /** Length of the selected route, to say how far along each one is. */
  routeDistanceKm: number;
  dangerDistanceM: number;
  onSelect: (encounter: Encounter) => void;
}

export default function EncounterPanel({
  encounters,
  routeDistanceKm,
  dangerDistanceM,
  onSelect,
}: EncounterPanelProps) {
  return (
    <div>
      <div className="mb-3 flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider">
        <span className="h-1.5 w-1.5 rounded-full bg-[#F5C24B]" />
        Close passes
        {encounters.length > 0 && <span className="text-ink-dim">· {encounters.length}</span>}
      </div>

      {encounters.length === 0 ? (
        <p className="font-mono text-[11px] text-ink-dim">
          Your route never comes within {formatGap(dangerDistanceM)} of theirs without sharing the road.
        </p>
      ) : (
        <ol className="flex flex-col gap-1.5">
          {encounters.map((e, i) => (
            <li key={`${e.start_fraction}-${i}`}>
              <button
                type="button"
                onClick={() => onSelect(e)}
                className="flex w-full items-center gap-3 rounded-md border border-border bg-panel-2 px-3 py-2 text-left transition-colors hover:border-[#F5C24B]/70"
              >
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#F5C24B] font-mono text-[10px] font-semibold text-[#1A1405]">
                  {i + 1}
                </span>
                <span className="flex-1 font-body text-[13px] font-semibold">{formatGap(e.min_gap_m)} gap</span>
                <span className="font-mono text-[10.5px] text-ink-dim">
                  {formatAlong(e, routeDistanceKm)} in
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}
      {encounters.length > 0 && (
        <p className="mt-2 font-mono text-[10px] text-ink-dim opacity-70">Click one to zoom the map to it.</p>
      )}
    </div>
  );
}
