"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { LoadingScreen } from "@/components/ui/loading-screen";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getCardAccounts } from "@/features/credit-cards/api/get-card-accounts";
import type { CardAccount, CardAccountListItem, MaskedCard } from "@/features/credit-cards/types";
import type { CardIssued } from "../types";
import { IssueCardAccountDialog } from "./IssueCardAccountDialog";
import { RenewCardDialog } from "./RenewCardDialog";
import { UpdateCardAccountStatusDialog } from "./UpdateCardAccountStatusDialog";
import { UpdateCardStatusDialog } from "./UpdateCardStatusDialog";
import { UpdateCreditLimitDialog } from "./UpdateCreditLimitDialog";

const PAGE_SIZE = 10;
const STATUS_FILTERS = ["all", "active", "blocked", "closed"] as const;
type StatusFilter = (typeof STATUS_FILTERS)[number];

const ACCOUNT_STATUS_BADGE: Record<CardAccount["status"], { variant: "default" | "secondary" | "outline"; className?: string }> = {
  active: { variant: "default" },
  blocked: { variant: "outline", className: "border-accent text-accent" },
  closed: { variant: "secondary" },
};

const CARD_STATUS_BADGE: Record<MaskedCard["status"], { variant: "default" | "secondary" | "outline"; className?: string }> = {
  active: { variant: "default" },
  blocked: { variant: "outline", className: "border-accent text-accent" },
  replaced: { variant: "secondary" },
  expired: { variant: "secondary" },
};

type Dialog =
  | { kind: "issue" }
  | { kind: "limit"; cardAccount: CardAccount }
  | { kind: "account-status"; cardAccount: CardAccount; targetStatus: CardAccount["status"] }
  | { kind: "renew"; cardAccountId: string }
  | { kind: "card-status"; card: MaskedCard; targetStatus: "active" | "blocked" };

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; items: CardAccountListItem[]; total: number };

/**
 * Paginated admin table of card accounts for one customer (mirrors
 * `AccountsList.tsx`'s loading/error/ready state machine), with a `status`
 * filter and inline mutation actions per row. Every mutation action is
 * gated by `write:admin` — the buttons render disabled (not hidden) when
 * the caller lacks it, same spirit as other permission gating in this app.
 */
