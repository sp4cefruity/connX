"use client";

import { MAX_RADIUS_M, MIN_RADIUS_M, RADIUS_STEP_M, formatRadius } from "@/lib/redSpots";
import type { DraftPatch, RedSpotDraft } from "@/lib/useRedSpotEditor";
import type { RedSpot, RedSpotHit } from "@/lib/types";

interface RedSpotPanelProps {
  redSpots: RedSpot[];
  /** Red spot results for Route A from the last comparison; null before any comparison. */
  hits: RedSpotHit[] | null;
  /** False when "Avoid red spots" is off, so no hit check ran. */
  checking: boolean;
  draft: RedSpotDraft | null;
  picking: boolean;
  saving: boolean;
  error: string | null;
  onStartAdding: () => void;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
  onChangeDraft: (patch: DraftPatch) => void;
  onSave: () => void;
  onCancel: () => void;
}

function sameGeometry(spot: RedSpot, other: RedSpot) {
  return (
    spot.latitude === other.latitude && spot.longitude === other.longitude && spot.radius_m === other.radius_m
  );
}

function StatusLine({ spot, hits, checking }: { spot: RedSpot; hits: RedSpotHit[] | null; checking: boolean }) {
  if (hits === null || !checking) return null;
  const hit = hits.find((h) => h.red_spot.id === spot.id);
  if (!hit || !sameGeometry(spot, hit.red_spot)) {
    return <span className="text-[11px] text-ink-dim">Changed since last compare. Compare again to check.</span>;
  }
  if (hit.intersects) {
    return (
      <span className="text-[11px] font-medium text-red-zone">
        Hit: Route A passes {formatRadius(hit.min_distance_m)} from the centre
      </span>
    );
  }
  return (
    <span className="text-[11px] text-ink-dim">
      Clear: Route A stays {formatRadius(hit.min_distance_m)} from the centre
    </span>
  );
}

export default function RedSpotPanel({
  redSpots,
  hits,
  checking,
  draft,
  picking,
  saving,
  error,
  onStartAdding,
  onEdit,
  onDelete,
  onChangeDraft,
  onSave,
  onCancel,
}: RedSpotPanelProps) {
  return (
    <div>
      <div className="mb-3.5 flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider">
        Red spots
      </div>

      <div className="mb-3.5 flex flex-col gap-2">
        {redSpots.length === 0 && !draft && (
          <p className="text-xs text-ink-dim">
            Draw a circle around a place Route A should stay out of, like a friend&apos;s house.
          </p>
        )}
        {redSpots.map((spot) => {
          const hit = checking && hits?.find((h) => h.red_spot.id === spot.id);
          const isHit = !!hit && hit.intersects && sameGeometry(spot, hit.red_spot);
          const isEditing = draft?.id === spot.id;
          return (
            <div
              key={spot.id}
              className={`rounded-md border bg-panel-2 px-3 py-2 text-sm ${
                isEditing ? "border-red-zone/60" : isHit ? "border-red-zone/40" : "border-border"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <button
                  onClick={() => onEdit(spot.id)}
                  className="flex min-w-0 flex-1 items-center gap-2 text-left hover:text-ink"
                  aria-label={`Edit ${spot.name}`}
                >
                  <span className={`h-2 w-2 shrink-0 rounded-full ${isHit ? "bg-red-zone" : "bg-red-zone/40"}`} />
                  <span className="truncate">{spot.name}</span>
                </button>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="font-mono text-[10.5px] text-ink-dim">{formatRadius(spot.radius_m)}</span>
                  <button
                    onClick={() => onDelete(spot.id)}
                    className="-m-2 p-2 text-[11px] text-ink-dim hover:text-danger"
                    aria-label={`Delete ${spot.name}`}
                  >
                    ✕
                  </button>
                </div>
              </div>
              <div className="mt-1 pl-4">
                <StatusLine spot={spot} hits={hits} checking={checking} />
              </div>
            </div>
          );
        })}
      </div>

      {draft ? (
        <div className="rounded-md border border-border bg-panel-2 p-3">
          <label htmlFor="red-spot-name" className="mb-1 block text-[11px] text-ink-dim">
            Name
          </label>
          <input
            id="red-spot-name"
            autoFocus
            value={draft.name}
            maxLength={120}
            onChange={(e) => onChangeDraft({ name: e.target.value })}
            placeholder="Priya's house"
            className="mb-3 w-full rounded border border-border bg-bg px-2.5 py-1.5 text-sm outline-none focus:border-accent"
          />
          <label htmlFor="red-spot-radius" className="mb-1 block text-[11px] text-ink-dim">
            Radius: {formatRadius(draft.radius_m)}
          </label>
          <input
            id="red-spot-radius"
            type="range"
            min={MIN_RADIUS_M}
            max={MAX_RADIUS_M}
            step={RADIUS_STEP_M}
            value={draft.radius_m}
            onChange={(e) => onChangeDraft({ radius_m: Number(e.target.value) })}
            className="mb-1 w-full accent-red-zone"
          />
          <div className="mb-3 flex justify-between font-mono text-[10px] text-ink-dim">
            <span>{formatRadius(MIN_RADIUS_M)}</span>
            <span>{formatRadius(MAX_RADIUS_M)}</span>
          </div>
          <p className="mb-3 text-[11px] leading-snug text-ink-dim">
            On the map, drag the red dot to move the spot or the white dot to resize it.
          </p>
          {error && <p className="mb-2 text-[11px] text-danger">{error}</p>}
          <div className="flex gap-2">
            <button
              onClick={onSave}
              disabled={!draft.name.trim() || saving}
              className="flex-1 rounded bg-red-zone py-2 font-mono text-[11px] uppercase tracking-wide text-on-red-zone disabled:opacity-40"
            >
              {saving ? "Saving…" : draft.id ? "Update" : "Save"}
            </button>
            <button
              onClick={onCancel}
              className="flex-1 rounded border border-border py-2 font-mono text-[11px] uppercase tracking-wide text-ink-dim"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={picking ? onCancel : onStartAdding}
          className={`w-full rounded-md border border-dashed py-2.5 text-center font-mono text-[11.5px] transition-colors ${
            picking
              ? "border-accent text-accent"
              : "border-border text-ink-dim hover:border-ink-dim hover:text-ink"
          }`}
        >
          {picking ? "Click the map to place the centre (click here to cancel)" : "+ Add red spot"}
        </button>
      )}
    </div>
  );
}
