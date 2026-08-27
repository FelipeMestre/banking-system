"use client";

import { useState } from "react";
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
    <form className="card" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="source">From account</label>
        <input
          id="source"
          className="input"
          value={sourceAccount}
          onChange={(event) => setSourceAccount(event.target.value)}
          disabled={disabled}
          autoComplete="off"
        />
      </div>

      <div className="field">
        <label htmlFor="destination">To account</label>
        <input
          id="destination"
          className="input"
          value={destinationAccount}
          onChange={(event) => setDestinationAccount(event.target.value)}
          disabled={disabled}
          autoComplete="off"
        />
      </div>

      <div className="field">
        <label htmlFor="amount">Amount in cents</label>
        <input
          id="amount"
          className="input"
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

      <button type="submit" className="btn btn-primary btn-block" disabled={!canSubmit}>
        {disabled ? "Working…" : "Send transfer"}
      </button>
    </form>
  );
}
