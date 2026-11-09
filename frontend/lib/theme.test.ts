import { describe, expect, it } from "vitest";
import { THEME_NAMES } from "./palette";
import { THEME_STORAGE_KEY, otherTheme, resolveTheme, themeInitScript } from "./theme";

describe("resolveTheme", () => {
  it("prefers a valid stored choice over the system", () => {
    expect(resolveTheme("dark", true)).toBe("dark");
    expect(resolveTheme("light", false)).toBe("light");
  });
  it("follows the system when nothing valid is stored", () => {
    expect(resolveTheme(null, true)).toBe("light");
    expect(resolveTheme(undefined, false)).toBe("dark");
    expect(resolveTheme("sepia", true)).toBe("light");
  });
  it("flips", () => {
    expect(otherTheme("light")).toBe("dark");
    expect(otherTheme("dark")).toBe("light");
  });
});

describe("themeInitScript", () => {
  const run = (stored: string | null, prefersLight: boolean) => {
    const attrs: Record<string, string> = {};
    const style: Record<string, string> = {};
    const g = globalThis as Record<string, unknown>;
    const saved = { localStorage: g.localStorage, document: g.document, window: g.window };
    g.localStorage = { getItem: (k: string) => (k === THEME_STORAGE_KEY ? stored : null) };
    g.document = { documentElement: { setAttribute: (k: string, v: string) => (attrs[k] = v), style } };
    g.window = { matchMedia: () => ({ matches: prefersLight }) };
    try {
      new Function(themeInitScript())();
    } finally {
      Object.assign(g, saved);
    }
    return { theme: attrs["data-theme"], scheme: style.colorScheme };
  };

  it("agrees with resolveTheme", () => {
    for (const stored of [null, "bogus", ...THEME_NAMES]) {
      for (const light of [true, false]) {
        expect(run(stored, light).theme).toBe(resolveTheme(stored, light));
      }
    }
  });
  it("sets colour-scheme to match", () => {
    expect(run("light", false).scheme).toBe("light");
  });
  it("does not throw when storage is blocked", () => {
    const g = globalThis as Record<string, unknown>;
    const saved = { localStorage: g.localStorage, document: g.document, window: g.window };
    g.localStorage = { getItem: () => { throw new Error("blocked"); } };
    const attrs: Record<string, string> = {};
    g.document = { documentElement: { setAttribute: (k: string, v: string) => (attrs[k] = v), style: {} } };
    g.window = { matchMedia: () => ({ matches: true }) };
    try {
      expect(() => new Function(themeInitScript())()).not.toThrow();
    } finally {
      Object.assign(g, saved);
    }
    expect(attrs["data-theme"]).toBe("light");
  });
});