export function CardAccountsList({
  customerId,
  hasWriteAdmin,
}: {
  customerId: string;
  hasWriteAdmin: boolean;
}) {
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState<StatusFilter>("all");
  const [state, setState] = useState<State>({ kind: "loading" });
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    getCardAccounts({
      customerId,
      limit: PAGE_SIZE,
      offset,
      status: status === "all" ? undefined : status,
    })
      .then((page) => {
        if (!cancelled) setState({ kind: "ready", items: page.items, total: page.total });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            kind: "error",
            message: error instanceof Error ? error.message : "Could not load card accounts.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [customerId, offset, status, reloadToken]);

  function reload() {
    setDialog(null);
    setReloadToken((token) => token + 1);
  }

  if (state.kind === "loading") {
    return <LoadingScreen message="Loading card accounts…" fullScreen={false} showBranding={false} />;
  }

  if (state.kind === "error") {
    return <p className="m-0 text-[0.9rem] text-neutral-600">{state.message}</p>;
  }

  const { items, total } = state;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="flex flex-col gap-ds-3">
      <div className="flex items-center justify-between gap-ds-3">
        <Select
          value={status}
          onValueChange={(next) => {
            setStatus(next as StatusFilter);
            setOffset(0);
          }}
        >
          <SelectTrigger aria-label="Filter by status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_FILTERS.map((option) => (
              <SelectItem key={option} value={option}>
                {option === "all" ? "All statuses" : option}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button type="button" onClick={() => setDialog({ kind: "issue" })} disabled={!hasWriteAdmin}>
          Issue card account
        </Button>
      </div>

      <div className="overflow-x-auto border-2 border-divider">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Card Account ID</TableHead>
              <TableHead>Card Number</TableHead>
              <TableHead>Credit Limit</TableHead>
              <TableHead>Account Status</TableHead>
              <TableHead>Card Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-neutral-600">
                  No card accounts to show.
                </TableCell>
              </TableRow>
            ) : (
              items.map((item) => (
                <TableRow key={item.card_account.id}>
                  <TableCell className="font-mono text-xs whitespace-normal break-all">
                    {item.card_account.id}
                  </TableCell>
                  <TableCell className="font-mono text-xs whitespace-normal break-all">
                    {item.card?.card_number ?? "—"}
                  </TableCell>
                  <TableCell>{item.card_account.credit_limit}</TableCell>
                  <TableCell>
                    <Badge
                      variant={ACCOUNT_STATUS_BADGE[item.card_account.status].variant}
                      className={ACCOUNT_STATUS_BADGE[item.card_account.status].className}
                    >
                      {item.card_account.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {item.card ? (
                      <Badge
                        variant={CARD_STATUS_BADGE[item.card.status].variant}
                        className={CARD_STATUS_BADGE[item.card.status].className}
                      >
                        {item.card.status}
                      </Badge>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell>
                    <RowActions item={item} hasWriteAdmin={hasWriteAdmin} onOpenDialog={setDialog} />
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-neutral-600">
          {total === 0 ? "No card accounts" : `Showing ${from}–${to} of ${total}`}
        </span>
        <div className="flex gap-ds-2">
          <Button type="button" variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
            Previous
          </Button>
          <Button type="button" variant="outline" disabled={to >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>
            Next
          </Button>
        </div>
      </div>

      {dialog?.kind === "issue" ? (
        <IssueCardAccountDialog customerId={customerId} onClose={() => setDialog(null)} onSuccess={reload} />
      ) : null}
      {dialog?.kind === "limit" ? (
        <UpdateCreditLimitDialog cardAccount={dialog.cardAccount} onClose={() => setDialog(null)} onSuccess={reload} />
      ) : null}
      {dialog?.kind === "account-status" ? (
        <UpdateCardAccountStatusDialog
          cardAccount={dialog.cardAccount}
          targetStatus={dialog.targetStatus}
          onClose={() => setDialog(null)}
          onSuccess={reload}
        />
      ) : null}
      {dialog?.kind === "renew" ? (
        <RenewCardDialog cardAccountId={dialog.cardAccountId} onClose={() => setDialog(null)} onSuccess={reload} />
      ) : null}
      {dialog?.kind === "card-status" ? (
        <UpdateCardStatusDialog
          card={dialog.card}
          targetStatus={dialog.targetStatus}
          onClose={() => setDialog(null)}
          onSuccess={reload}
        />
      ) : null}
    </div>
  );
}

/** Valid account-status transitions mirrored from `CARD_ACCOUNT_TRANSITIONS`
 * (openbankapi/domain/model.py) — active<->blocked, active/blocked->closed;
 * closed is terminal. */
const ACCOUNT_STATUS_TRANSITIONS: Record<CardAccount["status"], CardAccount["status"][]> = {
  active: ["blocked", "closed"],
  blocked: ["active", "closed"],
  closed: [],
};

function RowActions({
  item,
  hasWriteAdmin,
  onOpenDialog,
}: {
  item: CardAccountListItem;
  hasWriteAdmin: boolean;
  onOpenDialog: (dialog: Dialog) => void;
}) {
  const { card_account: cardAccount, card } = item;
  const nextAccountStatuses = ACCOUNT_STATUS_TRANSITIONS[cardAccount.status];

  return (
    <div className="flex flex-wrap gap-ds-2">
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={!hasWriteAdmin || cardAccount.status === "closed"}
        onClick={() => onOpenDialog({ kind: "limit", cardAccount })}
      >
        Update limit
      </Button>
      {nextAccountStatuses.includes("blocked") ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!hasWriteAdmin}
          onClick={() => onOpenDialog({ kind: "account-status", cardAccount, targetStatus: "blocked" })}
        >
          Block account
        </Button>
      ) : null}
      {nextAccountStatuses.includes("active") ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!hasWriteAdmin}
          onClick={() => onOpenDialog({ kind: "account-status", cardAccount, targetStatus: "active" })}
        >
          Unblock account
        </Button>
      ) : null}
      {nextAccountStatuses.includes("closed") ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!hasWriteAdmin}
          onClick={() => onOpenDialog({ kind: "account-status", cardAccount, targetStatus: "closed" })}
        >
          Close
        </Button>
      ) : null}
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={!hasWriteAdmin || cardAccount.status !== "active"}
        onClick={() => onOpenDialog({ kind: "renew", cardAccountId: cardAccount.id })}
      >
        Renew card
      </Button>
      {card && card.status === "active" ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!hasWriteAdmin}
          onClick={() => onOpenDialog({ kind: "card-status", card, targetStatus: "blocked" })}
        >
          Block card
        </Button>
      ) : null}
      {card && card.status === "blocked" ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!hasWriteAdmin}
          onClick={() => onOpenDialog({ kind: "card-status", card, targetStatus: "active" })}
        >
          Unblock card
        </Button>
      ) : null}
    </div>
  );
}
