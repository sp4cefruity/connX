interface ConnXLogoProps {
  className?: string;
  size?: number;
}

export default function ConnXLogo({ className = "", size = 32 }: ConnXLogoProps) {
  return (
    <svg
      viewBox="0 0 120 40"
      width={size * 3}
      height={size}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="ConnX"
    >
      {/* Two crossing route paths forming the X */}
      <path
        d="M6 12 L16 28"
        stroke="#5EE6C4"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
      <path
        d="M6 28 L16 12"
        stroke="#B98CFF"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
      {/* Small glow dot at intersection */}
      <circle cx="11" cy="20" r="2" fill="#5EE6C4" opacity="0.5" />

      {/* "conn" text */}
      <text
        x="24"
        y="25.5"
        fontFamily="var(--font-display), 'Space Grotesk', sans-serif"
        fontWeight="700"
        fontSize="18"
        fill="#ECEEF5"
        letterSpacing="-0.5"
      >
        conn
      </text>

      {/* "X" in accent teal */}
      <text
        x="77"
        y="25.5"
        fontFamily="var(--font-display), 'Space Grotesk', sans-serif"
        fontWeight="700"
        fontSize="18"
        fill="#5EE6C4"
        letterSpacing="-0.5"
      >
        X
      </text>
    </svg>
  );
}
