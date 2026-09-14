"use client";

import { CreditCard, Home, ArrowLeftRight, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { DS_ICON_PROPS } from "@/lib/icon-props";
import { usePermissions } from "@/lib/auth/usePermissions";
import { ThemeToggle } from "@/components/shared/ThemeToggle";

export function Sidebar() {
  const pathname = usePathname();
  const { hasReadAdmin } = usePermissions();
  const isHome = pathname === "/";
  const isTransfer = pathname === "/transfer" || pathname.startsWith("/transfer/");
  const isCards = pathname === "/cards" || pathname.startsWith("/cards/");
  const isAdmin = pathname === "/admin" || pathname.startsWith("/admin/");

  return (
    <nav className="flex h-full flex-col items-center border-r-2 border-divider bg-bg">
      <div className="flex h-[72px] w-full items-center justify-center border-b-2 border-divider">
        <div className="h-[22px] w-[22px] bg-accent" />
      </div>

      <div className="flex w-full flex-col items-center gap-[2px] py-[14px]">
        <Link
          href="/"
          title="Home"
          aria-current={isHome ? "page" : undefined}
          className={
            "flex h-[52px] w-[52px] items-center justify-center " +
            (isHome
              ? "bg-accent text-bg hover:bg-accent-600"
              : "text-neutral-700 hover:bg-neutral-200 hover:text-text")
          }
        >
          <Home size={21} {...DS_ICON_PROPS} />
        </Link>

        <Link
          href="/transfer"
          title="Payments"
          aria-current={isTransfer ? "page" : undefined}
          className={
            "flex h-[52px] w-[52px] items-center justify-center " +
            (isTransfer
              ? "bg-accent text-bg hover:bg-accent-600"
              : "text-neutral-700 hover:bg-neutral-200 hover:text-text")
          }
        >
          <ArrowLeftRight size={21} {...DS_ICON_PROPS} />
        </Link>

        <Link
          href="/cards"
          title="Cards"
          aria-current={isCards ? "page" : undefined}
          className={
            "flex h-[52px] w-[52px] items-center justify-center " +
            (isCards
              ? "bg-accent text-bg hover:bg-accent-600"
              : "text-neutral-700 hover:bg-neutral-200 hover:text-text")
          }
        >
          <CreditCard size={21} {...DS_ICON_PROPS} />
        </Link>
        {hasReadAdmin ? (
          <Link
            href="/admin"
            title="Admin"
            aria-current={isAdmin ? "page" : undefined}
            className={
              "flex h-[52px] w-[52px] items-center justify-center " +
              (isAdmin
                ? "bg-accent text-bg hover:bg-accent-600"
                : "text-neutral-700 hover:bg-neutral-200 hover:text-text")
            }
          >
            <ShieldCheck size={21} {...DS_ICON_PROPS} />
          </Link>
        ) : null}
      </div>

      <div className="mt-auto flex w-full flex-col items-center gap-[2px] border-t-2 border-divider py-[14px]">
        <ThemeToggle />
      </div>
    </nav>
  );
}
