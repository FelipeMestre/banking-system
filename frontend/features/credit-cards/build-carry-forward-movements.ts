import type { CardMovement, CurrentCycleProjection } from "./types";

/**
 * Synthesizes movement-styled rows for the current cycle's carried-forward
 * balance and its interest. Neither is a real `card_movements` row — the
 * backend computes both live from the previous statement and never persists
 * them (spec: "never cached, never a Statement row until the cycle actually
 * closes") — but the movements list renders them identically to a real
 * movement so the customer sees everything contributing to what they owe
 * in one place, not just as header figures in the summary card above.
 *
 * Returns an empty array when nothing is overdue, matching the projection's
 * own convention: absent, never a zero-amount row.
 */
export function buildCarryForwardMovements(projection: CurrentCycleProjection): CardMovement[] {
  if (projection.overdue_from_previous_cycle === null) return [];

  const movements: CardMovement[] = [
    {
      id: "carried-balance",
      movement_type: "carried_balance",
      amount: projection.overdue_from_previous_cycle,
      currency: "USD",
      occurred_at: projection.period_start,
    },
  ];

  if (projection.interest_on_overdue !== null) {
    movements.push({
      id: "carried-balance-interest",
      movement_type: "interest",
      amount: projection.interest_on_overdue,
      currency: "USD",
      occurred_at: projection.period_start,
      description: "Interest on overdue balance",
    });
  }

  return movements;
}
