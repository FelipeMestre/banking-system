"use client";

import { useState } from "react";
import { AccountsList } from "@/features/accounts";
import { BranchesList } from "@/features/branches";
import { CustomersList } from "@/features/customers";
import { LocationsPanel } from "@/features/locations";

const TABS = ["Accounts", "Branches", "Customers", "Locations"] as const;
type Tab = (typeof TABS)[number];

const PANELS: Record<Tab, React.ComponentType> = {
  Accounts: AccountsList,
  Branches: BranchesList,
  Customers: CustomersList,
  Locations: LocationsPanel,
};

/**
 * Page-level composition, colocated with the route it belongs to (per the
 * feature-oriented architecture: app composes screens from feature
 * components, it doesn't own business logic itself). Each tab is wired to
 * its own feature's real API. Styled as Modernist's `.seg` segmented
 * control, but driven by button + aria-selected state instead of radio
 * inputs — `.seg-opt`'s `:has(input:checked)` styling has nothing to key
 * off of without them.
 */
export function AdminTabs() {
  const [active, setActive] = useState<Tab>("Accounts");

  return (
    <div className="flex flex-col gap-ds-6">
      <div role="tablist" aria-label="Admin sections" className="seg w-fit">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={active === tab}
            onClick={() => setActive(tab)}
            className={
              "seg-opt " +
              (active === tab ? "bg-accent text-bg" : "hover:bg-neutral-200")
            }
          >
            {tab}
          </button>
        ))}
      </div>

      {TABS.map((tab) => {
        const Panel = PANELS[tab];
        return (
          <div key={tab} role="tabpanel" hidden={active !== tab}>
            <h2>{tab}</h2>
            <Panel />
          </div>
        );
      })}
    </div>
  );
}
