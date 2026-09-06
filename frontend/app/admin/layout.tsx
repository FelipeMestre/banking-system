import { RequireAdmin } from "@/lib/auth/RequireAdmin";

export default function Layout({ children }: { children: React.ReactNode }) {
  return <RequireAdmin>{children}</RequireAdmin>;
}
