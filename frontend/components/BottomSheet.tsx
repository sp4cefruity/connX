"use client";

import { useId, useRef } from "react";

interface BottomSheetProps {
  /** Small screens only: show the content, or just the handle bar. Ignored on desktop. */
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
  /** One line shown in the handle bar on small screens. */
  summary: React.ReactNode;
  children: React.ReactNode;
}

// A vertical drag on the handle bar longer than this opens or closes the sheet.
const SWIPE_PX = 24;

/**
 * The planner panel. From the `md` breakpoint (768 px, see lib/layout.ts) it
 * is the side panel, full height in the first grid column. Below it, it is a
 * bottom sheet under the map: collapsed it is only a handle bar, expanded it
 * takes 60% of the screen and its content scrolls. The map sits above it, not
 * under it, so the map and its controls stay fully usable in both states.
 */
export default function BottomSheet({ expanded, onExpandedChange, summary, children }: BottomSheetProps) {
  const contentId = useId();
  const startY = useRef<number | null>(null);
  // A swipe already toggled the sheet; ignore the click that follows it.
  const swiped = useRef(false);

  return (
    <aside
      className={`relative z-20 order-last -mt-2 flex shrink-0 flex-col rounded-t-2xl border-t border-border bg-panel shadow-[0_-8px_24px_rgba(0,0,0,0.35)] ${
        expanded ? "h-[60vh] supports-[height:100dvh]:h-[60dvh]" : "h-14"
      } md:order-none md:mt-0 md:h-auto md:min-h-0 md:rounded-none md:border-r md:border-t-0 md:shadow-none`}
    >
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls={contentId}
        aria-label={expanded ? "Collapse planner panel" : "Expand planner panel"}
        onPointerDown={(e) => {
          swiped.current = false;
          startY.current = e.clientY;
          e.currentTarget.setPointerCapture(e.pointerId);
        }}
        onPointerUp={(e) => {
          if (startY.current === null) return;
          const dy = e.clientY - startY.current;
          startY.current = null;
          if (Math.abs(dy) < SWIPE_PX) return; // a tap: the click handler toggles
          swiped.current = true;
          onExpandedChange(dy < 0);
        }}
        onPointerCancel={() => {
          startY.current = null;
        }}
        onClick={() => {
          if (swiped.current) {
            swiped.current = false;
            return;
          }
          onExpandedChange(!expanded);
        }}
        className="flex h-14 w-full shrink-0 touch-none select-none flex-col items-center justify-center gap-1.5 px-5 md:hidden"
      >
        <span aria-hidden className="h-1 w-10 rounded-full bg-ink-dim/40" />
        <span className="flex w-full min-w-0 items-center justify-between gap-3">
          <span className="truncate font-mono text-[11px] text-ink-dim">{summary}</span>
          <span aria-hidden className="shrink-0 font-mono text-[11px] uppercase tracking-wider text-ink">
            {expanded ? "Hide" : "Show"}
          </span>
        </span>
      </button>

      <div
        id={contentId}
        className={`${expanded ? "block" : "hidden"} min-h-0 flex-1 overflow-y-auto overscroll-contain md:block`}
      >
        {children}
      </div>
    </aside>
  );
}
