/**
 * Auth0 tenant/application identifiers. Safe to ship to the browser: this is
 * a SPA application (Token Endpoint Auth Method: none, PKCE-based), so there
 * is no client secret and no security boundary crossed by exposing these —
 * same reasoning as `gatewayOrigin` in `lib/api/client.ts`.
 */
const DEFAULT_AUTH0_DOMAIN = "dev-ekwg1eyvfjrof0to.us.auth0.com";
const DEFAULT_AUTH0_CLIENT_ID = "cwGe8nQhKP6EYpmCseLd3yOHDWIU1Ynp";

export function auth0Domain(): string {
  return process.env.NEXT_PUBLIC_AUTH0_DOMAIN ?? DEFAULT_AUTH0_DOMAIN;
}

export function auth0ClientId(): string {
  return process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID ?? DEFAULT_AUTH0_CLIENT_ID;
}
