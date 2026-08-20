"use client";

import { useState } from "react";
import type { LonLat, RedSpot } from "@/lib/types";

interface RedSpotPanelProps {
  redSpots: RedSpot[];
  onAdd: (payload: { name: string; radius_m: number; latitude: number; longitude: number }) => void;
  onDelete: (id: string) => void;
  pendingPoint: LonLat | null;
  onCancelPending: () => void;
  onStartAdding: () => void;
  isPicking: boolean;
}

const TYPE_ICON: Record<string, string> = {
  home: "🏠",
  office: "💼",
  school: "🎓",
  other: "❤️",
};

export default function RedSpotPanel({
  redSpots,
  onAdd,
  onDelete,
  pendingPoint,
  onCancelPending,
  onStartAdding,
  isPicking,
}: RedSpotPanelProps) {
  const [name, setName] = useState("");
  const [radius, setRadius] = useState(150);

  function save() {
    if (!pendingPoint || !name.trim()) return;
    onAdd({ name: name.trim(), radius_m: radius, latitude: pendingPoint.lat, longitude: pendingPoint.lon });
    setName("");
    setRadius(150);
  }

  return (
    <div>
      <div className="mb-3.5 flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider">
        Red spots
      </div>

      <div className="mb-3.5 flex flex-col gap-2">
        {redSpots.map((spot) => (
          <div
            key={spot.id}
            className="flex items-center justify-between rounded-md border border-border bg-panel-2 px-3 py-2 text-sm"
          >
            <span className="flex items-center gap-2">
              {TYPE_ICON[spot.type ?? "other"] ?? "📍"} {spot.name}
            </span>
            <div className="flex items-center gap-3">
              <span className="font-mono text-[10.5px] text-ink-dim">{spot.radius_m}m</span>
              <button
                onClick={() => onDelete(spot.id)}
                className="text-[11px] text-ink-dim hover:text-ember"
                aria-label={`Delete ${spot.name}`}
              >
                ✕
              </button>
            </div>
          </div>
        ))}
      </div>

      {pendingPoint ? (
        <div className="rounded-md border border-border bg-panel-2 p-3">
          <label className="mb-1 block text-[11px] text-ink-dim">Name</label>
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Home"
            className="mb-3 w-full rounded border border-border bg-bg px-2.5 py-1.5 text-sm outline-none focus:border-route-a"
          />
          <label className="mb-1 block text-[11px] text-ink-dim">
            Avoid radius — {radius}m
          </label>
          <input
            type="range"
            min={50}
            max={500}
            step={10}
            value={radius}
            onChange={(e) => setRadius(Number(e.target.value))}
            className="mb-3 w-full accent-ember"
          />
          <div className="flex gap-2">
            <button
              onClick={save}
              disabled={!name.trim()}
              className="flex-1 rounded bg-ember py-2 font-mono text-[11px] uppercase tracking-wide text-white disabled:opacity-40"
            >
              Save
            </button>
            <button
              onClick={onCancelPending}
              className="flex-1 rounded border border-border py-2 font-mono text-[11px] uppercase tracking-wide text-ink-dim"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={onStartAdding}
          className={`w-full rounded-md border border-dashed py-2.5 text-center font-mono text-[11.5px] transition-colors ${
            isPicking
              ? "border-route-a text-route-a"
              : "border-border text-ink-dim hover:border-ink-dim hover:text-ink"
          }`}
        >
          {isPicking ? "Tap the map to place it…" : "+ Add red spot"}
        </button>
      )}
    </div>
  );
}
