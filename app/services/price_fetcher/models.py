from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PriceResult:
    vendor_key: str
    vendor_name: str
    vendor_type: str           # "online_wholesale" | "online_vending" | "local_wholesale" | "local_retail"
    product_name: str
    unit_price: float | None = None
    case_price: float | None = None
    case_qty: int | None = None
    unit_size: str | None = None
    url: str | None = None
    in_stock: bool | None = None
    min_order: str | None = None
    notes: str = ""
    source: str = "scrape"    # "api" | "scrape" | "ai_search"
    confidence: str = "medium" # "high" | "medium" | "low"

    def to_dict(self) -> dict:
        return {
            "vendor_key": self.vendor_key,
            "vendor_name": self.vendor_name,
            "vendor_type": self.vendor_type,
            "product_name": self.product_name,
            "unit_price": self.unit_price,
            "case_price": self.case_price,
            "case_qty": self.case_qty,
            "unit_size": self.unit_size,
            "url": self.url,
            "in_stock": self.in_stock,
            "min_order": self.min_order,
            "notes": self.notes,
            "source": self.source,
            "confidence": self.confidence,
        }


class FetchError(Exception):
    pass


VENDOR_META: dict[str, dict] = {
    "sams_club": {
        "label": "Sam's Club",
        "type": "local_wholesale",
        "icon": "bi-building",
        "color": "primary",
    },
    "walmart": {
        "label": "Walmart",
        "type": "local_retail",
        "icon": "bi-cart3",
        "color": "info",
    },
    "webstaurantstore": {
        "label": "WebstaurantStore",
        "type": "online_wholesale",
        "icon": "bi-globe",
        "color": "success",
    },
    "vendors_supply": {
        "label": "Vendors Supply",
        "type": "online_vending",
        "icon": "bi-box",
        "color": "warning",
    },
    "candy_machines": {
        "label": "CandyMachines",
        "type": "online_vending",
        "icon": "bi-star",
        "color": "danger",
    },
}
