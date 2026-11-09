import type { ThemeName } from "@/lib/palette";

/** Pill button that flips between the light and dark theme. */
export default function ThemeToggle({ theme, onToggle }: { theme: ThemeName; onToggle: () => void }) {
  const next = theme === "light" ? "dark" : "light";
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      className="pointer-events-auto flex shrink-0 items-center gap-1.5 rounded-full border border-border bg-panel/70 px-2.5 py-1.5 font-mono text-[11px] text-ink-dim backdrop-blur-md transition-colors hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
    >
      <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        {theme === "light" ? (
          <path d="M13.5 9.6A5.7 5.7 0 0 1 6.4 2.5a5.7 5.7 0 1 0 7.1 7.1Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        ) : (
          <g stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <circle cx="8" cy="8" r="2.8" />
            <path d="M8 1.5v1.6M8 12.9v1.6M1.5 8h1.6M12.9 8h1.6M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M3.4 12.6l1.1-1.1M11.5 4.5l1.1-1.1" />
          </g>
        )}
      </svg>
      {theme === "light" ? "Dark" : "Light"}
    </button>
  );
}
