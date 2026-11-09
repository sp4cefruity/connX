import Link from "next/link";
import ConnXLogo from "@/components/ConnXLogo";
import HeroField from "@/components/HeroField";

const SEQUENCE = [
  { num: "01 · ENTER", label: "Where you're going", color: "text-route-a" },
  { num: "02 · COMPARE", label: "A route to steer clear of", color: "text-route-b" },
  { num: "03 · OVERLAP", label: "See where paths cross", color: "text-overlap" },
  { num: "04 · AVOID", label: "Route around it", color: "text-route-b" },
  { num: "05 · GO", label: "One tap, new path", color: "text-route-a" },
];

const STRIP = [
  {
    swatch: "bg-route-a shadow-[0_0_8px_rgb(var(--c-route-a))]",
    title: "Your route",
    body: "Wherever you're headed — traced end to end, distance and time attached, no jargon in between.",
  },
  {
    swatch: "bg-route-b shadow-[0_0_8px_rgb(var(--c-route-b))]",
    title: "The route to avoid",
    body: "Any second route you want kept at a distance. It doesn't need to belong to anyone in particular.",
  },
  {
    swatch: "bg-overlap shadow-[0_0_8px_rgb(var(--c-overlap))]",
    title: "Where they meet",
    body: "Shared roads and marked zones are measured, not just drawn — then ranked alternatives route around them.",
  },
];

export default function LandingPage() {
  return (
    <>
      <header className="fixed inset-x-0 top-0 z-50 mix-blend-difference flex items-center justify-between px-5 py-6 sm:px-10">
        <ConnXLogo size={24} />
        <Link
          href="/planner"
          className="rounded-full border border-white/35 px-4 py-2 font-mono text-xs uppercase tracking-widest"
        >
          Plan a route
        </Link>
      </header>

      <section className="relative min-h-screen overflow-hidden px-5 pb-16 pt-32 sm:px-10 lg:px-16">
        <HeroField />

        <div className="relative z-10 max-w-3xl">
          <div className="mb-7 flex items-center gap-2.5 font-mono text-xs uppercase tracking-[0.22em] text-route-a">
            <span className="inline-block h-px w-5.5 bg-route-a" />
            Route intelligence
          </div>

          <h1 className="max-w-[14ch] font-display text-[42px] font-semibold leading-[0.98] tracking-tight sm:text-[64px] lg:text-[88px]">
            Take the route that&apos;s <em className="not-italic text-route-a">yours</em>.
          </h1>

          <p className="mt-6 max-w-[46ch] font-display text-base italic leading-relaxed text-ink-dim sm:text-lg">
            To connect hearts, hearts so much bigger than maps.
          </p>

          <div className="mt-11 flex flex-wrap items-center gap-6">
            <Link
              href="/planner"
              className="group inline-flex items-center gap-2.5 rounded-sm bg-ink px-7 py-4 font-mono text-[13px] uppercase tracking-wider text-bg transition-all duration-300 hover:translate-x-1 hover:bg-route-a"
            >
              Plan a route
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} className="h-3.5 w-3.5">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </Link>
            <span className="font-mono text-xs text-ink-dim before:mr-1 before:content-['—'] before:text-route-b">
              Comparisons run on this device by default
            </span>
          </div>

          <div className="mt-20 grid grid-cols-2 gap-5 border-t border-border pt-6 sm:grid-cols-5">
            {SEQUENCE.map((s) => (
              <div key={s.num} className="font-mono">
                <div className={`text-xs tracking-wide ${s.color}`}>{s.num}</div>
                <div className="mt-2 font-body text-sm font-medium text-ink">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-14 border-t border-border px-5 py-24 sm:px-10 lg:grid-cols-2 lg:px-16 lg:py-28">
        <h2 className="max-w-[14ch] font-display text-3xl font-semibold leading-tight sm:text-[34px]">
          Two lines on a map rarely explain themselves.
        </h2>
        <div className="flex flex-col gap-7">
          {STRIP.map((row, i) => (
            <div
              key={row.title}
              className={`flex gap-4 pb-6 ${i < STRIP.length - 1 ? "border-b border-border" : ""}`}
            >
              <span className={`mt-1.5 h-2.5 w-2.5 flex-shrink-0 rounded-full ${row.swatch}`} />
              <div>
                <h3 className="mb-1.5 font-body text-base font-semibold">{row.title}</h3>
                <p className="max-w-[44ch] text-sm leading-relaxed text-ink-dim">{row.body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <footer className="flex flex-wrap items-center justify-between gap-3.5 border-t border-border px-5 py-10 sm:px-10 lg:px-16">
        <ConnXLogo size={18} />
        <p className="font-mono text-[11.5px] tracking-wide text-ink-dim">
          NO ACCOUNT REQUIRED · RED SPOTS NEVER LEAVE YOUR DEVICE
        </p>
      </footer>
    </>
  );
}
