"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AccountsList } from "@/features/accounts";
import { BranchesPanel } from "@/features/branches";
import { CustomersPanel } from "@/features/customers";
import { LocationsPanel } from "@/features/locations";

const TABS = ["Accounts", "Customers", "Branches", "Locations"] as const;
type Tab = (typeof TABS)[number];

const PANELS: Record<Tab, React.ComponentType> = {
  Accounts: AccountsList,
  Branches: BranchesPanel,
  Customers: CustomersPanel,
  Locations: LocationsPanel,
};

/**
 * Page-level composition, colocated with the route it belongs to (per the
 * feature-oriented architecture: app composes screens from feature
 * components, it doesn't own business logic itself). Each tab is wired to
 * its own feature's real API.
 */
export function AdminTabs() {
  const [active, setActive] = useState<Tab>("Accounts");

  return (
    <Tabs value={active} onValueChange={(value) => setActive(value as Tab)} className="gap-ds-6">
      <TabsList aria-label="Admin sections" className="w-fit">
        {TABS.map((tab) => (
          <TabsTrigger key={tab} value={tab} className="hover:cursor-pointer">
            {tab}
          </TabsTrigger>
        ))}
      </TabsList>

      {TABS.map((tab) => {
        const Panel = PANELS[tab];
        return (
          <TabsContent key={tab} value={tab}>
            <h2>{tab}</h2>
            <Panel />
          </TabsContent>
        );
      })}
    </Tabs>
  );
}
