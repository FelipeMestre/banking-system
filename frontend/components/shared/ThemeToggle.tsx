"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { DS_ICON_PROPS } from "@/lib/icon-props";

/**
 * `resolvedTheme` is undefined until next-themes reads localStorage on
 * mount, which happens after the server-rendered HTML paints. Rendering
 * both icons' worth of state before then would flash the wrong icon, so
 * this stays a neutral placeholder until `mounted` flips.
 */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = mounted && resolvedTheme === "dark";

  return (
    <button
      type="button"
      title={mounted ? (isDark ? "Switch to light mode" : "Switch to dark mode") : "Toggle theme"}
      aria-label="Toggle color theme"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className="flex h-[52px] w-[52px] items-center justify-center text-neutral-700 hover:cursor-pointer hover:bg-neutral-200 hover:text-text"
    >
      {mounted && !isDark ? <Moon size={21} {...DS_ICON_PROPS} /> : <Sun size={21} {...DS_ICON_PROPS} />}
    </button>
  );
}
