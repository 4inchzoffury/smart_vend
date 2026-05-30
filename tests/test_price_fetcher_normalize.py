"""Unit tests for PriceResult.normalize() — backfills unit_price/case_price.

Wholesale fetchers tend to report case_price + case_qty without a unit_price;
retail fetchers report unit_price with no case fields. normalize() fills the
gaps so the comparator results table can show both sides for cross-vendor
comparison, and so the auto-save path persists internally-consistent
ProductSource rows. See app/services/price_fetcher/models.py.
"""

from __future__ import annotations

from app.services.price_fetcher.models import PriceResult


def _r(**kwargs) -> PriceResult:
    defaults = {
        "vendor_key": "x",
        "vendor_name": "X",
        "vendor_type": "online_wholesale",
        "product_name": "Sample",
    }
    defaults.update(kwargs)
    return PriceResult(**defaults)


def test_normalize_backfills_unit_from_case() -> None:
    """Wholesale: case_price=$24, case_qty=24 → unit_price=$1.00 (marked derived)."""
    r = _r(case_price=24.0, case_qty=24)
    r.normalize()
    assert r.unit_price == 1.0
    assert r.unit_price_derived is True
    assert r.case_price == 24.0  # unchanged
    assert r.case_price_derived is False


def test_normalize_backfills_case_from_unit_when_pack_known() -> None:
    """Retail: unit_price=$1.10, case_qty=None, fallback_case_pack=24 →
    case_price=$26.40 and case_qty=24 (both marked derived/filled)."""
    r = _r(unit_price=1.10)
    r.normalize(fallback_case_pack=24)
    assert r.case_price == 26.40
    assert r.case_qty == 24
    assert r.case_price_derived is True
    assert r.unit_price == 1.10  # unchanged
    assert r.unit_price_derived is False


def test_normalize_noop_when_neither_side_has_qty() -> None:
    """Without a case_qty AND without a fallback, math is impossible — no-op."""
    r = _r(unit_price=1.10)
    r.normalize()
    assert r.case_price is None
    assert r.case_price_derived is False


def test_normalize_does_not_overwrite_existing_values() -> None:
    """If both sides are already set, normalize leaves them alone (no double-write)."""
    r = _r(unit_price=1.10, case_price=24.0, case_qty=24)
    r.normalize()
    assert r.unit_price == 1.10
    assert r.case_price == 24.0
    assert r.unit_price_derived is False
    assert r.case_price_derived is False


def test_normalize_uses_explicit_case_qty_over_fallback() -> None:
    """When case_qty is on the row, it wins over fallback_case_pack."""
    r = _r(case_price=12.0, case_qty=12)
    r.normalize(fallback_case_pack=24)  # ignored — case_qty is set
    assert r.unit_price == 1.0  # 12 / 12, not 12 / 24


def test_is_empty_detects_no_information_rows() -> None:
    """A row with no price and no URL carries nothing — drop it."""
    empty = _r()
    assert empty.is_empty() is True

    has_price = _r(unit_price=1.10)
    assert has_price.is_empty() is False

    has_url = _r(url="https://example.com/x")
    assert has_url.is_empty() is False

    has_case = _r(case_price=24.0)
    assert has_case.is_empty() is False


def test_to_dict_round_trips_derived_flags() -> None:
    """JSON serialization preserves the derived-flag fields so the UI can
    render the 'calc' badge after the row hits AgentJob.draft_body."""
    r = _r(case_price=24.0, case_qty=24)
    r.normalize()
    d = r.to_dict()
    assert d["unit_price"] == 1.0
    assert d["unit_price_derived"] is True
    assert d["case_price_derived"] is False
