"use client";

import { useEffect, useRef, useState } from "react";
import { geocode } from "@/lib/api";
import type { GeocodeResult, LonLat } from "@/lib/types";

interface LocationFieldProps {
  label: string;
  placeholder?: string;
  value: string;
  onChange: (label: string) => void;
  onSelect: (result: GeocodeResult) => void;
  showUseLocation?: boolean;
  onUseLocation?: (loc: LonLat) => void;
}

export default function LocationField({
  label,
  placeholder,
  value,
  onChange,
  onSelect,
  showUseLocation,
  onUseLocation,
}: LocationFieldProps) {
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [geoLoading, setGeoLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!value.trim()) {
      setResults([]);
      return;
    }
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const r = await geocode(value);
        setResults(r);
        if (r.length > 0) setOpen(true);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [value]);

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
            `https://nominatim.openstreetmap.org/reverse?lat=${loc.lat}&lon=${loc.lon}&format=jsonv2`,
            { headers: { "User-Agent": "ConnX/0.1" } }
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

  return (
    <div className="relative mb-2.5">
      <label className="mb-1.5 block text-[11px] text-ink-dim">{label}</label>
      <div className="flex items-center gap-2 rounded-md border border-border bg-panel-2 px-3 py-2.5 focus-within:border-route-a/40 transition-colors">
        <input
          ref={inputRef}
          type="text"
          value={value}
          placeholder={placeholder}
          onChange={(e) => {
            onChange(e.target.value);
            setOpen(true);
          }}
          onFocus={() => {
            if (results.length > 0) setOpen(true);
          }}
          onBlur={() => setTimeout(() => setOpen(false), 200)}
          className="w-full bg-transparent font-body text-sm text-ink outline-none placeholder:text-[#565b6e]"
        />
        {loading && (
          <svg className="h-3.5 w-3.5 animate-spin text-ink-dim" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" opacity="0.3" />
            <path d="M8 2a6 6 0 0 1 6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        )}
      </div>

      {showUseLocation && (
        <button
          type="button"
          onClick={useMyLocation}
          disabled={geoLoading}
          className="mt-1.5 flex items-center gap-1.5 font-mono text-[10.5px] tracking-wide text-route-a hover:text-route-a/80 transition-colors disabled:opacity-50"
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

      {open && results.length > 0 && (
        <ul className="absolute z-30 mt-1 w-full overflow-hidden rounded-md border border-border bg-panel-2 shadow-2xl max-h-52 overflow-y-auto">
          {results.map((r, i) => (
            <li key={i}>
              <button
                type="button"
                onMouseDown={() => {
                  onSelect(r);
                  setOpen(false);
                  setResults([]);
                }}
                className="flex w-full items-start gap-2 px-3 py-2.5 text-left text-sm text-ink hover:bg-white/5 transition-colors"
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
        </ul>
      )}
    </div>
  );
}
