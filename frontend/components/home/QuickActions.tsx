"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { PayBillDialog } from "@/features/credit-cards";

interface Props {
  /** Called once a bill payment is actually accepted, so the caller can
   * refresh whatever credit-card summary it shows elsewhere on the page. */
  onBillPaid?: () => void;
}

/**
 * "Download statement" has no destination in this app yet — rendering it
 * `disabled` rather than live-looking-but-inert is the same honesty rule
 * applied to the sidebar's non-Home icons: nothing on this screen should
 * look clickable and silently do nothing. "Pay a bill" now opens the real
 * card-selection + payment flow.
 */
export function QuickActions({ onBillPaid }: Props) {
  const [payBillOpen, setPayBillOpen] = useState(false);

  return (
    <section>
      <h6 className="mb-[14px] text-xs">Quick actions</h6>
      <div className="flex flex-col gap-[2px]">
        <Button asChild className="w-full justify-start">
          <Link href="/transfer">Send a transfer</Link>
        </Button>
        <Button
          type="button"
          variant="outline"
          className="w-full justify-start"
          onClick={() => setPayBillOpen(true)}
        >
          Pay a bill
        </Button>
        <Button type="button" variant="outline" disabled className="w-full justify-start">
          Download statement
        </Button>
      </div>
      {payBillOpen ? (
        <PayBillDialog
          onClose={() => setPayBillOpen(false)}
          onPaid={() => onBillPaid?.()}
        />
      ) : null}
    </section>
  );
}
