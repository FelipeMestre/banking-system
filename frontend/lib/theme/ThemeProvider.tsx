"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ReactNode } from "react";

/**
 * Wraps next-themes. `attribute="class"` toggles `.dark` on `<html>`, which
 * is what globals.css's `.dark { --color-bg: ...; }` block and the
 * `@custom-variant dark (&:is(.dark *))` selector both key off. Persistence
 * (localStorage) and cross-tab sync are next-themes' own defaults — no
 * extra wiring needed here.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="dark" enableSystem={false}>
      {children}
    </NextThemesProvider>
  );
}
