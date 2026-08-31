"use client";

import type { ReactNode } from "react";
import { Auth0Provider, type AppState } from "@auth0/auth0-react";
import { useRouter } from "next/navigation";
import { auth0ClientId, auth0Domain } from "./config";

interface Props {
  children: ReactNode;
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
      }}
      onRedirectCallback={onRedirectCallback}
    >
      {children}
    </Auth0Provider>
  );
}
