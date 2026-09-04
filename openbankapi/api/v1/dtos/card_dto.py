"""Card DTOs — masking is structural, not a runtime flag (Credit Cards Phase 1).

`CardMaskedDTO` is the default response shape everywhere except issue/renewal;
`CardIssuedDTO` is only ever returned by those two handlers. Two distinct
classes rather than one DTO with a boolean `masked` param: a boolean flag is a
leak waiting to happen (wrong default masks nothing), while separate types
make the unmasked path opt-in by construction and grep-able (design decision).
"""
from __future__ import annotations

import datetime as dt
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


def mask_card_number(card_number: str) -> str:
    return f"•••• •••• •••• {card_number[-4:]}"


class CardMaskedDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    card_account_id: UUID
    card_number: str
    expiration_date: dt.date
    status: str

    @field_serializer("card_number")
    def _mask(self, card_number: str) -> str:
        return mask_card_number(card_number)


class CardIssuedDTO(BaseModel):
    """Returned only by issue (`POST /card-accounts`) and renewal
    (`POST /card-accounts/{id}/cards`) — never by a plain read."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    card_account_id: UUID
    card_number: str
    expiration_date: dt.date
    status: str


class CardStatusUpdateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern="^(active|blocked|replaced|expired)$")
