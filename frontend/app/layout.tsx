import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Space_Grotesk } from "next/font/google";
import "./globals.css";
import { themeCss } from "@/lib/palette";
import { themeInitScript } from "@/lib/theme";

const display = Space_Grotesk({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-display",
});

const body = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-body",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "ConnX - connecting hearts",
  description:
    "Compare routes, spot overlaps, and avoid places you don't want to pass through.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <head>
        {/* Colour tokens for every theme (lib/palette.ts). */}
        <style dangerouslySetInnerHTML={{ __html: themeCss() }} />
        {/* Sets data-theme from localStorage / the system before first paint (lib/theme.ts). */}
        <script dangerouslySetInnerHTML={{ __html: themeInitScript() }} />
      </head>
      <body className="font-body">{children}</body>
    </html>
  );
}
