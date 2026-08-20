import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0A0A12",
        panel: "#12131D",
        "panel-2": "#161826",
        border: "rgba(255,255,255,0.08)",
        ink: "#ECEEF5",
        "ink-dim": "#8A90A6",
        "route-a": "#5EE6C4",
        "route-b": "#B98CFF",
        ember: "#FF5A36",
      },
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
