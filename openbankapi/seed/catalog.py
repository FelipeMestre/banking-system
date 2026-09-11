"""Demo purchase catalogue for seed (pure-event)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PurchaseSpec:
    amount_usd: float
    amount_cents: int
    installments: int
    description: str


CYCLE_PURCHASE_COUNT = 50

_MERCHANTS: tuple[str, ...] = (
    "Coffee House", "Grocery Market", "Pharmacy", "Book Store", "Restaurant",
    "Gas Station", "Clothing Retailer", "Hardware Store", "Streaming Service",
    "Electronics Store", "Bakery", "Rideshare", "Gym Membership", "Pet Store",
    "Movie Theater", "Furniture Shop", "Florist", "Bike Shop", "Toy Store",
    "Bookshop Cafe",
)


def purchases_for_cycle(cycle_index: int, card_index: int = 0) -> list[PurchaseSpec]:
    """50 single-charge purchases for one billing cycle.

    Amounts cycle $5.00-$60.00 (deterministic, no randomness — reproducible
    seed data) so 50 of them stay well under even the smaller $5000 card
    limit. `installments` is always 1: cycle math here is about testing
    period rollover and interest carry, not the separate installment-billing
    path already covered elsewhere.

    `card_index` shifts the merchant/amount pattern per card (still fully
    deterministic, no randomness) so two demo card accounts don't end up with
    byte-identical purchase histories — `card_index=0` reproduces the
    original single-card sequence exactly, so this is additive, not a
    behavior change for the first card.
    """
    purchases = []
    for i in range(CYCLE_PURCHASE_COUNT):
        merchant = _MERCHANTS[(i + card_index * 7) % len(_MERCHANTS)]
        amount = Decimal("5.00") + Decimal((i + card_index * 3) % 12) * Decimal("5.00")
        purchases.append(
            PurchaseSpec(float(amount), int(amount * 100), 1, f"{merchant} (cycle {cycle_index + 1}, #{i + 1})")
        )
    return purchases
