from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.inventory import InventoryLog, Product, ProductSource, Supplier


def _make_supplier(db: Session, **kwargs) -> Supplier:
    defaults = {"name": "Sysco Foods"}
    defaults.update(kwargs)
    s = Supplier(**defaults)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _make_product(db: Session, **kwargs) -> Product:
    defaults = {
        "sku": "WATER-16OZ",
        "name": "Water 16oz",
        "unit_cost": 0.50,
        "sell_price": 1.50,
        "on_hand_qty": 0,
        "is_active": True,
    }
    defaults.update(kwargs)
    p = Product(**defaults)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_inventory_index_empty(client: TestClient) -> None:
    resp = client.get("/inventory/")
    assert resp.status_code == 200
    assert "Inventory" in resp.text


def test_supplier_create(client: TestClient, db: Session) -> None:
    resp = client.post(
        "/inventory/suppliers",
        data={"name": "Sysco Foods", "supplier_type": "distributor"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert db.query(Supplier).count() == 1
    s = db.query(Supplier).first()
    assert s is not None
    assert s.name == "Sysco Foods"


def test_suppliers_index(client: TestClient, db: Session) -> None:
    _make_supplier(db)
    resp = client.get("/inventory/suppliers")
    assert resp.status_code == 200
    assert "Sysco Foods" in resp.text


def test_product_create(client: TestClient, db: Session) -> None:
    resp = client.post(
        "/inventory/",
        data={
            "sku": "COKE-12OZ",
            "name": "Coke 12oz",
            "unit_cost": "0.60",
            "sell_price": "2.00",
            "category": "Beverages",
            "par_level": "24",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert db.query(Product).count() == 1
    p = db.query(Product).first()
    assert p is not None
    assert p.sku == "COKE-12OZ"
    assert p.par_level == 24
    assert abs(p.sell_price - 2.00) < 0.001


def test_inventory_index_shows_products(client: TestClient, db: Session) -> None:
    _make_product(db)
    resp = client.get("/inventory/")
    assert resp.status_code == 200
    assert "Water 16oz" in resp.text


def test_inventory_category_filter(client: TestClient, db: Session) -> None:
    _make_product(db, sku="WATER-16OZ", name="Water 16oz", category="Beverages")
    _make_product(db, sku="CHIPS-1OZ", name="Chips 1oz", category="Snacks")
    resp = client.get("/inventory/?category=Beverages")
    assert resp.status_code == 200
    assert "Water 16oz" in resp.text
    assert "Chips 1oz" not in resp.text


def test_product_edit_form(client: TestClient, db: Session) -> None:
    p = _make_product(db)
    resp = client.get(f"/inventory/{p.id}/edit")
    assert resp.status_code == 200
    assert "Water 16oz" in resp.text


def test_product_update(client: TestClient, db: Session) -> None:
    p = _make_product(db)
    resp = client.post(
        f"/inventory/{p.id}",
        data={"name": "Water 20oz", "sku": "WATER-20OZ", "sell_price": "2.00", "unit_cost": "0.60"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    db.refresh(p)
    assert p.name == "Water 20oz"


def test_product_restock(client: TestClient, db: Session) -> None:
    p = _make_product(db, on_hand_qty=10)
    resp = client.post(
        f"/inventory/{p.id}/restock",
        data={"qty": "24", "notes": "Weekly restock"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    db.refresh(p)
    assert p.on_hand_qty == 34
    log = db.query(InventoryLog).first()
    assert log is not None
    assert log.qty_change == 24
    assert log.qty_after == 34
    assert log.log_type == "restock"


def test_product_deactivate(client: TestClient, db: Session) -> None:
    p = _make_product(db)
    resp = client.delete(f"/inventory/{p.id}")
    assert resp.status_code == 200
    db.refresh(p)
    assert p.is_active is False


def test_low_stock_filter(client: TestClient, db: Session) -> None:
    _make_product(db, sku="LOW-SKU", name="Low Stock Item", on_hand_qty=2, par_level=24)
    _make_product(db, sku="OK-SKU", name="OK Stock Item", on_hand_qty=50, par_level=24)
    resp = client.get("/inventory/?low_stock=true")
    assert resp.status_code == 200
    assert "Low Stock Item" in resp.text
    assert "OK Stock Item" not in resp.text


def test_product_404(client: TestClient) -> None:
    assert client.get("/inventory/9999/edit").status_code == 404


# ── Per-supplier sourcing (ProductSource) ──────────────────────────────────────


def test_product_create_with_case_pack_and_seasonal(client: TestClient, db: Session) -> None:
    resp = client.post(
        "/inventory/",
        data={
            "sku": "GUM-1",
            "name": "Gum",
            "sell_price": "1.50",
            "case_pack_qty": "12",
            "is_seasonal": "true",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    p = db.query(Product).filter(Product.sku == "GUM-1").first()
    assert p is not None
    assert p.case_pack_qty == 12
    assert p.is_seasonal is True


def test_effective_unit_cost_case_math(db: Session) -> None:
    s = _make_supplier(db)
    p = _make_product(db, case_pack_qty=24)
    src = ProductSource(product_id=p.id, supplier_id=s.id, case_price=18.96, case_pack_qty=24)
    db.add(src)
    db.commit()
    assert abs(src.effective_unit_cost - 0.79) < 0.001


def test_add_source_recomputes_best_cost(client: TestClient, db: Session) -> None:
    s = _make_supplier(db)
    p = _make_product(db, unit_cost=None, case_pack_qty=24)
    resp = client.post(
        f"/inventory/{p.id}/sources",
        data={"supplier_id": str(s.id), "case_price": "24.00", "case_pack_qty": "24"},
    )
    assert resp.status_code == 200
    db.refresh(p)
    assert p.source_count == 1
    assert abs(p.unit_cost - 1.00) < 0.001  # 24 / 24


def test_cheaper_source_becomes_best(client: TestClient, db: Session) -> None:
    s = _make_supplier(db, name="Sams")
    p = _make_product(db, unit_cost=None)
    client.post(f"/inventory/{p.id}/sources", data={"supplier_id": str(s.id), "unit_cost": "1.00"})
    client.post(
        f"/inventory/{p.id}/sources",
        data={"new_supplier_name": "Webstaurant", "unit_cost": "0.70"},
    )
    db.refresh(p)
    assert p.source_count == 2
    assert p.best_source.supplier.name == "Webstaurant"
    assert abs(p.unit_cost - 0.70) < 0.001


def test_toggle_preferred_source_is_exclusive(client: TestClient, db: Session) -> None:
    s = _make_supplier(db)
    p = _make_product(db)
    client.post(f"/inventory/{p.id}/sources", data={"supplier_id": str(s.id), "unit_cost": "1.00"})
    client.post(
        f"/inventory/{p.id}/sources",
        data={"new_supplier_name": "Other", "unit_cost": "1.20"},
    )
    db.refresh(p)
    first, second = p.sources[0], p.sources[1]
    client.post(f"/inventory/{p.id}/sources/{first.id}/preferred")
    client.post(f"/inventory/{p.id}/sources/{second.id}/preferred")
    db.refresh(p)
    preferred = [s for s in p.sources if s.is_preferred]
    assert len(preferred) == 1
    assert preferred[0].id == second.id


def test_delete_source_recomputes(client: TestClient, db: Session) -> None:
    s = _make_supplier(db)
    p = _make_product(db, unit_cost=None)
    client.post(f"/inventory/{p.id}/sources", data={"supplier_id": str(s.id), "unit_cost": "0.50"})
    db.refresh(p)
    src_id = p.sources[0].id
    resp = client.post(f"/inventory/{p.id}/sources/{src_id}/delete")
    assert resp.status_code == 200
    db.refresh(p)
    assert p.source_count == 0


def test_product_detail_page_renders(client: TestClient, db: Session) -> None:
    p = _make_product(db)
    resp = client.get(f"/inventory/{p.id}")
    assert resp.status_code == 200
    assert "Sourcing" in resp.text
    assert "Restock History" in resp.text


def test_save_source_from_comparison(client: TestClient, db: Session) -> None:
    p = _make_product(db, case_pack_qty=40)
    resp = client.post(
        f"/inventory/{p.id}/sources/from-comparison",
        data={
            "vendor_name": "Sam's Club",
            "vendor_key": "sams_club",
            "unit_price": "0.62",
            "case_price": "24.80",
            "case_qty": "40",
        },
    )
    assert resp.status_code == 200
    # Supplier auto-created from the comparator vendor
    sup = db.query(Supplier).filter(Supplier.name == "Sam's Club").first()
    assert sup is not None
    db.refresh(p)
    assert p.source_count == 1
    assert p.sources[0].origin == "comparator"
    assert abs(p.unit_cost - 0.62) < 0.001


def test_restock_run_groups_below_par(client: TestClient, db: Session) -> None:
    s = _make_supplier(db, name="BestSupplier")
    low = _make_product(db, sku="LOW", name="Low Item", par_level=24, on_hand_qty=4)
    _make_product(db, sku="OK", name="Stocked Item", par_level=10, on_hand_qty=50)
    client.post(
        f"/inventory/{low.id}/sources",
        data={"supplier_id": str(s.id), "unit_cost": "1.00"},
    )
    resp = client.get("/inventory/restock-run")
    assert resp.status_code == 200
    assert "Low Item" in resp.text
    assert "Stocked Item" not in resp.text  # at/above par excluded
    assert "BestSupplier" in resp.text


def test_restock_captures_cost(client: TestClient, db: Session) -> None:
    p = _make_product(db, unit_cost=0.55, on_hand_qty=0)
    client.post(f"/inventory/{p.id}/restock", data={"qty": "12"}, follow_redirects=False)
    log = db.query(InventoryLog).filter(InventoryLog.product_id == p.id).first()
    assert log is not None
    assert log.unit_cost_at_log is not None
    assert abs(log.unit_cost_at_log - 0.55) < 0.001


def test_supplier_create_with_account_number(client: TestClient, db: Session) -> None:
    resp = client.post(
        "/inventory/suppliers",
        data={"name": "Costco", "account_number": "MEMBER-123"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    s = db.query(Supplier).filter(Supplier.name == "Costco").first()
    assert s is not None
    assert s.account_number == "MEMBER-123"
