import { describe, expect, it } from "vitest";
import { parseAmountToCents } from "@/lib/money";

describe("parseAmountToCents", () => {
  it("parses 1,250.00 to 125000", () => {
    expect(parseAmountToCents("1,250.00")).toBe(125000);
  });

  it("parses 0.10 to 10", () => {
    expect(parseAmountToCents("0.10")).toBe(10);
  });

  it("returns null for invalid inputs", () => {
    for (const bad of ["", "0", "0.00", "abc", "1.234", "-5", "  ", "1.2.3"]) {
      expect(parseAmountToCents(bad)).toBeNull();
    }
  });

  it("handles integer without decimal", () => {
    expect(parseAmountToCents("42")).toBe(4200);
  });

  it("handles commas and trims", () => {
    expect(parseAmountToCents(" 1,000 ")).toBe(100000);
  });

  it("rejects unsafe integer overflow", () => {
    expect(parseAmountToCents("90071992547409.92")).toBeNull();
    expect(parseAmountToCents("999999999999999999.99")).toBeNull();
  });
});
