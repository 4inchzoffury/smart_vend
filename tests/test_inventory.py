from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.inventory import InventoryLog, Product, Supplier


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
