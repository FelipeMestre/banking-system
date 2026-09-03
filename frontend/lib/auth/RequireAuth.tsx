"use client";

import { useEffect } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useRouter } from "next/navigation";
import { LoadingScreen } from "@/components/ui/loading-screen";

interface Props {
  children: React.ReactNode;
}

/**
 * Route-agnostic guard: redirects to `/login` unless the visitor is
 * authenticated with no Auth0 error. Mounted independently in each guarded
 * layout — it carries no route names or paths of its own.
 */
export function RequireAuth({ children }: Props): React.ReactElement | null {
  const { isLoading, isAuthenticated, error } = useAuth0();
  const router = useRouter();

  const shouldRedirectToLogin = !isLoading && (!isAuthenticated || Boolean(error));

  useEffect(() => {
    if (shouldRedirectToLogin) {
      router.replace("/login");
    }
  }, [shouldRedirectToLogin, router]);

  if (isLoading) {
    return <LoadingScreen message="Loading…" />;
  }

  if (shouldRedirectToLogin) {
    return null;
  }

  return <>{children}</>;
}
