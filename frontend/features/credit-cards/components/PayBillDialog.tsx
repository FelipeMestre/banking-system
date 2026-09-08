"use client";

import { useEffect, useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { LoadingScreen } from "@/components/ui/loading-screen";
import { ApiError } from "@/lib/api/client";
import { getCardAccounts } from "../api/get-card-accounts";
import { getCurrentCustomer } from "../api/get-current-customer";
import { getInstallmentPayoff } from "../api/get-installment-payoff";
import { getStatements } from "../api/get-statements";
import { CardList } from "./CardList";
import { PayDialog, type PayDialogPresets } from "./PayDialog";
import type { CardAccountListItem, InstallmentPayoff, Statement } from "../types";

const CARD_ACCOUNTS_PAGE_SIZE = 50;

interface Props {
  onClose: () => void;
  /** Called once a payment has actually been accepted — the caller refreshes
   * whatever credit-card summary it shows (spec: same contract `PayDialog`
   * already exposes). */
  onPaid?: () => void;
}

type CardsState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; items: CardAccountListItem[] };

/**
 * The homepage's "Pay a bill" quick action: pick which card to pay, then pay
 * its latest closed cycle. Two stages sharing one flow — card selection
 * (reusing `CardList`, the same tiles the Cards page itself uses) followed
 * by the real `PayDialog`, preset to that cycle's `total_due`/`minimum_payment`
 * exactly the way `CreditCardsPageScreen` already wires it, just entered from
 * the homepage instead of from an already-selected card.
 */
export function PayBillDialog({ onClose, onPaid }: Props) {
  const [cardsState, setCardsState] = useState<CardsState>({ kind: "loading" });
  const [selectedCardAccountId, setSelectedCardAccountId] = useState<string | null>(null);
  const [latestStatement, setLatestStatement] = useState<Statement | null>(null);
  const [payoff, setPayoff] = useState<InstallmentPayoff | null>(null);

  useEffect(() => {
    let cancelled = false;
    getCurrentCustomer()
      .then((customer) => getCardAccounts({ customerId: customer.id, limit: CARD_ACCOUNTS_PAGE_SIZE, offset: 0 }))
      .then((page) => {
        if (cancelled) return;
        setCardsState({ kind: "ready", items: page.items });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 404) {
          setCardsState({ kind: "ready", items: [] });
          return;
        }
        setCardsState({
          kind: "error",
          message: error instanceof Error ? error.message : "Could not load your cards.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function selectCard(cardAccountId: string) {
    setSelectedCardAccountId(cardAccountId);
    getStatements({ cardAccountId, limit: 1 })
      .then((rows) => setLatestStatement(rows[0] ?? null))
      .catch(() => setLatestStatement(null));
    getInstallmentPayoff(cardAccountId)
      .then(setPayoff)
      .catch(() => setPayoff(null));
  }

  if (selectedCardAccountId) {
    const presets: PayDialogPresets | undefined = latestStatement
      ? {
          minimum: latestStatement.minimum_payment,
          full: latestStatement.total_due,
          installmentPayoff: payoff?.payoff_amount,
        }
      : payoff
        ? { installmentPayoff: payoff.payoff_amount }
        : undefined;

    return (
      <PayDialog cardAccountId={selectedCardAccountId} onClose={onClose} onPaid={onPaid} presets={presets} />
    );
  }

  return (
    <Dialog title="Pay a bill" onClose={onClose} onAccept={onClose} acceptLabel="Close" hideCancel>
      {cardsState.kind === "loading" ? (
        <LoadingScreen message="Loading your cards…" fullScreen={false} showBranding={false} />
      ) : cardsState.kind === "error" ? (
        <p className="m-0 text-sm text-neutral-600">{cardsState.message}</p>
      ) : cardsState.items.length === 0 ? (
        <p className="m-0 text-sm text-neutral-600">You have no credit cards yet.</p>
      ) : (
        <div className="flex flex-col gap-ds-2">
          <p className="m-0 text-sm text-neutral-600">Select a card to pay its latest cycle.</p>
          <CardList items={cardsState.items} selectedCardAccountId={null} onSelect={selectCard} />
        </div>
      )}
    </Dialog>
  );
}
