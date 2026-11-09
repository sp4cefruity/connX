export default function HeroField() {
  return (
    <div className="absolute inset-0 z-0" aria-hidden="true">
      <svg
        viewBox="0 0 800 460"
        preserveAspectRatio="xMidYMid slice"
        className="block h-full w-full"
      >
        <g>
          <line className="grid-line" x1="0" y1="60" x2="800" y2="60" />
          <line className="grid-line" x1="0" y1="140" x2="800" y2="140" />
          <line className="grid-line" x1="0" y1="220" x2="800" y2="220" />
          <line className="grid-line" x1="0" y1="300" x2="800" y2="300" />
          <line className="grid-line" x1="0" y1="380" x2="800" y2="380" />
          <line className="grid-line" x1="100" y1="0" x2="100" y2="460" />
          <line className="grid-line" x1="220" y1="0" x2="220" y2="460" />
          <line className="grid-line" x1="340" y1="0" x2="340" y2="460" />
          <line className="grid-line" x1="460" y1="0" x2="460" y2="460" />
          <line className="grid-line" x1="580" y1="0" x2="580" y2="460" />
          <line className="grid-line" x1="700" y1="0" x2="700" y2="460" />
        </g>

        <ellipse className="overlap-glow" cx="410" cy="205" rx="130" ry="42" />

        <circle className="avoid-ring" cx="655" cy="130" r="26" />
        <circle cx="655" cy="130" r="3" className="fill-overlap" opacity="0.8" />

        <path
          className="path-line path-a draw"
          d="M20,360 C140,340 200,220 300,205 C390,192 450,215 520,175 C610,120 620,150 780,90"
        />
        <path
          className="path-line path-b draw delay"
          d="M20,380 C130,368 200,270 290,235 C370,205 440,215 520,180 C620,140 700,190 780,250"
        />

        <circle className="overlap-dot" cx="335" cy="212" r="4" />
        <circle className="overlap-dot d2" cx="495" cy="182" r="4" />
      </svg>

      <span className="telemetry t1" style={{ top: "16%", left: "6%" }}>
        N 20.2961° · E 85.8245°
      </span>
      <span className="telemetry t2" style={{ top: "46%", right: "8%" }}>
        OVERLAP Δ 2.4KM
      </span>
      <span className="telemetry t3" style={{ bottom: "14%", left: "10%" }}>
        REROUTE ×3 AVAILABLE
      </span>
    </div>
  );
}
