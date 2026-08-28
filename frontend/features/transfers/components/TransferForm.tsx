"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatCents, parseCentsInput } from "@/lib/money";
import type { TransferRequestBody } from "../types";

interface Props {
  disabled: boolean;
  onSubmit: (body: TransferRequestBody) => void;
}

export function TransferForm({ disabled, onSubmit }: Props) {
  const [sourceAccount, setSourceAccount] = useState("acc-123");
  const [destinationAccount, setDestinationAccount] = useState("acc-456");
  const [amount, setAmount] = useState("1100");

  const cents = parseCentsInput(amount);
  const canSubmit =
    !disabled && cents !== null && sourceAccount.trim() !== "" && destinationAccount.trim() !== "";

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (cents === null) return;
    onSubmit({
      source_account: sourceAccount.trim(),
      destination_account: destinationAccount.trim(),
      amount: cents,
    });
  }

  return (
    <form className="flex flex-col gap-ds-2 rounded-md bg-surface p-ds-3" onSubmit={handleSubmit}>
      <div className="field">
        <Label htmlFor="source">From account</Label>
        <Input
          id="source"
          value={sourceAccount}
          onChange={(event) => setSourceAccount(event.target.value)}
          disabled={disabled}
          autoComplete="off"
        />
      </div>

      <div className="field">
        <Label htmlFor="destination">To account</Label>
        <Input
          id="destination"
          value={destinationAccount}
          onChange={(event) => setDestinationAccount(event.target.value)}
          disabled={disabled}
          autoComplete="off"
        />
      </div>

      <div className="field">
        <Label htmlFor="amount">Amount in cents</Label>
        <Input
          id="amount"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          disabled={disabled}
          inputMode="numeric"
          autoComplete="off"
          aria-describedby="amount-hint"
        />
        <p id="amount-hint" className="hint">
          {cents === null
            ? "Whole cents only, greater than zero."
            : `Sending ${formatCents(cents)}. A fee is added on top by the gateway.`}
        </p>
      </div>

      <Button type="submit" className="w-full" disabled={!canSubmit}>
        {disabled ? "Working…" : "Send transfer"}
      </Button>
    </form>
  );
}
