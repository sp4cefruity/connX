import type { Config } from "tailwindcss";
import { tailwindColors } from "./lib/palette";

// Colours come from lib/palette.ts (one source of truth), through CSS
// variables that app/layout.tsx defines per theme.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: tailwindColors(),
      fontFamily: {
        display: ["var(--font-display)"],
        body: ["var(--font-body)"],
        mono: ["var(--font-mono)"],
      },
    },
  },
  plugins: [],
};
export default config;
