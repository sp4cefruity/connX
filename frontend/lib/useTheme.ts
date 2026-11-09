"use client";

import { useCallback, useEffect, useState } from "react";
import { DEFAULT_THEME, type ThemeName } from "./palette";
import { THEME_STORAGE_KEY, isThemeName, otherTheme, resolveTheme } from "./theme";

/** The theme the inline script in layout.tsx already put on <html>. */
function currentTheme(): ThemeName {
  if (typeof document === "undefined") return DEFAULT_THEME;
  const attr = document.documentElement.getAttribute("data-theme");
  return isThemeName(attr) ? attr : DEFAULT_THEME;
}

/**
 * The active theme and a way to flip it. The choice is written to localStorage
 * and to <html data-theme>; until the user chooses, the system preference is
 * followed live.
 */
export function useTheme(): { theme: ThemeName; toggle: () => void } {
  const [theme, setTheme] = useState<ThemeName>(DEFAULT_THEME);

  const apply = useCallback((next: ThemeName) => {
    document.documentElement.setAttribute("data-theme", next);
    document.documentElement.style.colorScheme = next;
    setTheme(next);
  }, []);

  // Read after mount (not in the initial state) so server and client markup agree.
  useEffect(() => {
    setTheme(currentTheme());
    const query = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = () => {
      let stored: string | null = null;
      try {
        stored = localStorage.getItem(THEME_STORAGE_KEY);
      } catch {
        /* storage blocked: follow the system */
      }
      if (!isThemeName(stored)) apply(resolveTheme(null, query.matches));
    };
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, [apply]);

  const toggle = useCallback(() => {
    const next = otherTheme(currentTheme());
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      /* storage blocked: the choice lasts for this page view only */
    }
    apply(next);
  }, [apply]);

  return { theme, toggle };
}
