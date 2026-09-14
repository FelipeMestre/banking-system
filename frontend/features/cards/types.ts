/**
 * Admin-only card listing row from `GET /cards` (Credit Cards Phase 2 —
 * `CardAdminListItemDTO`). Deliberately unmasked (`card_number`): the
 * purchase-simulation dialog needs the real number to call
 * `POST /cards/{card_number}/purchases` on the admin's behalf.
 */
export interface CardListItem {
  id: string;
  card_account_id: string;
  card_number: string;
  status: string;
  customer_name: string;
}

/**
 * Mirrors `PurchaseRequestDTO` (openbankapi/api/v1/dtos/purchase_dto.py)
 * field for field. There is no `merchant_name` on the real DTO — only
 * `card_id`, `amount`, `currency`, `description`, `installments` — and
 * nothing here computes or sends exchange-rate data; the gateway resolves
 * currency conversion itself.
 */
export interface PurchaseRequestBody {
  card_id: string;
  amount: string;
  currency: string;
  description?: string;
  installments: number;
}

export interface PurchaseAccepted {
  request_id: string;
  status: string;
}

/**
 * A verdict from the card service's Flink job, via the WebSocket or GET
 * `.../status` (`PurchaseStatusDTO`, openbankapi/api/v1/dtos/purchase_dto.py).
 * `_status()` (card-service/domain.py) emits `reason` only on decline (e.g.
 * `"insufficient_credit"`), never `decline_reason`.
 */
export interface PurchaseStatus {
  request_id: string;
  status: "pending" | "approved" | "declined";
  reason?: string;
  ts?: string;
}

/**
 * `POST /admin/batch/monthly-close` result (`MonthlyCloseRunResultDTO`,
 * openbankapi/api/v1/dtos/batch_dto.py). Manually runs the same
 * `check_and_close_if_due` the hourly `batch-worker` cron calls, using the
 * gateway's real current date — never a date the frontend supplies.
 */
export interface MonthlyCloseRunResult {
  closed_count: number;
  statement_ids: string[];
  card_account_ids: string[];
}

/**
 * `POST /admin/batch/due-date-check` result (`DueDateCheckRunResultDTO`,
 * openbankapi/api/v1/dtos/batch_dto.py). Manually runs the same
 * `StatementService.run_due_date_check` the hourly `batch-worker` cron calls.
 */
export interface DueDateCheckRunResult {
  finalized_count: number;
  late_fees_applied_count: number;
}
