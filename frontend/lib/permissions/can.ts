/**
 * Permission helpers — decode-only UX gate (spec admin-authorization).
 *
 * Backend is security boundary (RS256/JWKS). Frontend only hides
 * affordances. `permissions[]` primary, `scope` space-split fallback.
 * No verification here — just `atob` decode.
 */

export function effectivePermissions(claims: Record<string, unknown>): string[] {
  const perms = claims["permissions"];
  if (Array.isArray(perms) && perms.length > 0) {
    return perms.map((p) => String(p));
  }
  const scope = claims["scope"];
  if (typeof scope === "string" && scope.trim().length > 0) {
    return scope.split(/\s+/).filter(Boolean);
  }
  return [];
}

export function hasPermission(claims: Record<string, unknown>, permission: string): boolean {
  return effectivePermissions(claims).includes(permission);
}

export function hasAllPermissions(claims: Record<string, unknown>, required: string[]): boolean {
  const had = effectivePermissions(claims);
  return required.every((r) => had.includes(r));
}

export function hasAnyPermission(claims: Record<string, unknown>, required: string[]): boolean {
  const had = effectivePermissions(claims);
  return required.some((r) => had.includes(r));
}

/**
 * Decode JWT payload without verification (UX only).
 * Returns empty record on failure.
 */
export function decodeClaims(token: string): Record<string, unknown> {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return {};
    const payload = parts[1];
    if (!payload) return {};
    // base64url -> base64
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const json = atob(base64);
    const parsed = JSON.parse(json) as Record<string, unknown>;
    return parsed ?? {};
  } catch {
    return {};
  }
}
