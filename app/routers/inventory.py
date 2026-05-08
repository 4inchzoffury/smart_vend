from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.inventory import InventoryLog, Product, Supplier
from app.views import templates

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/suppliers", response_class=HTMLResponse)
def suppliers_index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    suppliers = db.query(Supplier).order_by(Supplier.name).all()
    return templates.TemplateResponse(
        request, "inventory/suppliers.html", {"active_nav": "inventory", "suppliers": suppliers}
    )


@router.post("/suppliers", response_class=HTMLResponse)
def supplier_create(
    name: str = Form(...),
    supplier_type: str = Form(""),
    contact_name: str = Form(""),
    contact_email: str = Form(""),
    contact_phone: str = Form(""),
    website: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    supplier = Supplier(
        name=name,
        supplier_type=supplier_type or None,
        contact_name=contact_name or None,
        contact_email=contact_email or None,
        contact_phone=contact_phone or None,
        website=website or None,
        notes=notes or None,
    )
    db.add(supplier)
    db.commit()
    return RedirectResponse(url="/inventory/suppliers", status_code=303)


@router.get("/", response_class=HTMLResponse)
def inventory_index(
    request: Request,
    category: str | None = None,
    supplier_id: int | None = None,
    low_stock: bool = False,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    query = db.query(Product).filter(Product.is_active.is_(True))
    if category:
        query = query.filter(Product.category == category)
    if supplier_id:
        query = query.filter(Product.primary_supplier_id == supplier_id)
    if low_stock:
        query = query.filter(
            Product.par_level.is_not(None), Product.on_hand_qty < Product.par_level
        )
    products = query.order_by(Product.category, Product.name).all()
    suppliers = db.query(Supplier).order_by(Supplier.name).all()
    categories = [r[0] for r in db.query(Product.category).distinct() if r[0]]
    return templates.TemplateResponse(
        request,
        "inventory/index.html",
        {
            "active_nav": "inventory",
            "products": products,
            "suppliers": suppliers,
            "categories": categories,
            "category_filter": category,
            "supplier_filter": supplier_id,
            "low_stock": low_stock,
        },
    )


@router.get("/new", response_class=HTMLResponse)
def product_new_form(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    suppliers = db.query(Supplier).order_by(Supplier.name).all()
    return templates.TemplateResponse(
        request, "inventory/_product_form.html", {"product": None, "suppliers": suppliers}
    )


@router.post("/", response_class=HTMLResponse)
def product_create(
    request: Request,
    sku: str = Form(...),
    name: str = Form(...),
    brand: str = Form(""),
    category: str = Form(""),
    unit_cost: str = Form(""),
    sell_price: str = Form(""),
    unit_size: str = Form(""),
    par_level: str = Form(""),
    primary_supplier_id: str = Form(""),
    restock_notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    product = Product(
        sku=sku,
        name=name,
        brand=brand or None,
        category=category or None,
        unit_cost=float(unit_cost) if unit_cost else None,
        sell_price=float(sell_price) if sell_price else None,
        unit_size=unit_size or None,
        par_level=int(par_level) if par_level else None,
        primary_supplier_id=int(primary_supplier_id) if primary_supplier_id else None,
        restock_notes=restock_notes or None,
    )
    db.add(product)
    db.commit()
    return RedirectResponse(url="/inventory/", status_code=303)


@router.get("/{product_id}/edit", response_class=HTMLResponse)
def product_edit_form(
    product_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    product = db.get(Product, product_id)
    if not product:
        return Response(status_code=404)
    suppliers = db.query(Supplier).order_by(Supplier.name).all()
    return templates.TemplateResponse(
        request, "inventory/_product_form.html", {"product": product, "suppliers": suppliers}
    )


@router.post("/{product_id}", response_class=HTMLResponse)
def product_update(
    product_id: int,
    name: str = Form(...),
    brand: str = Form(""),
    category: str = Form(""),
    unit_cost: str = Form(""),
    sell_price: str = Form(""),
    unit_size: str = Form(""),
    par_level: str = Form(""),
    primary_supplier_id: str = Form(""),
    restock_notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    product = db.get(Product, product_id)
    if not product:
        return Response(status_code=404)
    product.name = name
    product.brand = brand or None
    product.category = category or None
    product.unit_cost = float(unit_cost) if unit_cost else None
    product.sell_price = float(sell_price) if sell_price else None
    product.unit_size = unit_size or None
    product.par_level = int(par_level) if par_level else None
    product.primary_supplier_id = int(primary_supplier_id) if primary_supplier_id else None
    product.restock_notes = restock_notes or None
    db.commit()
    return RedirectResponse(url="/inventory/", status_code=303)


@router.post("/{product_id}/restock", response_class=HTMLResponse)
def product_restock(
    product_id: int,
    qty: int = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    product = db.get(Product, product_id)
    if not product:
        return Response(status_code=404)
    product.on_hand_qty += qty
    log = InventoryLog(
        product_id=product_id,
        log_type="restock",
        qty_change=qty,
        qty_after=product.on_hand_qty,
        notes=notes or None,
    )
    db.add(log)
    db.commit()
    return RedirectResponse(url="/inventory/", status_code=303)


@router.delete("/{product_id}", response_class=HTMLResponse)
def product_deactivate(product_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    product = db.get(Product, product_id)
    if product:
        product.is_active = False
        db.commit()
    return HTMLResponse(content="", status_code=200)
