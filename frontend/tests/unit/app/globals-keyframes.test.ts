import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

function readGlobalsCss(): string {
  return fs.readFileSync(path.join(__dirname, "../../../app/globals.css"), "utf8");
}

describe("globals.css keyframes", () => {
  it("contains @keyframes ob-spin with 360deg rotation", () => {
    const css = readGlobalsCss();
    expect(css).toContain("@keyframes ob-spin");
    expect(css).toContain("rotate(360deg)");
  });

  it("contains @keyframes ob-sweep with translate", () => {
    const css = readGlobalsCss();
    expect(css).toContain("@keyframes ob-sweep");
    expect(css).toContain("translateX");
  });

  it("contains @keyframes ob-fade-in with opacity", () => {
    const css = readGlobalsCss();
    expect(css).toContain("@keyframes ob-fade-in");
    expect(css).toContain("opacity");
  });

  it("contains prefers-reduced-motion guard for loading-screen", () => {
    const css = readGlobalsCss();
    expect(css).toContain("prefers-reduced-motion");
    expect(css).toContain('[data-slot="loading-screen"]');
  });

  it("reduced-motion guard disables animations with 0.01ms", () => {
    const css = readGlobalsCss();
    expect(css).toContain("0.01ms");
    expect(css).toContain("animation-duration");
  });

});
