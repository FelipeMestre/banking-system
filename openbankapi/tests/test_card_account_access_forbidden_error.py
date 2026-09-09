"""RED/GREEN for Group C1 (`credit-cards-frontend-page`): `CardAccountAccessForbiddenError`
maps to 403, modeled on `AccountAccessForbiddenError`."""
from __future__ import annotations

import uuid

from openbankapi.api.v1.services.error_handlers import status_for
from openbankapi.domain.exceptions import CardAccountAccessForbiddenError, CardAccountNotFoundError


def test_card_account_access_forbidden_maps_to_403():
    assert status_for(CardAccountAccessForbiddenError(uuid.uuid4())) == 403


def test_card_account_access_forbidden_is_distinct_from_not_found():
    card_account_id = uuid.uuid4()
    assert status_for(CardAccountNotFoundError(card_account_id)) == 404
    assert status_for(CardAccountAccessForbiddenError(card_account_id)) == 403
