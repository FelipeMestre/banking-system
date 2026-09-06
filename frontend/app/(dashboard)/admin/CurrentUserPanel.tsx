"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePermissions } from "@/lib/auth/usePermissions";

/**
 * Shows the signed-in user's own effective permissions, decoded from their
 * Access Token client-side (spec: decode-only, backend RS256/JWKS remains
 * the real security boundary — see `lib/permissions/can.ts`).
 *
 * No "roles" here on purpose: this app has no roles concept today, only
 * `read:admin`/`write:admin` permissions. Auth0 doesn't put a roles claim on
 * a token unless a custom Action adds one, and none does here — showing an
 * empty "roles" section would just be confusing, not informative.
 */
export function CurrentUserPanel() {
  const { claims, permissions, isLoading } = usePermissions();
  const sub = typeof claims["sub"] === "string" ? claims["sub"] : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Your permissions</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-ds-3">
        {isLoading ? (
          <p className="m-0 text-sm text-neutral-600">Loading…</p>
        ) : (
          <>
            {sub ? (
              <p className="m-0 font-mono text-xs text-neutral-600">{sub}</p>
            ) : null}
            {permissions.length > 0 ? (
              <div className="flex flex-wrap gap-ds-2">
                {permissions.map((permission) => (
                  <Badge key={permission} variant="secondary">
                    {permission}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="m-0 text-sm text-neutral-600">No permissions on this token.</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
