import { RequireAuth } from "@/lib/auth/RequireAuth";

export default function Layout({ children }: { children: React.ReactNode }) {
  return <RequireAuth>{children}</RequireAuth>;
}
