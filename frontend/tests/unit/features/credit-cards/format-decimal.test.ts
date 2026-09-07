import { describe, expect, it } from "vitest";
import {
  availableCents,
  creditLimitDecimalToCents,
  formatDecimalCurrency,
} from "@/features/credit-cards/format-decimal";
import { formatCents } from "@/lib/money";

describe("creditLimitDecimalToCents", () => {
  it("converts decimal string with commas to int cents", () => {
    expect(creditLimitDecimalToCents("1,500.00")).toBe(150000);
    expect(creditLimitDecimalToCents("1500.00")).toBe(150000);
  });

  it("rejects more than 2 decimal places", () => {
    expect(creditLimitDecimalToCents("500.123")).toBeNull();
    expect(creditLimitDecimalToCents("10.999")).toBeNull();
  });

  it("strips commas and handles whole numbers", () => {
    expect(creditLimitDecimalToCents("500")).toBe(50000);
    expect(creditLimitDecimalToCents("1,234,567.89")).toBe(123456789);
  });

  it("returns null for non-numeric input", () => {
    expect(creditLimitDecimalToCents("not-a-number")).toBeNull();
    expect(creditLimitDecimalToCents("")).toBeNull();
  });
});

describe("availableCents", () => {
  it("derives available via integer arithmetic", () => {
    expect(availableCents("500.00", 15000)).toBe(35000);
  });

  it("returns null when limit is unparseable", () => {
    expect(availableCents("not-a-number", 15000)).toBeNull();
  });

  it("handles overpayment negative used_credit", () => {
    expect(availableCents("500.00", -10000)).toBe(60000);
  });

  it("null renders as em dash via formatCents guard", () => {
    const avail = availableCents("not-a-number", 15000);
    expect(avail).toBeNull();
    expect(avail === null ? "—" : formatCents(avail)).toBe("—");
  });

  it("guards 100x mismatch: 1500.00 becomes 150000 not 1500", () => {
    expect(creditLimitDecimalToCents("1500.00")).toBe(150000);
    expect(availableCents("1500.00", 0)).toBe(150000);
  });
});

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
