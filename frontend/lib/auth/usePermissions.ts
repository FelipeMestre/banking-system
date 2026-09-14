"use client";

import { useEffect, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { decodeClaims, effectivePermissions, hasPermission as hasPerm } from "../permissions/can";

/**
 * Hook to expose RBAC permissions from the Auth0 Access Token.
 *
 * Decode-only (no verify) — backend is security boundary.
 * `permissions[]` primary, `scope` fallback via `can.ts`.
 */
export function usePermissions() {
  const { getAccessTokenSilently, isAuthenticated, isLoading } = useAuth0();
  const [claims, setClaims] = useState<Record<string, unknown>>({});
  const [loadingClaims, setLoadingClaims] = useState(false);

  useEffect(() => {
    if (isLoading || !isAuthenticated) {
      setClaims({});
      return;
    }
    let cancelled = false;
    setLoadingClaims(true);
    getAccessTokenSilently()
      .then((token) => {
        if (cancelled) return;
        const decoded = decodeClaims(token ?? "");
        setClaims(decoded);
      })
      .catch(() => {
        if (!cancelled) setClaims({});
      })
      .finally(() => {
        if (!cancelled) setLoadingClaims(false);
      });
    return () => {
      cancelled = true;
    };
  }, [getAccessTokenSilently, isAuthenticated, isLoading]);

  const hasPermission = (permission: string): boolean => hasPerm(claims, permission);
  const hasReadAdmin = hasPermission("read:admin");
  const hasWriteAdmin = hasPermission("write:admin");
  const permissions = effectivePermissions(claims);

  return {
    claims,
    permissions,
    hasPermission,
    hasReadAdmin,
    hasWriteAdmin,
    isLoading: isLoading || loadingClaims,
    isAuthenticated,
  };
}
