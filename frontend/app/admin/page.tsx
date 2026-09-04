import { SimulatePurchaseButton } from "@/features/cards";
import { AdminTabs } from "./AdminTabs";

export default function Page() {
  return (
    <main className="mx-auto max-w-[960px] px-ds-6 py-ds-8">
      <header className="mb-ds-6 flex items-start justify-between gap-ds-4">
        <div>
          <h1>Admin</h1>
          <p className="m-0 text-[0.9rem] text-neutral-600">Manage accounts, branches, customers, and locations.</p>
        </div>
        <SimulatePurchaseButton />
      </header>
      <AdminTabs />
    </main>
  );
}
