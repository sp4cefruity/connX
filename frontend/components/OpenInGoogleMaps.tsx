"use client";

import { MAX_WAYPOINTS_DESKTOP, MAX_WAYPOINTS_MOBILE, googleMapsUrl, isMobileClient } from "@/lib/googleMapsUrl";
import type { RouteResult } from "@/lib/types";

/** Opens the route in Google Maps in its own tab; the URL is built on click so the device check is current. */
export default function OpenInGoogleMaps({ route, label }: { route: RouteResult; label: string }) {
  const open = () => {
    const url = googleMapsUrl(route, isMobileClient() ? MAX_WAYPOINTS_MOBILE : MAX_WAYPOINTS_DESKTOP);
    if (url) window.open(url, "_blank", "noopener,noreferrer");
  };
  return (
    <button
      type="button"
      onClick={open}
      disabled={route.geometry.length < 2}
      aria-label={`Open ${label} in Google Maps`}
      className="ml-auto shrink-0 rounded-md border border-border px-2 py-0.5 font-mono text-[10.5px] font-normal text-ink-dim hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
    >
      Google Maps ↗
    </button>
  );
}
