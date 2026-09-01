import { Sidebar } from "@/components/home/Sidebar";
import { Topbar } from "@/components/home/Topbar";
import { RequireAuth } from "@/lib/auth/RequireAuth";

// Invented — there is no endpoint for a personalized greeting or a last
// sign-in timestamp today. Static, same values `lib/placeholder-home.ts`
// used to hold, kept here since nothing else in the app needs them.
const CUSTOMER_GREETING = "Good afternoon";
const LAST_SIGN_IN = "";

/**
 * The dashboard shell (sidebar + topbar). A route group — `(dashboard)`
 * doesn't appear in the URL — so this wraps only `/` and not `/transfer`,
 * which the design handoff explicitly leaves unstyled by this system for now
 * ("expect a follow-up to bring it onto Modernist and under the same shell").
 */
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <div className="grid min-h-screen grid-cols-[76px_1fr] bg-bg text-text">
        <Sidebar />
        <div className="flex min-w-0 flex-col">
          <Topbar greeting={CUSTOMER_GREETING} lastSignIn={LAST_SIGN_IN} />
          <main className="flex min-w-0 flex-1 flex-col px-ds-8 pt-[28px] pb-[40px]">{children}</main>
        </div>
      </div>
    </RequireAuth>
  );
}
