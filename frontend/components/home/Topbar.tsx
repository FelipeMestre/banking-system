"use client";

import { useRef } from "react";
import { Lock, LogOut, User } from "lucide-react";
import { useAuth0 } from "@auth0/auth0-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DS_ICON_PROPS } from "@/lib/icon-props";

interface Props {
  greeting: string;
  lastSignIn: string;
}

export function Topbar({ greeting, lastSignIn }: Props) {
  const { user, logout } = useAuth0();
  const logoutButtonRef = useRef<HTMLButtonElement>(null);

  function handleLogout() {
    logout({ logoutParams: { returnTo: window.location.origin } });
  }

  return (
    <header className="flex h-[72px] flex-none items-center justify-between gap-ds-6 border-b-2 border-divider px-ds-8">
      <div className="flex min-w-0 items-baseline gap-[14px]">
        <h1 className="m-0 text-xl tracking-[-0.01em]">{greeting}</h1>
        <span className="whitespace-nowrap text-xs text-neutral-600">{lastSignIn}</span>
      </div>

      <div className="flex items-center gap-ds-6">
        <div className="flex items-center gap-ds-2 font-body text-[11px] font-semibold uppercase tracking-[0.1em] text-neutral-700">
          <Lock size={14} {...DS_ICON_PROPS} />
          Secured session
        </div>

        <div className="h-[28px] w-[2px] bg-divider" />

        <div className="flex items-center gap-[10px]">
          <div className="h-[14px] w-[14px] bg-accent" />
          <span className="font-heading text-[19px] font-extrabold tracking-[-0.02em]">OpenBank</span>
        </div>

        <div className="h-[28px] w-[2px] bg-divider" />

        <DropdownMenu
          onOpenChange={(open) => {
            // Radix focuses the menu container on open, not the first item —
            // a keyboard user then needs an extra ArrowDown before Enter does
            // anything. With a single actionable item, focus it directly so
            // Enter works immediately once the menu opens. `onOpenAutoFocus`
            // isn't part of DropdownMenuContent's public props in this Radix
            // version, so this runs a tick after the item has mounted instead.
            if (open) requestAnimationFrame(() => logoutButtonRef.current?.focus());
          }}
        >
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="rounded-full"
              aria-label="Account menu"
            >
              <User size={18} {...DS_ICON_PROPS} />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56 bg-bg">
            {user?.email ? (
              <>
                <DropdownMenuLabel className="truncate font-normal text-neutral-600">
                  {user.email}
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
              </>
            ) : null}
            <DropdownMenuItem asChild variant="destructive">
              <button ref={logoutButtonRef} type="button" onClick={handleLogout} className="w-full">
                <LogOut size={14} {...DS_ICON_PROPS} />
                Log out
              </button>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
