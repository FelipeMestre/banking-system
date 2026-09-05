import { describe, expect, it } from "vitest";
import { formatDecimalCurrency } from "@/features/credit-cards/format-decimal";

describe("formatDecimalCurrency", () => {
  it("formats a decimal string with the given symbol", () => {
    expect(formatDecimalCurrency("120.00", "$")).toBe("$120.00");
  });

  it("defaults to $ when no symbol is given", () => {
    expect(formatDecimalCurrency("1500")).toBe("$1500.00");
  });

  it("returns an em dash for a non-numeric value", () => {
    expect(formatDecimalCurrency("not-a-number")).toBe("—");
  });
});
