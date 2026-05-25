from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.equipment import Distributor, EquipmentSource, EquipmentUnit


def _unit(db: Session, **kw) -> EquipmentUnit:
    defaults = {
        "manufacturer": "HAHA Vending",
        "product_name": "HAHA Mini 360C",
        "equipment_type": "smart_cooler",
        "status": "active",
    }
    defaults.update(kw)
    u = EquipmentUnit(**defaults)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _dist(db: Session, name: str = "Acme Supply") -> Distributor:
    d = Distributor(name=name)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def test_index_empty(client: TestClient) -> None:
    resp = client.get("/equipment/")
    assert resp.status_code == 200
    assert "Equipment Catalog" in resp.text


def test_index_groups_and_excludes_archived(client: TestClient, db: Session) -> None:
    _unit(db, product_name="Active Cooler", price_low=3000)
    _unit(db, product_name="Old Cooler", status="archived", price_low=1000)
    resp = client.get("/equipment/")
    assert "Active Cooler" in resp.text
    assert "Old Cooler" not in resp.text
    # Category section header is rendered from the type label.
    assert "AI Smart Cooler" in resp.text


def test_include_archived_shows_archived(client: TestClient, db: Session) -> None:
    _unit(db, product_name="Old Cooler", status="archived", price_low=1000)
    resp = client.get("/equipment/?include_archived=1")
    assert resp.status_code == 200
    assert "Old Cooler" in resp.text


def test_best_source_and_recompute(db: Session) -> None:
    u = _unit(db, price_low=9999)
    d1 = _dist(db, "AM Equipment")
    d2 = _dist(db, "VendGuys")
    db.add_all(
        [
            EquipmentSource(
                equipment_unit_id=u.id, distributor_id=d1.id, price_low=3095, price_high=3095
            ),
            EquipmentSource(
                equipment_unit_id=u.id, distributor_id=d2.id, price_low=3449, price_high=3449
            ),
        ]
    )
    db.commit()
    db.refresh(u)
    assert u.source_count == 2
    assert u.best_source.distributor.name == "AM Equipment"
    u.recompute_best_price()
    db.commit()
    assert u.price_low == 3095
    assert u.price_high == 3449


def test_add_source_recomputes_best_price(client: TestClient, db: Session) -> None:
    u = _unit(db, price_low=5000)
    d = _dist(db)
    resp = client.post(
        f"/equipment/{u.id}/sources", data={"distributor_id": str(d.id), "price_low": "3095"}
    )
    assert resp.status_code == 200
    db.refresh(u)
    assert any(s.price_low == 3095 for s in u.sources)
    assert u.price_low == 3095  # denormalized best price updated


def test_add_source_creates_new_distributor(client: TestClient, db: Session) -> None:
    u = _unit(db)
    resp = client.post(
        f"/equipment/{u.id}/sources",
        data={"new_distributor_name": "Fresh Supplier", "price_low": "2500"},
    )
    assert resp.status_code == 200
    db.refresh(u)
    assert any(s.distributor.name == "Fresh Supplier" for s in u.sources)


def test_delete_source(client: TestClient, db: Session) -> None:
    u = _unit(db)
    d = _dist(db)
    s = EquipmentSource(equipment_unit_id=u.id, distributor_id=d.id, price_low=3000)
    db.add(s)
    db.commit()
    db.refresh(s)
    resp = client.post(f"/equipment/{u.id}/sources/{s.id}/delete")
    assert resp.status_code == 200
    db.refresh(u)
    assert len(u.sources) == 0


def test_archive_and_unarchive(client: TestClient, db: Session) -> None:
    u = _unit(db, price_low=3000)
    client.post(f"/equipment/{u.id}/archive", follow_redirects=False)
    db.refresh(u)
    assert u.status == "archived"
    client.post(f"/equipment/{u.id}/unarchive", follow_redirects=False)
    db.refresh(u)
    assert u.status == "active"


def test_detail_shows_sourcing(client: TestClient, db: Session) -> None:
    u = _unit(db, price_low=3000)
    d = _dist(db)
    db.add(
        EquipmentSource(
            equipment_unit_id=u.id,
            distributor_id=d.id,
            price_low=3095,
            distributor_url="https://example.com/p",
        )
    )
    db.commit()
    resp = client.get(f"/equipment/{u.id}")
    assert resp.status_code == 200
    assert "Sourcing" in resp.text
    assert "Acme Supply" in resp.text


def test_distributors_tab(client: TestClient, db: Session) -> None:
    _dist(db)
    resp = client.get("/equipment/?tab=distributors")
    assert resp.status_code == 200
    assert "Acme Supply" in resp.text


def test_starting_price_label(client: TestClient, db: Session) -> None:
    _unit(
        db,
        manufacturer="Prime Micro Markets",
        product_name="Micro Market Starter Package",
        equipment_type="micro_market",
        price_low=4500,
        price_is_starting=True,
    )
    resp = client.get("/equipment/")
    assert resp.status_code == 200
    assert "Starting at" in resp.text
