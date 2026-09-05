"use client";

import { useCallback, useEffect, useState } from "react";
import { LoadingScreen } from "@/components/ui/loading-screen";
import { ApiError } from "@/lib/api/client";
import { getCardAccounts } from "../api/get-card-accounts";
import { getCurrentCustomer } from "../api/get-current-customer";
import { getMovements } from "../api/get-movements";
import { getUsedCredit } from "../api/get-used-credit";
import { CardDetail } from "./CardDetail";
import { CardList } from "./CardList";
import { MovementsList } from "./MovementsList";
import { PayDialog } from "./PayDialog";
import type { CardAccountListItem, CardMovement, UsedCreditEstimate } from "../types";

const CARD_ACCOUNTS_PAGE_SIZE = 50;
const MOVEMENTS_PAGE_SIZE = 20;

type CardsState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; items: CardAccountListItem[] };

/**
 * Composes the customer-facing Cards page from the real `card-accounts`,
 * used-credit-estimate, and movements endpoints. Explicitly renders NONE of
 * Phase 4's billing UI (spec: "Explicit Exclusion of Phase-4 Billing UI") —
 * no cycle/statement/minimum-payment/due-date/PDF/late-fee element, and no
 * card issue/renew/block action (that stays admin-only Phase 1 CRUD).
 */
export function CreditCardsPageScreen() {
  const [cardsState, setCardsState] = useState<CardsState>({ kind: "loading" });
  const [selectedCardAccountId, setSelectedCardAccountId] = useState<string | null>(null);
  const [estimate, setEstimate] = useState<UsedCreditEstimate | null>(null);
  const [movements, setMovements] = useState<CardMovement[]>([]);
  const [payDialogOpen, setPayDialogOpen] = useState(false);

  const loadCards = useCallback(() => {
    setCardsState({ kind: "loading" });
    getCurrentCustomer()
      .then((customer) => getCardAccounts({ customerId: customer.id, limit: CARD_ACCOUNTS_PAGE_SIZE, offset: 0 }))
      .then((page) => {
        setCardsState({ kind: "ready", items: page.items });
        setSelectedCardAccountId((current) => current ?? page.items[0]?.card_account.id ?? null);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 404) {
          setCardsState({ kind: "ready", items: [] });
          return;
        }
        setCardsState({
          kind: "error",
          message: error instanceof Error ? error.message : "Could not load your cards.",
        });
      });
  }, []);

  useEffect(() => loadCards(), [loadCards]);

  const refreshDetail = useCallback(() => {
    if (!selectedCardAccountId) return;
    getUsedCredit(selectedCardAccountId).then(setEstimate).catch(() => setEstimate(null));
    getMovements({ cardAccountId: selectedCardAccountId, limit: MOVEMENTS_PAGE_SIZE, offset: 0 })
      .then((page) => setMovements(page.items))
      .catch(() => setMovements([]));
  }, [selectedCardAccountId]);

  useEffect(() => {
    setEstimate(null);
    setMovements([]);
    refreshDetail();
  }, [refreshDetail]);

  if (cardsState.kind === "loading") {
    return <LoadingScreen message="Loading your cards…" fullScreen={false} showBranding={false} />;
  }

  if (cardsState.kind === "error") {
    return <p className="m-0 text-sm text-neutral-600">{cardsState.message}</p>;
  }

  return (
    <div className="flex flex-col gap-ds-4">
      <h1 className="m-0 font-heading text-[20px] font-extrabold tracking-[-0.01em]">Your cards</h1>
      <div className="grid grid-cols-1 gap-ds-4 lg:grid-cols-[320px_1fr]">
        <CardList
          items={cardsState.items}
          selectedCardAccountId={selectedCardAccountId}
          onSelect={setSelectedCardAccountId}
        />
        {selectedCardAccountId ? (
          <div className="flex flex-col gap-ds-4">
            <CardDetail
              estimate={estimate}
              loading={estimate === null}
              onPay={() => setPayDialogOpen(true)}
            />
            <MovementsList items={movements} />
          </div>
        ) : null}
      </div>
      {payDialogOpen && selectedCardAccountId ? (
        <PayDialog
          cardAccountId={selectedCardAccountId}
          onClose={() => setPayDialogOpen(false)}
          onPaid={refreshDetail}
        />
      ) : null}
    </div>
  );
}
