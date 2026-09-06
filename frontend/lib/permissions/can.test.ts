import { describe, expect, it } from "vitest";
import { effectivePermissions, hasPermission, hasAllPermissions } from "./can";

describe("effectivePermissions", () => {
  it("returns permissions array when present (primary)", () => {
    const claims = { permissions: ["read:admin"], scope: "write:admin" };
    expect(effectivePermissions(claims as Record<string, unknown>)).toEqual(["read:admin"]);
  });

  it("falls back to scope split when permissions absent", () => {
    const claims = { scope: "read:admin write:admin" };
    expect(new Set(effectivePermissions(claims as Record<string, unknown>))).toEqual(
      new Set(["read:admin", "write:admin"]),
    );
  });

  it("falls back when permissions empty", () => {
    const claims = { permissions: [], scope: "read:admin" };
    expect(effectivePermissions(claims as Record<string, unknown>)).toEqual(["read:admin"]);
  });

  it("returns empty when neither present", () => {
    expect(effectivePermissions({} as Record<string, unknown>)).toEqual([]);
    expect(effectivePermissions({ permissions: [], scope: "" } as unknown as Record<string, unknown>)).toEqual([]);
  });

  it("splits scope on whitespace variations", () => {
    const claims = { scope: "read:admin  write:admin\tread:other" };
    const result = effectivePermissions(claims as Record<string, unknown>);
    expect(result).toContain("read:admin");
    expect(result).toContain("write:admin");
  });

  it("ignores non-array permissions", () => {
    const claims = { permissions: "read:admin", scope: "write:admin" };
    expect(effectivePermissions(claims as unknown as Record<string, unknown>)).toEqual(["write:admin"]);
  });
});

describe("hasPermission", () => {
  it("returns true when permission present via permissions", () => {
    const claims = { permissions: ["read:admin"] };
    expect(hasPermission(claims as Record<string, unknown>, "read:admin")).toBe(true);
    expect(hasPermission(claims as Record<string, unknown>, "write:admin")).toBe(false);
  });

  it("returns true via scope fallback", () => {
    const claims = { scope: "read:admin write:admin" };
    expect(hasPermission(claims as Record<string, unknown>, "write:admin")).toBe(true);
  });

  it("permissions primary ignores scope", () => {
    const claims = { permissions: ["read:admin"], scope: "write:admin" };
    expect(hasPermission(claims as Record<string, unknown>, "write:admin")).toBe(false);
    expect(hasPermission(claims as Record<string, unknown>, "read:admin")).toBe(true);
  });

  it("returns false when no claims", () => {
    expect(hasPermission({} as Record<string, unknown>, "read:admin")).toBe(false);
  });
});

describe("hasAllPermissions", () => {
  it("checks all required", () => {
    const claims = { permissions: ["read:admin", "write:admin"] };
    expect(hasAllPermissions(claims as Record<string, unknown>, ["read:admin", "write:admin"])).toBe(true);
    expect(hasAllPermissions(claims as Record<string, unknown>, ["read:admin", "write:admin", "extra"])).toBe(false);
  });
});
