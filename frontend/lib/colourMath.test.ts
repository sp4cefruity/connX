import { describe, expect, it } from "vitest";
import { blend, chroma, contrast, deltaE, isHex, rgbChannels } from "./colourMath";

describe("contrast (WCAG 2 ratio)", () => {
  it("is 21 for black on white and 1 for a colour on itself", () => {
    expect(contrast("#000000", "#FFFFFF")).toBeCloseTo(21, 5);
    expect(contrast("#5EE6C4", "#5EE6C4")).toBeCloseTo(1, 5);
  });

  it("does not depend on argument order", () => {
    expect(contrast("#0A0A12", "#5EE6C4")).toBeCloseTo(contrast("#5EE6C4", "#0A0A12"), 10);
  });
});

describe("deltaE (OKLab x100)", () => {
  it("is 0 for identical colours and 100 for black vs white", () => {
    expect(deltaE("#F5C24B", "#F5C24B")).toBe(0);
    expect(deltaE("#000000", "#FFFFFF")).toBeCloseTo(100, 1);
  });

  // Reference values from the dataviz skill's validate_palette.js, so this
  // port stays in step with the method's calibrated thresholds.
  it("matches the reference validator under normal vision", () => {
    expect(deltaE("#F5C24B", "#FF5A36")).toBeCloseTo(22.4, 1);
    expect(deltaE("#F5C24B", "#5EE6C4")).toBeCloseTo(19.1, 1);
  });

  it("matches the reference validator under Machado 2009 simulation", () => {
    expect(deltaE("#F5C24B", "#FF5A36", "deutan")).toBeCloseTo(14.9, 1);
    expect(deltaE("#F5C24B", "#5EE6C4", "protan")).toBeCloseTo(14.0, 1);
  });

  it("collapses red and green under deuteranopia", () => {
    expect(deltaE("#D03030", "#30A030", "deutan")).toBeLessThan(deltaE("#D03030", "#30A030") / 2);
  });
});

describe("chroma (OKLCH C)", () => {
  it("is ~0 for greys and high for saturated colours", () => {
    expect(chroma("#8A8A8A")).toBeLessThan(0.001);
    expect(chroma("#FF0000")).toBeGreaterThan(0.2);
  });
});

describe("blend", () => {
  it("composites a colour at an opacity over a background, in sRGB like the browser", () => {
    expect(blend("#FF0000", 0.5, "#000000")).toBe("#800000");
    expect(blend("#123456", 1, "#FFFFFF")).toBe("#123456");
    expect(blend("#123456", 0, "#FFFFFF")).toBe("#FFFFFF");
  });
});

describe("hex helpers", () => {
  it("accepts only #RRGGBB", () => {
    expect(isHex("#5EE6C4")).toBe(true);
    expect(isHex("#5ee6c4")).toBe(true);
    expect(isHex("#5EE")).toBe(false);
    expect(isHex("rgba(0,0,0,0.1)")).toBe(false);
  });

  it("rgbChannels gives the space-separated channels a CSS rgb() variable needs", () => {
    expect(rgbChannels("#5EE6C4")).toBe("94 230 196");
  });
});
