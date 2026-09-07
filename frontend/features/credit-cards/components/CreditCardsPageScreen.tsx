"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { LoadingScreen } from "@/components/ui/loading-screen";
import { ApiError } from "@/lib/api/client";
import { downloadStatementPdf } from "../api/download-statement-pdf";
import { getCardAccounts } from "../api/get-card-accounts";
import { getCurrentCustomer } from "../api/get-current-customer";
import { getInstallmentPayoff } from "../api/get-installment-payoff";
import { getMovements } from "../api/get-movements";
import { getStatements } from "../api/get-statements";
import { CardDetail } from "./CardDetail";
import { CardList } from "./CardList";
import { CurrentCycleSummary } from "./CurrentCycleSummary";
import { MovementsList } from "./MovementsList";
import { PayDialog } from "./PayDialog";
import { StatementCycleTabs } from "./StatementCycleTabs";
import { StatementTotalsSidebar } from "./StatementTotalsSidebar";
import type {
  CardAccountListItem,
  CardMovement,
  InstallmentPayoff,
  Statement,
} from "../types";

const CARD_ACCOUNTS_PAGE_SIZE = 50;
const MOVEMENTS_PAGE_SIZE = 100;
const STATEMENTS_PAGE_SIZE = 24;

type CardsState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; items: CardAccountListItem[] };

