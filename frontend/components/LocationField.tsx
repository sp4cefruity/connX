"use client";

import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { geocode, isSearchSlowError } from "@/lib/api";
import { dropdownPlacement, type DropdownPlacement } from "@/lib/layout";
import type { GeocodeResult, LonLat } from "@/lib/types";

// Type-ahead debounce. Photon is fast enough that a short wait feels instant.
const DEBOUNCE_MS = 150;
// Give up on a search after this long and show the quiet "slow" state.
const SLOW_AFTER_MS = 8000;

interface LocationFieldProps {
  label: string;
  /** Current map centre; sent to the backend to bias results toward the viewport. */
  bias?: LonLat | null;
  placeholder?: string;
  value: string;
  onChange: (label: string) => void;
  onSelect: (result: GeocodeResult) => void;
  showUseLocation?: boolean;
  onUseLocation?: (loc: LonLat) => void;
}

export default function LocationField({
  label,
  bias,
  placeholder,
  value,
  onChange,
  onSelect,
  showUseLocation,
  onUseLocation,
}: LocationFieldProps) {
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const [loading, setLoading] = useState(false);
  const [slow, setSlow] = useState(false);
  const [geoLoading, setGeoLoading] = useState(false);
  const [rect, setRect] = useState<DropdownPlacement | null>(null);
  const [mounted, setMounted] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const abortRef = useRef<AbortController | null>(null);
  const fieldRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  // Label written into the input by the last selection. While value matches
  // it, the search effect must stay quiet — otherwise picking a suggestion
  // re-triggers the query and pops the dropdown right back open (the
  // "have to click twice" bug).
  const lastPickedRef = useRef<string | null>(null);
  // The bias is read at request time; changing it must not re-run the search.
  const biasRef = useRef<LonLat | null | undefined>(bias);
  biasRef.current = bias;
  const listId = useId();

  // Portals can only render on the client, once we have a document.
  useEffect(() => setMounted(true), []);
  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    const q = value.trim();
    if (lastPickedRef.current !== null && q === lastPickedRef.current.trim()) return;
    lastPickedRef.current = null;

    if (q.length < 2) {
      clearTimeout(debounceRef.current);
      abortRef.current?.abort();
      setResults([]);
      setOpen(false);
      setActiveIdx(-1);
      setSlow(false);
      setLoading(false);
      return;
    }

    clearTimeout(debounceRef.current);
    abortRef.current?.abort(); // stale request: the user kept typing
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      let timedOut = false;
      const slowTimer = setTimeout(() => {
        timedOut = true;
        ctrl.abort();
      }, SLOW_AFTER_MS);
      try {
        const r = await geocode(value, { signal: ctrl.signal, bias: biasRef.current });
        if (ctrl.signal.aborted) return;
        setSlow(false);
        setResults(r);
        setActiveIdx(-1);
        setOpen(r.length > 0);
      } catch (err) {
        if (timedOut || (!ctrl.signal.aborted && isSearchSlowError(err))) {
          // Quiet state, not an error: keep whatever the user was looking at.
          setSlow(true);
        } else if (!ctrl.signal.aborted) {
          setResults([]);
        }
      } finally {
        clearTimeout(slowTimer);
        if (!ctrl.signal.aborted || timedOut) setLoading(false);
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(debounceRef.current);
  }, [value]);

  function pick(r: GeocodeResult) {
    clearTimeout(debounceRef.current);
    abortRef.current?.abort(); // an in-flight response must not reopen the list
    lastPickedRef.current = r.label;
    onSelect(r);
    setLoading(false);
    setSlow(false);
    setOpen(false);
    setResults([]);
    setActiveIdx(-1);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || results.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && activeIdx >= 0) {
      e.preventDefault();
      pick(results[activeIdx]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      setActiveIdx(-1);
    }
  }

  // Close on clicks/taps anywhere outside the field AND its portaled dropdown.
  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      const t = e.target as Node | null;
      if (fieldRef.current?.contains(t)) return;
      if (listRef.current?.contains(t)) return;
      setOpen(false);
      setActiveIdx(-1);
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  // Keep the highlighted option visible while arrowing through long lists.
  useEffect(() => {
    if (activeIdx < 0 || !listRef.current) return;
    listRef.current
      .querySelector(`[data-idx="${activeIdx}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [activeIdx]);

  // Recompute the dropdown's screen position every time it opens, and keep
  // it pinned to the input while the sidebar scrolls or the window resizes.
  // Using position: fixed + viewport coordinates (rather than an absolutely
  // positioned child of the field) means the list is painted in a portal at
  // <body> level, so no ancestor's `overflow` or stacking context can ever
  // clip it — this is what was silently swallowing the suggestions before.
  // It opens above the input when there is more room there (an input low in
  // the phone bottom sheet, or above the on-screen keyboard).
  const updateRect = useCallback(() => {
    const el = boxRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const vv = window.visualViewport;
    const view = vv
      ? { top: vv.offsetTop, bottom: vv.offsetTop + vv.height }
      : { top: 0, bottom: window.innerHeight };
    setRect(dropdownPlacement(r, view));
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    updateRect();
    const vv = window.visualViewport;
    window.addEventListener("scroll", updateRect, true);
    window.addEventListener("resize", updateRect);
    vv?.addEventListener("resize", updateRect);
    vv?.addEventListener("scroll", updateRect);
    return () => {
      window.removeEventListener("scroll", updateRect, true);
      window.removeEventListener("resize", updateRect);
      vv?.removeEventListener("resize", updateRect);
      vv?.removeEventListener("scroll", updateRect);
    };
  }, [open, updateRect]);

  function useMyLocation() {
    if (!navigator.geolocation || !onUseLocation) return;
    setGeoLoading(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const loc: LonLat = {
          lon: pos.coords.longitude,
          lat: pos.coords.latitude,
        };
        // Reverse geocode to get a human-readable label
        try {
          const resp = await fetch(
            `https://nominatim.openstreetmap.org/reverse?lat=${loc.lat}&lon=${loc.lon}&format=jsonv2`
          );
          const data = await resp.json();
          const label =
            data.name ||
            data.display_name?.split(",").slice(0, 2).join(",") ||
            "Current location";
          onChange(label);
        } catch {
          onChange("Current location");
        }
        onUseLocation(loc);
        setGeoLoading(false);
      },
      () => {
        setGeoLoading(false);
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 60000 }
    );
  }

  const showDropdown = open && results.length > 0;

  return (
    <div className="relative mb-2.5" ref={fieldRef}>
      <label className="mb-1.5 block text-[11px] text-ink-dim">{label}</label>
      <div ref={boxRef} className="flex items-center gap-2 rounded-md border border-border bg-panel-2 px-3 py-2.5 focus-within:border-accent/40 transition-colors">
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-expanded={showDropdown}
          aria-controls={listId}
          aria-activedescendant={activeIdx >= 0 ? `${listId}-opt-${activeIdx}` : undefined}
          aria-autocomplete="list"
          value={value}
          placeholder={placeholder}
          onChange={(e) => {
            onChange(e.target.value);
            setOpen(true);
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (results.length > 0) setOpen(true);
          }}
          className="w-full bg-transparent font-body text-sm text-ink outline-none placeholder:text-ink-faint"
        />
        {loading && (
          <svg className="h-3.5 w-3.5 animate-spin text-ink-dim" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" opacity="0.3" />
            <path d="M8 2a6 6 0 0 1 6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        )}
      </div>

      {slow && !loading && (
        <p role="status" className="mt-1.5 font-mono text-[10.5px] text-ink-dim">
          Search is slow right now. Keep typing or try again in a moment.
        </p>
      )}

      {showUseLocation && (
        <button
          type="button"
          onClick={useMyLocation}
          disabled={geoLoading}
          className="mt-1.5 flex items-center gap-1.5 font-mono text-[10.5px] tracking-wide text-accent hover:text-accent/80 transition-colors disabled:opacity-50"
        >
          {geoLoading ? (
            <>
              <svg className="h-3 w-3 animate-spin" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" opacity="0.3" />
                <path d="M8 2a6 6 0 0 1 6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              Locating...
            </>
          ) : (
            <>
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3" className="h-3 w-3">
                <circle cx="8" cy="8" r="3" />
                <path d="M8 1v3M8 12v3M1 8h3M12 8h3" strokeLinecap="round" />
              </svg>
              USE MY LOCATION
            </>
          )}
        </button>
      )}

      {mounted &&
        showDropdown &&
        rect &&
        createPortal(
          <ul
            ref={listRef}
            id={listId}
            role="listbox"
            style={{
              position: "fixed",
              top: rect.y,
              left: rect.left,
              width: rect.width,
              maxHeight: rect.maxHeight,
              transform: rect.side === "above" ? "translateY(-100%)" : undefined,
            }}
            className="z-[999] overflow-y-auto rounded-md border border-border bg-panel-2 shadow-2xl"
          >
            {results.map((r, i) => (
              <li key={`${r.label}-${r.lon}-${r.lat}`} role="option" aria-selected={i === activeIdx} id={`${listId}-opt-${i}`} data-idx={i}>
                <button
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault(); // keep focus in the input
                    pick(r);
                  }}
                  onMouseEnter={() => setActiveIdx(i)}
                  className={`flex w-full items-start gap-2 px-3 py-2.5 text-left text-sm transition-colors ${
                    i === activeIdx ? "bg-white/10 text-ink" : "text-ink"
                  }`}
                >
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2" className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-ink-dim">
                    <path d="M8 1.5C5.24 1.5 3 3.74 3 6.5 3 10.25 8 14.5 8 14.5s5-4.25 5-8c0-2.76-2.24-5-5-5z" />
                    <circle cx="8" cy="6.5" r="1.5" />
                  </svg>
                  <div className="min-w-0">
                    <div className="truncate font-medium">{r.label}</div>
                    {r.address && (
                      <div className="truncate text-[11px] text-ink-dim">{r.address}</div>
                    )}
                  </div>
                </button>
              </li>
            ))}
          </ul>,
          document.body
        )}
    </div>
  );
}
