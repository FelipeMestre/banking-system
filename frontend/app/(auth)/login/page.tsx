"use client";

import { useEffect } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

/** A minimal page to exercise the Auth0 integration end to end. */
export default function LoginPage() {
  const { isLoading, isAuthenticated, error, loginWithRedirect, logout, user } = useAuth0();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace("/");
    }
  }, [isLoading, isAuthenticated, router]);

  function signup() {
    loginWithRedirect({ authorizationParams: { screen_hint: "signup" } });
  }

  function handleLogout() {
    logout({ logoutParams: { returnTo: window.location.origin } });
  }

  if (isLoading) {
    return (
      <main className="mx-auto max-w-[480px] px-ds-6 py-ds-8">
        <p className="m-0 text-[0.9rem] text-neutral-600">Loading…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-[480px] px-ds-6 py-ds-8">
      <h1>Auth0 test</h1>

      {isAuthenticated ? (
        <div className="flex flex-col gap-ds-3">
          <p className="m-0 text-[0.9rem] text-neutral-600">Logged in as {user?.email}</p>
          <pre className="overflow-x-auto rounded-md bg-surface p-ds-3 text-xs">
            {JSON.stringify(user, null, 2)}
          </pre>
          <Button type="button" variant="outline" onClick={handleLogout}>
            Logout
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-ds-3">
          {error ? <p className="m-0 text-[0.9rem] text-accent-700">Error: {error.message}</p> : null}
          <Button type="button" onClick={signup}>
            Signup
          </Button>
          <Button type="button" variant="outline" onClick={() => loginWithRedirect()}>
            Login
          </Button>
        </div>
      )}
    </main>
  );
}
