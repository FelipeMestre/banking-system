"use client";

import { useEffect, type ReactNode } from "react";
import { Auth0Provider, useAuth0, type AppState } from "@auth0/auth0-react";
import { useRouter } from "next/navigation";
import { setAccessTokenGetter } from "../api/client";
import { auth0Audience, auth0ClientId, auth0Domain } from "./config";

interface Props {
  children: ReactNode;
}

/**
 * Registers `getAccessTokenSilently` with `lib/api/client.ts` on mount.
 *
 * Plain API-client functions (e.g. `features/accounts/api/get-accounts.ts`)
 * are not React components and cannot call `useAuth0()` themselves — this
 * bridge is what lets `authorizedFetch` reach the SDK's token cache anyway.
 * Deregisters on unmount so a stale getter never outlives its provider.
 */
function AccessTokenBridge({ children }: { children: ReactNode }) {
  const { getAccessTokenSilently } = useAuth0();

  useEffect(() => {
    setAccessTokenGetter(async () => {
      try {
        return await getAccessTokenSilently();
      } catch {
        // Not authenticated yet, or silent renewal failed — the request this
        // token was for will simply go out unauthenticated and get its own
        // 401, which is the correct failure mode here, not a crash.
        return undefined;
      }
    });
    return () => setAccessTokenGetter(null);
  }, [getAccessTokenSilently]);

  return <>{children}</>;
}

/**
 * Wraps the app with Auth0Provider. Next.js still server-renders a "use
 * client" component's initial HTML, where `window` doesn't exist yet — the
 * `typeof window` guard below is why `redirect_uri` doesn't crash on that
 * first server pass. Everything else the SDK does (handling the callback,
 * silent renewal) runs from its own effects, which never run on the server.
 */
export function Auth0ProviderWithNavigate({ children }: Props) {
  const router = useRouter();

  function onRedirectCallback(appState?: AppState) {
    router.push(appState?.returnTo ?? "/");
  }

  return (
    <Auth0Provider
      domain={auth0Domain()}
      clientId={auth0ClientId()}
      authorizationParams={{
        redirect_uri: typeof window !== "undefined" ? window.location.origin : undefined,
        audience: auth0Audience(),
      }}
      onRedirectCallback={onRedirectCallback}
    >
      <AccessTokenBridge>{children}</AccessTokenBridge>
    </Auth0Provider>
  );
}
