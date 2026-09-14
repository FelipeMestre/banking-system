import { BatchJobsPanel, SimulatePurchaseButton } from "@/features/cards";
import { AdminTabs } from "./AdminTabs";
import { CurrentUserPanel } from "./CurrentUserPanel";

export default function Page() {
  return (
    <div className="mx-auto w-full">
      <header className="mb-ds-6 flex items-start justify-between gap-ds-4">
        <div>
          <h1>Admin</h1>
          <p className="m-0 text-[0.9rem] text-neutral-600">Manage accounts, customers, and credit cards.</p>
        </div>
        <SimulatePurchaseButton />
      </header>
      <div className="mb-ds-6 flex gap-12">
        <CurrentUserPanel />
        <section className="flex flex-col gap-ds-3 border-2 border-divider p-ds-4">
          <div>
            <h2 className="m-0">Monthly batch (testing)</h2>
            <p className="m-0 text-[0.85rem] text-neutral-600">
              Manually run the credit card batch worker&apos;s jobs on demand, using today&apos;s
              real date, instead of waiting for the hourly cron.
            </p>
          </div>
          <BatchJobsPanel />
        </section>
      </div>
      
      <AdminTabs />
    </div>
  );
}
