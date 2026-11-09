/**
 * Which theme is active: the user's stored choice, else the system preference
 * (ADR 0004). Pure helpers plus the tiny script layout.tsx inlines so the right
 * theme is on <html> before first paint. Keep runtime imports out of this file.
 */
import { DEFAULT_THEME, THEME_NAMES, type ThemeName } from "./palette";

export const THEME_STORAGE_KEY = "connx-theme";

export function isThemeName(value: unknown): value is ThemeName {
  return typeof value === "string" && (THEME_NAMES as readonly string[]).includes(value);
}

/** The stored choice if valid, otherwise the system preference. */
export function resolveTheme(stored: string | null | undefined, prefersLight: boolean): ThemeName {
  if (isThemeName(stored)) return stored;
  return prefersLight ? "light" : DEFAULT_THEME;
}

export function otherTheme(theme: ThemeName): ThemeName {
  return theme === "light" ? "dark" : "light";
}

/**
 * Inline script for <head>: sets `data-theme` (and the browser's colour-scheme
 * for form controls and scrollbars) before the page paints. It must not throw
 * when storage is blocked. Mirrors resolveTheme; both are tested.
 */
export function themeInitScript(): string {
  const names = JSON.stringify(THEME_NAMES);
  return (
    `(function(){try{var t=null;try{t=localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)})}catch(e){}` +
    `if(${names}.indexOf(t)<0){t=window.matchMedia&&window.matchMedia("(prefers-color-scheme: light)").matches?"light":${JSON.stringify(DEFAULT_THEME)}}` +
    `var d=document.documentElement;d.setAttribute("data-theme",t);d.style.colorScheme=t}catch(e){}})();`
  );
}
