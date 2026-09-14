"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { SimulatePurchaseDialog } from "./SimulatePurchaseDialog";

/** Opens `SimulatePurchaseDialog` — the admin-only credit card purchase testing tool. */
export function SimulatePurchaseButton() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button type="button" variant="outline" onClick={() => setOpen(true)}>
        Simulate purchase
      </Button>
      {open ? <SimulatePurchaseDialog onClose={() => setOpen(false)} /> : null}
    </>
  );
}
