"use client";

import { useState } from "react";
import { usePermissions } from "@/lib/auth/usePermissions";
import { CardAccountsList } from "./CardAccountsList";
import { CustomerPicker } from "./CustomerPicker";

/**
 * Top-level admin panel for the "Credit Cards" tab: a customer picker gates
 * the card-accounts table, since listing card accounts requires a
 * `customer_id` (`GET /card-accounts?customer_id=` — `status` alone is 422).
 * Viewing the tab is already gated by `read:admin` in `AdminTabs`; mutation
 * buttons inside `CardAccountsList` are additionally gated by `write:admin`.
 */
export function CardAccountAdminPanel() {
  const { hasWriteAdmin } = usePermissions();
  const [customerId, setCustomerId] = useState<string | null>(null);

  return (
    <div className="flex flex-col gap-ds-4">
      <CustomerPicker value={customerId} onChange={setCustomerId} />
      {customerId ? (
        <CardAccountsList customerId={customerId} hasWriteAdmin={hasWriteAdmin} />
      ) : (
        <p className="m-0 text-[0.9rem] text-neutral-600">Select a customer to view their card accounts.</p>
      )}
    </div>
  );
}
