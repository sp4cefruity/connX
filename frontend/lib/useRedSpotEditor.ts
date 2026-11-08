"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, createRedSpot, deleteRedSpot, listRedSpots, updateRedSpot } from "./api";
import { DEFAULT_RADIUS_M, clampRadius } from "./redSpots";
import type { LonLat, RedSpot } from "./types";

/** The red spot being drawn (`id === null`) or edited. Not saved until `save()`. */
export interface RedSpotDraft {
  id: string | null;
  name: string;
  lon: number;
  lat: number;
  radius_m: number;
}

export type DraftPatch = Partial<Pick<RedSpotDraft, "name" | "lon" | "lat" | "radius_m">>;

/** Red spot state + actions: list, draw (click to place), rename / move / resize, delete. */
export function useRedSpotEditor() {
  const [redSpots, setRedSpots] = useState<RedSpot[]>([]);
  const [picking, setPicking] = useState(false);
  const [draft, setDraft] = useState<RedSpotDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Bumped to ask the map to pan to a spot picked from the list.
  const [focus, setFocus] = useState<{ lon: number; lat: number; key: number } | null>(null);

  useEffect(() => {
    listRedSpots()
      .then(setRedSpots)
      .catch(() => {
        /* red spots are optional to load — app still functions (spec §36) */
      });
  }, []);

  const startAdding = useCallback(() => {
    setDraft(null);
    setError(null);
    setPicking(true);
  }, []);

  const placeAt = useCallback((point: LonLat) => {
    setDraft({ id: null, name: "", lon: point.lon, lat: point.lat, radius_m: DEFAULT_RADIUS_M });
    setPicking(false);
    setError(null);
  }, []);

  const edit = useCallback(
    (id: string) => {
      const spot = redSpots.find((s) => s.id === id);
      if (!spot) return;
      setDraft({ id, name: spot.name, lon: spot.longitude, lat: spot.latitude, radius_m: spot.radius_m });
      setPicking(false);
      setError(null);
    },
    [redSpots]
  );

  /** Pick a spot from the list: edit it and pan the map to it. */
  const editAndFocus = useCallback(
    (id: string) => {
      const spot = redSpots.find((s) => s.id === id);
      if (!spot) return;
      edit(id);
      setFocus({ lon: spot.longitude, lat: spot.latitude, key: Date.now() });
    },
    [edit, redSpots]
  );

  const patchDraft = useCallback((patch: DraftPatch) => {
    setDraft((d) => {
      if (!d) return d;
      const next = { ...d, ...patch };
      if (patch.radius_m !== undefined) next.radius_m = clampRadius(patch.radius_m);
      return next;
    });
  }, []);

  const cancel = useCallback(() => {
    setDraft(null);
    setPicking(false);
    setError(null);
  }, []);

  const save = useCallback(async () => {
    if (!draft || !draft.name.trim()) return;
    const body = {
      name: draft.name.trim(),
      latitude: draft.lat,
      longitude: draft.lon,
      radius_m: clampRadius(draft.radius_m),
    };
    setSaving(true);
    setError(null);
    try {
      if (draft.id === null) {
        const created = await createRedSpot(body);
        setRedSpots((prev) => [...prev, created]);
      } else {
        const updated = await updateRedSpot(draft.id, body);
        setRedSpots((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      }
      setDraft(null);
    } catch (err) {
      // Keep the draft open so nothing the user drew is lost.
      setError(
        err instanceof ApiError && typeof err.message === "string" && err.status !== 422
          ? err.message
          : "Couldn't save this red spot. Check the name and radius and try again."
      );
    } finally {
      setSaving(false);
    }
  }, [draft]);

  const remove = useCallback(
    async (id: string) => {
      setRedSpots((prev) => prev.filter((s) => s.id !== id));
      setDraft((d) => (d?.id === id ? null : d));
      try {
        await deleteRedSpot(id);
      } catch {
        // reload from server on failure to stay in sync
        listRedSpots().then(setRedSpots).catch(() => {});
      }
    },
    []
  );

  /** Map click: places the centre while picking. */
  const handleMapClick = useCallback(
    (point: LonLat) => {
      if (picking) placeAt(point);
    },
    [picking, placeAt]
  );

  return {
    redSpots,
    picking,
    draft,
    saving,
    error,
    focus,
    startAdding,
    handleMapClick,
    edit,
    editAndFocus,
    patchDraft,
    cancel,
    save,
    remove,
  };
}
