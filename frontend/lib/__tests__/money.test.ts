import { describe, expect, it } from "vitest";
import { formatCents, parseCentsInput } from "../money";

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
