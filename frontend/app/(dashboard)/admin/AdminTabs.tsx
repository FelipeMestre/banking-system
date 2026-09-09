"use client";

import { useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AccountsPanel } from "@/features/accounts";
import { BranchesPanel } from "@/features/branches";
import { CardAccountAdminPanel } from "@/features/card-account-admin";
import { CustomersPanel } from "@/features/customers";
import { LocationsPanel } from "@/features/locations";
import { usePermissions } from "@/lib/auth/usePermissions";

const TABS = ["Accounts", "Customers", "Branches", "Locations", "Credit Cards"] as const;
type Tab = (typeof TABS)[number];

const PANELS: Record<Tab, React.ComponentType> = {
  Accounts: AccountsPanel,
  Branches: BranchesPanel,
  Customers: CustomersPanel,
  Locations: LocationsPanel,
  "Credit Cards": CardAccountAdminPanel,
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
          // `forceMount` + hide-when-inactive (rather than Radix's default
          // unmount-on-switch) keeps each panel's already-fetched data and
          // rendered height alive across tab switches. Unmounting used to
          // drop every panel back to its own "Loading…" state on every
          // switch, briefly collapsing the page's height and snapping the
          // scroll position to the top — uncomfortable on a long table.
          <TabsContent key={tab} value={tab} forceMount className="data-[state=inactive]:hidden">
            <Panel />
          </TabsContent>
        );
      })}
    </Tabs>
  );
}
