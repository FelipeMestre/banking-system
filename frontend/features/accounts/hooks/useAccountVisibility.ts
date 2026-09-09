"use client";

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "openbank:accounts-visible";

function readStoredValue(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    // Private browsing / blocked storage — fall back to the hidden default.
    return false;
  }
}

/**
 * Whether account numbers and balances show in the clear, or masked.
 *
 * Defaults to hidden and persists in localStorage rather than any
 * session/auth state — this is a device-level display preference, not tied
 * to who's logged in, so it survives a logout and reloads unchanged the next
 * time someone signs back in on this device.
 *
 * Starts at `false` and syncs from storage in an effect, not a lazy
 * `useState` initializer: this runs inside a "use client" component that
 * Next.js still server-renders on its first pass, where `window` doesn't
 * exist yet (same reasoning as `Auth0ProviderWithNavigate`'s `typeof window`
 * guard) — reading synchronously would crash that pass or desync from the
 * client's first paint.
 */
export function useAccountVisibility() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(readStoredValue());
  }, []);

  const toggle = useCallback(() => {
    setVisible((current) => {
      const next = !current;
      try {
        window.localStorage.setItem(STORAGE_KEY, String(next));
      } catch {
        // Storage unavailable — the toggle still works for this render, it
        // just won't persist past a reload.
      }
      return next;
    });
  }, []);

  return { visible, toggle };
}
