"""Account endpoints — including the rule the whole architecture rests on."""
from __future__ import annotations

import uuid

import pytest

from openbankapi.controllers.dtos.cuenta_dto import CuentaUpdateDTO
from openbankapi.tests.conftest import build
from openbankapi.tests.fakes import FakeCuentaRepository


def _create(wired):
    return wired.client.post(
        "/cuentas",
        json={"moneda": "USD", "cliente_id": str(wired.cliente_id),
              "sucursal_id": str(wired.sucursal_id)},
    )


# --- spec §11.1 -------------------------------------------------------------


def test_account_creation_returns_16_digits_and_zero_balance(wired):
    response = _create(wired)
    assert response.status_code == 201
    body = response.json()
    assert len(body["numero_cuenta"]) == 16
    assert body["numero_cuenta"].isdigit()
    assert body["saldo"] == 0
    assert body["estado"] == "activa"


def test_the_client_cannot_choose_the_account_number(wired):
    """It is the Kafka partition key: correct by construction, not by validation."""
    response = wired.client.post(
        "/cuentas",
        json={"moneda": "USD", "cliente_id": str(wired.cliente_id),
              "sucursal_id": str(wired.sucursal_id),
              "numero_cuenta": "9999999999999999"},
    )
    assert response.status_code == 422


def test_a_generated_number_collision_never_surfaces_a_500():
    cliente_id, sucursal_id = uuid.uuid4(), uuid.uuid4()
    cuentas = FakeCuentaRepository(known_clientes={cliente_id}, known_sucursales={sucursal_id},
                                   collide_times=2)
    h = build(cuentas=cuentas)
    with h.client:
        response = h.client.post(
            "/cuentas",
            json={"moneda": "USD", "cliente_id": str(cliente_id), "sucursal_id": str(sucursal_id)},
        )
    assert response.status_code == 201
    assert cuentas.attempts == 3, "should have retried past both collisions"


# --- spec §11.3: saldo is not writable --------------------------------------


def test_the_update_dto_has_no_saldo_field_at_all():
    """Structural, not behavioural: the field must not exist to be set."""
    assert "saldo" not in CuentaUpdateDTO.model_fields


def test_sending_saldo_in_an_update_is_rejected(wired):
    numero = _create(wired).json()["numero_cuenta"]

    response = wired.client.put(f"/cuentas/{numero}", json={"saldo": 999999})

    assert response.status_code == 422
    assert wired.client.get(f"/cuentas/{numero}").json()["saldo"] == 0


def test_a_legitimate_update_still_leaves_the_balance_alone(wired):
    numero = _create(wired).json()["numero_cuenta"]
    await_balance = wired.cuentas.rows[numero].saldo

    response = wired.client.put(f"/cuentas/{numero}", json={"estado": "bloqueada"})

    assert response.status_code == 200
    assert response.json()["estado"] == "bloqueada"
    assert response.json()["saldo"] == await_balance


# --- spec §11.4: referential integrity --------------------------------------


def test_a_nonexistent_cliente_is_a_clean_4xx_not_a_db_error(wired):
    response = wired.client.post(
        "/cuentas",
        json={"moneda": "USD", "cliente_id": str(uuid.uuid4()),
              "sucursal_id": str(wired.sucursal_id)},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ReferencedEntityNotFoundError"


def test_a_nonexistent_sucursal_is_a_clean_4xx(wired):
    response = wired.client.post(
        "/cuentas",
        json={"moneda": "USD", "cliente_id": str(wired.cliente_id),
              "sucursal_id": str(uuid.uuid4())},
    )
    assert response.status_code == 422


# --- soft delete ------------------------------------------------------------


def test_deleting_an_account_closes_it_rather_than_removing_it(wired):
    numero = _create(wired).json()["numero_cuenta"]

    assert wired.client.delete(f"/cuentas/{numero}").json()["estado"] == "cerrada"
    assert wired.client.get(f"/cuentas/{numero}").status_code == 200


def test_an_unknown_account_is_404(wired):
    assert wired.client.get("/cuentas/1111111111111111").status_code == 404
