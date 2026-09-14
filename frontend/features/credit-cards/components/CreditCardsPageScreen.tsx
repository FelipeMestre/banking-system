"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { LoadingScreen } from "@/components/ui/loading-screen";
import { ApiError } from "@/lib/api/client";
import { buildCarryForwardMovements } from "../build-carry-forward-movements";
import { downloadStatementPdf } from "../api/download-statement-pdf";
import { getCardAccounts } from "../api/get-card-accounts";
import { getCurrentCustomer } from "../api/get-current-customer";
import { getCurrentCycle } from "../api/get-current-cycle";
import { getInstallmentPayoff } from "../api/get-installment-payoff";
import { getMovements } from "../api/get-movements";
import { getStatements } from "../api/get-statements";
import { CardList } from "./CardList";
import { CurrentCycleProjection } from "./CurrentCycleProjection";
import { MovementsList } from "./MovementsList";
import { PayDialog } from "./PayDialog";
import { SelectedStatementSummary } from "./SelectedStatementSummary";
import { StatementCycleTabs } from "./StatementCycleTabs";
import { StatementTotalsSidebar } from "./StatementTotalsSidebar";
import type {
  CardAccountListItem,
  CardMovement,
  CurrentCycleProjection as CurrentCycleProjectionData,
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
  // `null` = the implicit leading "Current cycle" tab is selected (the live,
  // uncommitted cycle) — the default, rather than the most-recent CLOSED
  // statement, so a customer lands on the always-fresh live view first.
  const [selectedStatementId, setSelectedStatementId] = useState<string | null>(null);
  const [projection, setProjection] = useState<CurrentCycleProjectionData | null>(null);
  // Read by `loadMovements` for the `since` bound WITHOUT being one of its
  // dependencies — the live projection resolving on its own must never
  // re-trigger a second movements fetch; it only supplies the bound the
  // NEXT time movements are (re)loaded for some other reason.
  const projectionRef = useRef<CurrentCycleProjectionData | null>(null);
  const [movements, setMovements] = useState<CardMovement[]>([]);
  const [payoff, setPayoff] = useState<InstallmentPayoff | null>(null);
  const [payDialogOpen, setPayDialogOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);

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
    getCurrentCycle({ cardAccountId: selectedCardAccountId })
      .then((data) => {
        projectionRef.current = data;
        setProjection(data);
      })
      .catch(() => {
        projectionRef.current = null;
        setProjection(null);
      });
    getStatements({ cardAccountId: selectedCardAccountId, limit: STATEMENTS_PAGE_SIZE })
      .then((rows) => {
        setStatements(rows);
        // Keep the current selection if it still resolves (a specific
        // closed statement, or `null` for the always-valid current cycle);
        // only fall back to `null` if a previously-selected statement
        // disappeared from the list.
        setSelectedStatementId((current) =>
          current === null || rows.some((row) => row.id === current) ? current : null,
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
    setProjection(null);
    refreshDetail();
  }, [refreshDetail]);

  // A boolean, not the `projection` object itself: it flips false -> true
  // exactly once per card/cycle selection and then stays true, so a later
  // projection update (e.g. after a payment refreshes it with new figures)
  // does NOT change `loadMovements`'s identity and does NOT trigger a second,
  // redundant fetch — only the FIRST resolution needs to unblock movements.
  const projectionLoaded = projection !== null;

  const loadMovements = useCallback(() => {
    if (!selectedCardAccountId) {
      setMovements([]);
      return;
    }
    if (selectedStatementId === null) {
      // Current cycle selected: scope by `since` (the live projection's own
      // `period_start`), never `statement_id` — no `Statement` row exists
      // yet for the still-open cycle. Wait for the projection to resolve
      // rather than firing an unscoped fetch — that would return the whole
      // account history instead of "no movements yet", which is exactly
      // what a customer would see if the fallback below were skipped.
      if (!projectionLoaded) {
        setMovements([]);
        return;
      }
      getMovements({
        cardAccountId: selectedCardAccountId,
        limit: MOVEMENTS_PAGE_SIZE,
        offset: 0,
        since: projectionRef.current?.period_start,
      })
        .then((page) => setMovements(page.items))
        .catch(() => setMovements([]));
      return;
    }
    getMovements({
      cardAccountId: selectedCardAccountId,
      limit: MOVEMENTS_PAGE_SIZE,
      offset: 0,
      statementId: selectedStatementId,
    })
      .then((page) => setMovements(page.items))
      .catch(() => setMovements([]));
  }, [selectedCardAccountId, selectedStatementId, projectionLoaded]);

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
    pendingCardsRefreshRef.current = setTimeout(() => {
      refreshCards().finally(() => {
        pendingCardsRefreshRef.current = null;
      });
    }, 1500);
  }, [refreshCards]);

  const isCurrentCycleSelected = selectedStatementId === null;
  const selectedStatement = statements.find((row) => row.id === selectedStatementId) ?? null;

  const handleDownloadStatement = useCallback(
    (statement: Statement) => {
      if (!selectedCardAccountId) return;
      setDownloading(true);
      downloadStatementPdf(selectedCardAccountId, statement.id, `statement-${statement.period_end}.pdf`)
        .catch(() => {
          // Best-effort: the customer can retry the download; nothing else on
          // the page depends on this succeeding.
        })
        .finally(() => setDownloading(false));
    },
    [selectedCardAccountId],
  );

  const handleDownload = useCallback(() => {
    if (!selectedStatement) return;
    handleDownloadStatement(selectedStatement);
  }, [selectedStatement, handleDownloadStatement]);

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
    <div className="flex flex-col gap-[48px]">
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
        <div className="flex flex-col gap-[48px]">
          <section className="flex flex-col gap-ds-2">
            {isCurrentCycleSelected ? (
              projection ? (
                <CurrentCycleProjection
                  projection={projection}
                  onPay={() => setPayDialogOpen(true)}
                />
              ) : (
                <>
                  <h6 className="m-0">Current cycle</h6>
                  <p className="m-0 border-2 border-divider p-ds-4 text-sm text-neutral-600">
                    Loading the current cycle…
                  </p>
                </>
              )
            ) : selectedStatement ? (
              <SelectedStatementSummary
                statement={selectedStatement}
                onDownload={handleDownload}
                downloading={downloading}
                onPay={selectedStatement.payable ? () => setPayDialogOpen(true) : undefined}
              />
            ) : (
              <>
                <h6 className="m-0">Billing cycle</h6>
                <p className="m-0 border-2 border-divider p-ds-4 text-sm text-neutral-600">
                  No billing cycle has closed yet.
                </p>
              </>
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
              onDownload={handleDownloadStatement}
              downloading={downloading}
            />
          </section>

          <div className="grid grid-cols-1 gap-ds-4 md:grid-cols-[1fr_240px]">
            <section className="flex flex-col gap-ds-2">
              <h6 className="m-0">
                Movements
                {isCurrentCycleSelected ? " — current cycle" : selectedStatement ? ` — ${selectedStatement.period_end}` : ""}
              </h6>
              <div
                data-testid="movements-scroll-container"
                className="scrollbar-app-bg max-h-[160px] overflow-y-auto pr-ds-1 sm:max-h-[190px] lg:max-h-[260px]"
              >
                <MovementsList
                  items={
                    isCurrentCycleSelected && projection
                      ? [...buildCarryForwardMovements(projection), ...movements]
                      : movements
                  }
                />
              </div>
            </section>
            <section className="flex flex-col gap-ds-2">
              <h6 className="m-0">
                Totals
                {isCurrentCycleSelected ? " — current cycle" : selectedStatement ? ` — ${selectedStatement.period_end}` : ""}
              </h6>
              {isCurrentCycleSelected ? (
                <p className="m-0 border-2 border-divider p-ds-4 text-sm text-neutral-600">
                  See the current-cycle figures above — this panel only breaks down a closed
                  billing cycle's movements.
                </p>
              ) : selectedStatement ? (
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
            isCurrentCycleSelected
              ? projection
                ? { full: projection.total_to_pay, installmentPayoff: payoff?.payoff_amount }
                : payoff
                  ? { installmentPayoff: payoff.payoff_amount }
                  : undefined
              : selectedStatement
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
