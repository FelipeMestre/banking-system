"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/home/Sidebar";
import { Topbar } from "@/components/home/Topbar";
import { RequireAuth } from "@/lib/auth/RequireAuth";

// Invented — there is no endpoint for a personalized greeting or a last
// sign-in timestamp today. Static, same values `lib/placeholder-home.ts`
// used to hold, kept here since nothing else in the app needs them.
const CUSTOMER_GREETING = "Good afternoon";
const LAST_SIGN_IN = "";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isTransfer = pathname === "/transfer" || pathname.startsWith("/transfer/");

  return (
    <RequireAuth>
      <div className="grid min-h-screen grid-cols-[76px_1fr] bg-bg text-text">
        <Sidebar />
        <div className="flex min-w-0 flex-col">
          {isTransfer ? null : <Topbar greeting={CUSTOMER_GREETING} lastSignIn={LAST_SIGN_IN} />}
          <main
            className={
              isTransfer
                ? "flex min-w-0 flex-1 flex-col bg-bg"
                : "flex min-w-0 flex-1 flex-col px-ds-8 pt-[28px] pb-[40px]"
            }
          >
            {children}
          </main>
        </div>
      </div>
    </RequireAuth>
  );
}
