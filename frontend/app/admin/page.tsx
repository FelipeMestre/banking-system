import { AdminTabs } from "./AdminTabs";

export default function Page() {
  return (
    <main className="mx-auto max-w-[960px] px-ds-6 py-ds-8">
      <header className="mb-ds-6">
        <h1>Admin</h1>
        <p className="subtitle">Manage accounts, branches, customers, and locations.</p>
      </header>
      <AdminTabs />
    </main>
  );
}
