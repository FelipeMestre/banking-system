/** The shape every paged list endpoint returns (limit/offset, per the API's own convention). */
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

/** FX conversion detail, present only when a request's `currency` differs
 * from the account's own currency (the backend omits it entirely otherwise,
 * via `response_model_exclude_none`). Shared by every admin cash-movement
 * endpoint that can apply a conversion (deposits, withdrawals, ...). */
export interface AppliedRate {
  pair: string;
  mid_rate: number;
  applied_rate: number;
  margin: number;
  direction: string;
  source_ts: string;
}
