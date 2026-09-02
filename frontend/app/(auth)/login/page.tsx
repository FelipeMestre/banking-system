"use client";

import { useEffect } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

function LoginBackground() {
  return (
    <svg
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 size-full"
      viewBox="0 0 1440 900"
      preserveAspectRatio="xMidYMid slice"
      xmlns="http://www.w3.org/2000/svg"
    >
      <line x1="0" y1="150" x2="1440" y2="150" stroke="var(--color-divider)" strokeWidth="2" />
      <line x1="0" y1="750" x2="1440" y2="750" stroke="var(--color-divider)" strokeWidth="2" />
      <line x1="240" y1="0" x2="240" y2="900" stroke="var(--color-divider)" strokeWidth="2" />
      <line x1="1200" y1="0" x2="1200" y2="900" stroke="var(--color-divider)" strokeWidth="2" />
      <line x1="0" y1="0" x2="500" y2="900" stroke="var(--color-divider)" strokeWidth="1" />
      <line x1="1440" y1="0" x2="940" y2="900" stroke="var(--color-divider)" strokeWidth="1" />
    </svg>
  );
}

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
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-bg p-10 text-text md:p-5">
        <LoginBackground />
        <p className="relative z-10 text-sm text-neutral-600">Loading…</p>
      </div>
    );
  }

  if (isAuthenticated) {
    return (
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-bg p-10 text-text md:p-5">
        <LoginBackground />
        <div className="relative z-10 flex w-full max-w-[420px] flex-col gap-ds-8">
          <header className="flex flex-col items-center gap-[14px]">
            <div className="flex size-12 items-center justify-center bg-text">
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                aria-hidden="true"
                className="text-bg"
              >
                <rect x="3" y="9" width="18" height="11" stroke="currentColor" strokeWidth="2" />
                <path
                  d="M6 9V6a6 6 0 0 1 12 0v3"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="square"
                />
              </svg>
            </div>
            <div className="flex items-center gap-2.5">
              <span aria-hidden="true" className="size-[14px] bg-accent" />
              <span className="font-heading text-[24px] font-extrabold tracking-[-0.02em] text-text">
                OpenBank
              </span>
            </div>
          </header>

          <div className="flex flex-col items-center gap-ds-6 border-2 border-divider bg-bg p-9 px-ds-8 text-center">
            <div className="flex flex-col gap-ds-2">
              <h1 className="font-heading text-[18px] font-extrabold leading-none text-text">
                You are signed in
              </h1>
              <p className="text-[13px] leading-[1.5] text-neutral-700">
                Logged in as {user?.email ?? "your account"}.
              </p>
            </div>
            <div className="flex w-full flex-col gap-ds-3">
              <Button
                type="button"
                variant="outline"
                className="w-full justify-start rounded-none h-auto py-3 text-sm font-heading font-extrabold"
                onClick={handleLogout}
              >
                Log out
              </Button>
              <Button
                type="button"
                className="w-full justify-start rounded-none h-auto py-3 text-sm font-heading font-extrabold"
                onClick={() => router.push("/")}
              >
                Go to dashboard
              </Button>
            </div>
            {user ? (
              <pre className="max-h-32 w-full overflow-auto rounded-none bg-surface p-ds-3 text-left text-xs text-neutral-700">
                {JSON.stringify(user, null, 2)}
              </pre>
            ) : null}
          </div>

          <div className="flex items-center justify-center gap-ds-6 text-[11px] text-neutral-600">
            <span>© 2026 OpenBank</span>
            <span>Member FDIC</span>
            <span>Security Center</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-bg p-10 text-text md:p-5">
      <LoginBackground />

      <div className="relative z-10 flex w-full max-w-[420px] flex-col gap-ds-8">
        <header className="flex flex-col items-center gap-[14px]">
          <div className="flex size-12 items-center justify-center bg-text">
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
              className="text-bg"
            >
              <rect x="3" y="9" width="18" height="11" stroke="currentColor" strokeWidth="2" />
              <path
                d="M6 9V6a6 6 0 0 1 12 0v3"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="square"
              />
            </svg>
          </div>
          <div className="flex items-center gap-2.5">
            <span aria-hidden="true" className="size-[14px] bg-accent" />
            <span className="font-heading text-[24px] font-extrabold tracking-[-0.02em] text-text">
              OpenBank
            </span>
          </div>
        </header>

        <div className="flex flex-col items-center gap-ds-6 border-2 border-divider bg-bg p-9 px-ds-8 text-center">
          <div className="flex flex-col gap-ds-2">
            <h1 className="font-heading text-[18px] font-extrabold leading-none text-text">
              Welcome to OpenBank
            </h1>
            <p className="text-[13px] leading-[1.5] text-neutral-700">
              Log in or create an account through our secure identity provider.
            </p>
          </div>

          {error ? (
            <p role="alert" className="w-full text-left text-[13px] leading-[1.5] text-accent-700">
              Error: {error.message}
            </p>
          ) : null}

          <div className="flex w-full flex-col gap-ds-3">
            <Button
              type="button"
              className="w-full justify-start rounded-none h-auto py-3 text-sm font-heading font-extrabold"
              onClick={() => loginWithRedirect()}
            >
              Log in
            </Button>
            <Button
              type="button"
              variant="outline"
              className="w-full justify-start rounded-none h-auto py-3 text-sm font-heading font-extrabold"
              onClick={signup}
            >
              Create account
            </Button>
          </div>

          <p className="text-[11px] leading-[1.5] text-neutral-600">
            You&apos;ll be redirected to OpenBank&apos;s authentication provider, then returned here
            automatically.
          </p>
        </div>

        <div className="flex items-center justify-center gap-ds-6 text-[11px] text-neutral-600">
          <span>© 2026 OpenBank</span>
          <span>Member FDIC</span>
          <span>Security Center</span>
        </div>
      </div>
    </div>
  );
}
