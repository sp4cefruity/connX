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
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

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
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 350);
    return () => clearTimeout(debounceRef.current);
  }, [value]);

  function useMyLocation() {
    if (!navigator.geolocation || !onUseLocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        onUseLocation({ lon: pos.coords.longitude, lat: pos.coords.latitude });
      },
      () => {
        /* permission denied — app continues to function normally, per spec §26 */
      }
    );
  }

  return (
    <div className="relative mb-2.5">
      <label className="mb-1.5 block text-[11px] text-ink-dim">{label}</label>
      <div className="flex items-center gap-2 rounded-md border border-border bg-panel-2 px-3 py-2.5">
        <input
          type="text"
          value={value}
          placeholder={placeholder}
          onChange={(e) => {
            onChange(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          className="w-full bg-transparent font-body text-sm text-ink outline-none placeholder:text-[#565b6e]"
        />
        {loading && <span className="font-mono text-[10px] text-ink-dim">…</span>}
      </div>

      {showUseLocation && (
        <button
          type="button"
          onClick={useMyLocation}
          className="mt-1.5 font-mono text-[10.5px] tracking-wide text-route-a"
        >
          USE MY LOCATION
        </button>
      )}

      {open && results.length > 0 && (
        <ul className="absolute z-20 mt-1 w-full overflow-hidden rounded-md border border-border bg-panel-2 shadow-xl">
          {results.map((r, i) => (
            <li key={i}>
              <button
                type="button"
                onMouseDown={() => {
                  onSelect(r);
                  setOpen(false);
                }}
                className="block w-full px-3 py-2 text-left text-sm text-ink hover:bg-white/5"
              >
                <div>{r.label}</div>
                {r.address && (
                  <div className="truncate text-[11px] text-ink-dim">{r.address}</div>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
