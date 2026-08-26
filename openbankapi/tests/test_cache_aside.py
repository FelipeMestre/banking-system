"""Cache-aside behaviour (spec §8.2)."""
from __future__ import annotations

from openbankapi.tests.conftest import build
from openbankapi.tests.fakes import FakeCache


def _make_locacion(h):
    return h.client.post("/locaciones", json={"nombre": "Montevideo"}).json()["id"]


def test_a_miss_populates_the_cache(harness):
    locacion_id = _make_locacion(harness)

    harness.client.get(f"/locaciones/{locacion_id}")

    assert f"locacion:{locacion_id}" in harness.cache.store


def test_a_hit_does_not_reach_the_repository(harness):
    locacion_id = _make_locacion(harness)
    harness.client.get(f"/locaciones/{locacion_id}")
    loads_after_first = harness.locaciones.loads

    harness.client.get(f"/locaciones/{locacion_id}")

    assert harness.locaciones.loads == loads_after_first


def test_a_write_invalidates_the_entry(harness):
    locacion_id = _make_locacion(harness)
    harness.client.get(f"/locaciones/{locacion_id}")

    harness.client.put(f"/locaciones/{locacion_id}", json={"nombre": "Salto"})

    assert f"locacion:{locacion_id}" not in harness.cache.store
    assert harness.client.get(f"/locaciones/{locacion_id}").json()["nombre"] == "Salto"


def test_a_failing_cache_degrades_to_a_miss_not_a_500():
    """A cache that can take the API down is not a cache."""
    h = build(cache=FakeCache(failing=True))
    with h.client:
        locacion_id = _make_locacion(h)
        response = h.client.get(f"/locaciones/{locacion_id}")
    assert response.status_code == 200
    assert response.json()["nombre"] == "Montevideo"


def test_a_404_is_not_cached(harness):
    import uuid

    missing = uuid.uuid4()
    assert harness.client.get(f"/locaciones/{missing}").status_code == 404
    assert f"locacion:{missing}" not in harness.cache.store
