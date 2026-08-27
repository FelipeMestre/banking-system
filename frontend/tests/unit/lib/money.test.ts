import { describe, expect, it } from "vitest";
import { formatCents, maskAccountNumber, parseCentsInput } from "../../../lib/money";

describe("formatCents", () => {
  it("formats the spec's worked example", () => {
    expect(formatCents(1100)).toBe("$11.00");
    expect(formatCents(25)).toBe("$0.25");
  });

  it("keeps the cents exact where a float divide would not", () => {
    // 1_00 through 9_99 round-trip losslessly only with integer arithmetic.
    expect(formatCents(2337)).toBe("$23.37");
    expect(formatCents(9999999)).toBe("$99,999.99");
  });

  it("pads a single-digit cents value", () => {
    expect(formatCents(105)).toBe("$1.05");
    expect(formatCents(5)).toBe("$0.05");
  });

  it("handles zero and negatives", () => {
    expect(formatCents(0)).toBe("$0.00");
    expect(formatCents(-1125)).toBe("-$11.25");
  });

  it("accepts a currency symbol for multi-currency accounts", () => {
    expect(formatCents(1897420, "€")).toBe("€18,974.20");
    expect(formatCents(2144099, "£")).toBe("£21,440.99");
  });
});

describe("parseCentsInput", () => {
  it("accepts whole positive cents", () => {
    expect(parseCentsInput("1100")).toBe(1100);
    expect(parseCentsInput("  42 ")).toBe(42);
  });

  it("rejects anything that is not a positive integer", () => {
    for (const bad of ["", "0", "-5", "11.00", "1e3", "abc", "1,100"]) {
      expect(parseCentsInput(bad)).toBeNull();
    }
  });
});

describe("maskAccountNumber", () => {
  it("masks a 16-digit account number to its last 4 digits", () => {
    // The space is part of the format, matching the bound design's literal
    // output ("•••• 3456"), not an incidental extra character.
    expect(maskAccountNumber("1234567890123456")).toBe("•••• 3456");
  });

  it("never throws and never exposes more than the trailing 4 characters", () => {
    expect(maskAccountNumber("123")).toBe("•••• 123");
    expect(maskAccountNumber("")).toBe("•••• ");
    expect(maskAccountNumber("abc-def")).toBe("•••• -def");
    expect(maskAccountNumber("12345")).toBe("•••• 2345");
  });

  it("caps exposure on input longer than a real account number", () => {
    // A malformed value is still sensitive: length must never widen the window.
    expect(maskAccountNumber("1".repeat(40) + "9876")).toBe("•••• 9876");
  });

  it("exposes at most 4 characters for any input", () => {
    const inputs = ["", "1", "12", "123", "1234", "12345", "1234567890123456", "x".repeat(64)];
    for (const input of inputs) {
      const masked = maskAccountNumber(input);
      expect(masked.startsWith("•••• ")).toBe(true);
      expect(masked.slice(5).length).toBeLessThanOrEqual(4);
    }
  });
});
