"use client";

import { useEffect } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useRouter } from "next/navigation";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { LoadingScreen } from "@/components/ui/loading-screen";
import { usePermissions } from "./usePermissions";

interface Props {
  children: React.ReactNode;
}

export function RequireAdmin({ children }: Props): React.ReactElement | null {
  const { isLoading, isAuthenticated, error } = useAuth0();
  const { hasReadAdmin, isLoading: permLoading } = usePermissions();
  const router = useRouter();

  const shouldRedirectToLogin = !isLoading && (!isAuthenticated || Boolean(error));

  useEffect(() => {
    if (shouldRedirectToLogin) {
      router.replace("/login");
    }
  }, [shouldRedirectToLogin, router]);

  if (isLoading || permLoading) {
    return <LoadingScreen message="Loading…" />;
  }

  if (shouldRedirectToLogin) {
    return null;
  }

  if (!hasReadAdmin) {
    return (
      <Alert variant="destructive" className="m-ds-6">
        <AlertTitle>Not authorized</AlertTitle>
        <AlertDescription>You do not have permission to view the admin area. Required: read:admin.</AlertDescription>
      </Alert>
    );
  }

  return <>{children}</>;
}