export function CreditCardsPageScreen() {
  const [cardsState, setCardsState] = useState<CardsState>({ kind: "loading" });
  const [selectedCardAccountId, setSelectedCardAccountId] = useState<string | null>(null);
  const [statements, setStatements] = useState<Statement[]>([]);
  const [selectedStatementId, setSelectedStatementId] = useState<string | null>(null);
  const [movements, setMovements] = useState<CardMovement[]>([]);
  const [payoff, setPayoff] = useState<InstallmentPayoff | null>(null);
  const [payDialogOpen, setPayDialogOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [isCardsStale, setIsCardsStale] = useState(false);

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

  const refreshCards = useCallback(() => {
    return getCurrentCustomer()
      .then((customer) => getCardAccounts({ customerId: customer.id, limit: CARD_ACCOUNTS_PAGE_SIZE, offset: 0 }))
      .then((page) => {
        setCardsState({ kind: "ready", items: page.items });
        setSelectedCardAccountId((current) => {
          if (current && page.items.some((i) => i.card_account.id === current)) return current;
          return page.items[0]?.card_account.id ?? null;
        });
      })
      .catch(() => {
        // keep last cardsState on refresh failure; staleness will still clear via timer
      });
  }, []);

  const refreshDetail = useCallback(() => {
    if (!selectedCardAccountId) return;
    getInstallmentPayoff(selectedCardAccountId).then(setPayoff).catch(() => setPayoff(null));
    getStatements({ cardAccountId: selectedCardAccountId, limit: STATEMENTS_PAGE_SIZE })
      .then((rows) => {
        setStatements(rows);
        setSelectedStatementId((current) =>
          rows.some((row) => row.id === current) ? current : (rows[0]?.id ?? null),
        );
      })
      .catch(() => {
        setStatements([]);
        setSelectedStatementId(null);
      });
  }, [selectedCardAccountId]);

  useEffect(() => {
    setStatements([]);
    setSelectedStatementId(null);
    setPayoff(null);
    refreshDetail();
  }, [refreshDetail]);

  const loadMovements = useCallback(() => {
    if (!selectedCardAccountId) {
      setMovements([]);
      return;
    }
    getMovements({
      cardAccountId: selectedCardAccountId,
      limit: MOVEMENTS_PAGE_SIZE,
      offset: 0,
      statementId: selectedStatementId ?? undefined,
    })
      .then((page) => setMovements(page.items))
      .catch(() => setMovements([]));
  }, [selectedCardAccountId, selectedStatementId]);

  useEffect(() => loadMovements(), [loadMovements]);

  const pendingMovementsRefreshRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingCardsRefreshRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (pendingMovementsRefreshRef.current !== null) {
        clearTimeout(pendingMovementsRefreshRef.current);
      }
      if (pendingCardsRefreshRef.current !== null) {
        clearTimeout(pendingCardsRefreshRef.current);
      }
    };
  }, []);

  const refreshMovementsAfterPayment = useCallback(() => {
    loadMovements();
    if (pendingMovementsRefreshRef.current !== null) {
      clearTimeout(pendingMovementsRefreshRef.current);
    }
    pendingMovementsRefreshRef.current = setTimeout(loadMovements, 1500);
  }, [loadMovements]);

  const refreshCardsAfterPayment = useCallback(() => {
    refreshCards();
    if (pendingCardsRefreshRef.current !== null) {
      clearTimeout(pendingCardsRefreshRef.current);
    }
    setIsCardsStale(true);
    pendingCardsRefreshRef.current = setTimeout(() => {
      refreshCards().finally(() => {
        setIsCardsStale(false);
        pendingCardsRefreshRef.current = null;
      });
    }, 1500);
  }, [refreshCards]);

  const selectedStatement = statements.find((row) => row.id === selectedStatementId) ?? null;

  const handleDownload = useCallback(() => {
    if (!selectedCardAccountId || !selectedStatement) return;
    setDownloading(true);
    downloadStatementPdf(
      selectedCardAccountId,
      selectedStatement.id,
      `statement-${selectedStatement.period_end}.pdf`,
    )
      .catch(() => {
        // Best-effort: the customer can retry the download; nothing else on
        // the page depends on this succeeding.
      })
      .finally(() => setDownloading(false));
  }, [selectedCardAccountId, selectedStatement]);

  if (cardsState.kind === "loading") {
    return <LoadingScreen message="Loading your cards…" fullScreen={false} showBranding={false} />;
  }

  if (cardsState.kind === "error") {
    return <p className="m-0 text-sm text-neutral-600">{cardsState.message}</p>;
  }

  const selectedCard = cardsState.items.find(
    (item) => item.card_account.id === selectedCardAccountId,
  );

  return (
    <div className="flex flex-col gap-ds-4">
      <h1 className="m-0 font-heading text-[20px] font-extrabold tracking-[-0.01em]">Your cards</h1>

      <section className="flex flex-col gap-ds-2">
        <h6 className="m-0">Select a card</h6>
        <CardList
          items={cardsState.items}
          selectedCardAccountId={selectedCardAccountId}
          onSelect={setSelectedCardAccountId}
        />
      </section>

      {selectedCard ? (
        <div className="flex flex-col gap-ds-4">
          <CardDetail
            cardAccount={selectedCard.card_account}
            isStale={isCardsStale}
            onPay={() => setPayDialogOpen(true)}
          />

          <section className="flex flex-col gap-ds-2">
            <h6 className="m-0">
              Current cycle{selectedStatement ? ` — ${selectedStatement.period_end}` : ""}
            </h6>
            {selectedStatement ? (
              <CurrentCycleSummary
                statement={selectedStatement}
                onPay={() => setPayDialogOpen(true)}
                onDownload={handleDownload}
                downloading={downloading}
              />
            ) : (
              <p className="m-0 border-2 border-divider p-ds-4 text-sm text-neutral-600">
                No billing cycle has closed yet.
              </p>
            )}
          </section>

          <section className="flex flex-col gap-ds-2">
            <h6 className="m-0">
              Billing cycles{selectedCard?.card ? ` — ${selectedCard.card.card_number}` : ""}
            </h6>
            <StatementCycleTabs
              statements={statements}
              selectedStatementId={selectedStatementId}
              onSelect={setSelectedStatementId}
            />
          </section>

          <div className="grid grid-cols-1 gap-ds-4 md:grid-cols-[1fr_240px]">
            <section className="flex flex-col gap-ds-2">
              <h6 className="m-0">
                Movements{selectedStatement ? ` — ${selectedStatement.period_end}` : ""}
              </h6>
              <MovementsList items={movements} />
            </section>
            <section className="flex flex-col gap-ds-2">
              <h6 className="m-0">
                Totals{selectedStatement ? ` — ${selectedStatement.period_end}` : ""}
              </h6>
              {selectedStatement ? (
                <StatementTotalsSidebar statement={selectedStatement} cycleMovements={movements} />
              ) : (
                <p className="m-0 border-2 border-divider p-ds-4 text-sm text-neutral-600">
                  No billing cycle has closed yet.
                </p>
              )}
            </section>
          </div>
        </div>
      ) : null}
      {payDialogOpen && selectedCardAccountId ? (
        <PayDialog
          cardAccountId={selectedCardAccountId}
          onClose={() => setPayDialogOpen(false)}
          onPaid={() => {
            refreshDetail();
            refreshMovementsAfterPayment();
            refreshCardsAfterPayment();
          }}
          presets={
            selectedStatement
              ? {
                  minimum: selectedStatement.minimum_payment,
                  full: selectedStatement.total_due,
                  installmentPayoff: payoff?.payoff_amount,
                }
              : payoff
                ? { installmentPayoff: payoff.payoff_amount }
                : undefined
          }
        />
      ) : null}
    </div>
  );
}
