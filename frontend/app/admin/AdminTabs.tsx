"use client";

import { useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AccountsList } from "@/features/accounts";
import { BranchesPanel } from "@/features/branches";
import { CustomersPanel } from "@/features/customers";
import { LocationsPanel } from "@/features/locations";
import { usePermissions } from "@/lib/auth/usePermissions";

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
  const { hasReadAdmin } = usePermissions();
  const [active, setActive] = useState<Tab>("Accounts");

  if (!hasReadAdmin) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Not authorized</AlertTitle>
        <AlertDescription>You need read:admin to view admin data.</AlertDescription>
      </Alert>
    );
  }

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
            <Panel />
          </TabsContent>
        );
      })}
    </Tabs>
  );
}
