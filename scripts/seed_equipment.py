"""Seed the equipment_units table with initial manufacturer data.

Run once:  python scripts/seed_equipment.py

Data sourced from public manufacturer/reseller pages (May 2026):
  - HAHA Vending: GeniusVend.com + VendGuys.com
  - Micromart: micromart.com/pricing/smart-fridge
  - Cantaloupe: store.cantaloupe.com
  - 365 Retail Markets: 365retailmarkets.com + third-party spec sheets
  - SandStar: AVS Companies reseller page
  - WEIMI: weimivending.com B2B listing
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.database import Base, engine
from app.models.equipment import EquipmentUnit

Base.metadata.create_all(bind=engine)

UNITS: list[dict] = [

    # ── HAHA Vending (via GeniusVend / VendGuys) ─────────────────────────
    {
        "manufacturer": "HAHA Vending",
        "reseller": "GeniusVend / VendGuys",
        "product_name": "HAHA Mini 360C",
        "product_line": None,
        "equipment_type": "smart_cooler",
        "price_low": 3449,
        "price_high": 3499,
        "price_notes": "Includes free shipping. Processing fee 5.95% + $0.05/txn.",
        "monthly_fee": 40.0,
        "processing_fee_pct": 5.95,
        "warranty_years": 1,
        "warranty_notes": "1-year standard warranty",
        "extended_warranty_available": True,
        "extended_warranty_notes": "2-year +$350 / 4-year +$650",
        "height_in": 76.4,
        "width_in": 22.8,
        "depth_in": 30.0,
        "weight_lbs": 220.0,
        "capacity_cu_ft": 15.5,
        "capacity_units": 245,
        "power_watts": 380,
        "operating_temp_low": 32.0,
        "operating_temp_high": 50.0,
        "connectivity": "4G",
        "payment_types": "EMV, NFC, Apple Pay, Google Pay, credit/debit",
        "ai_features": True,
        "ai_accuracy_pct": 99.0,
        "certifications": None,
        "delivery_days_min": 1,
        "delivery_days_max": 5,
        "delivery_notes": "Free shipping included",
        "highlights": (
            "Entry-level AI smart cooler — ideal for smaller venues\n"
            "~245 bottle capacity in compact 22.8\" footprint\n"
            "Pure air cooling with heated anti-fog glass\n"
            "AI vision checkout — no RFID tags needed\n"
            "Extended warranty available"
        ),
        "product_url": "https://geniusvend.com/products/genius-vend-ai-powered-smart-mini-vending-cooler",
        "data_source": "https://vendguys.com/pages/haha-vending-feature-page",
        "data_confidence": "seeded",
    },
    {
        "manufacturer": "HAHA Vending",
        "reseller": "GeniusVend / VendGuys",
        "product_name": "HAHA PRO 542CT",
        "product_line": None,
        "equipment_type": "smart_cooler",
        "price_low": 4699,
        "price_high": 4700,
        "price_notes": "Includes free shipping. Processing fee 5.95% + $0.05/txn.",
        "monthly_fee": 40.0,
        "processing_fee_pct": 5.95,
        "warranty_years": 1,
        "warranty_notes": "1-year standard warranty",
        "extended_warranty_available": True,
        "extended_warranty_notes": "2-year +$350 / 4-year +$650",
        "height_in": 79.5,
        "width_in": 29.5,
        "depth_in": 29.1,
        "weight_lbs": 264.5,
        "capacity_cu_ft": 18.7,
        "capacity_units": 406,
        "power_watts": 380,
        "operating_temp_low": 32.0,
        "operating_temp_high": 50.0,
        "connectivity": "4G",
        "payment_types": "EMV, NFC, Apple Pay, Google Pay, credit/debit",
        "ai_features": True,
        "ai_accuracy_pct": 99.0,
        "certifications": None,
        "delivery_days_min": 1,
        "delivery_days_max": 5,
        "delivery_notes": "Free shipping included",
        "highlights": (
            "Mid-range workhorse — most popular HAHA model\n"
            "~406 unit capacity across multiple product types\n"
            "Handles drinks, snacks, fresh food, health products\n"
            "AI vision checkout in ~60 seconds\n"
            "Extended warranty available"
        ),
        "product_url": "https://geniusvend.com/products/prime-ai-vending-machine",
        "data_source": "https://vendguys.com/pages/haha-vending-feature-page",
        "data_confidence": "seeded",
    },
    {
        "manufacturer": "HAHA Vending",
        "reseller": "GeniusVend / VendGuys",
        "product_name": "HAHA Freezer 550CT",
        "product_line": None,
        "equipment_type": "freezer",
        "price_low": 4949,
        "price_high": 4999,
        "price_notes": "Includes free shipping. Processing fee 5.95% + $0.05/txn.",
        "monthly_fee": 40.0,
        "processing_fee_pct": 5.95,
        "warranty_years": 1,
        "warranty_notes": "1-year standard warranty",
        "extended_warranty_available": True,
        "extended_warranty_notes": "2-year +$350 / 4-year +$650",
        "height_in": 80.4,
        "width_in": 27.6,
        "depth_in": 35.8,
        "weight_lbs": 275.6,
        "capacity_cu_ft": 19.5,
        "capacity_units": 468,
        "power_watts": 500,
        "operating_temp_low": -7.6,
        "operating_temp_high": 14.0,
        "connectivity": "4G",
        "payment_types": "EMV, NFC, Apple Pay, Google Pay, credit/debit",
        "ai_features": True,
        "ai_accuracy_pct": 99.0,
        "certifications": None,
        "delivery_days_min": 1,
        "delivery_days_max": 5,
        "delivery_notes": "Free shipping included",
        "highlights": (
            "Deep-freeze AI cooler for ice cream, frozen meals, ice packs\n"
            "Operating temp -7.6°F to 14°F\n"
            "~468 unit capacity\n"
            "AI vision checkout — no staff needed\n"
            "Extended warranty available"
        ),
        "product_url": "https://geniusvend.com/products/genius-vend-ai-smart-vending-freezer",
        "data_source": "https://vendguys.com/pages/haha-vending-feature-page",
        "data_confidence": "seeded",
    },
    {
        "manufacturer": "HAHA Vending",
        "reseller": "GeniusVend / VendGuys",
        "product_name": "HAHA Ultra 1200CT",
        "product_line": None,
        "equipment_type": "smart_cooler",
        "price_low": 6999,
        "price_high": 7300,
        "price_notes": "Dual-door high-capacity unit. Includes free shipping.",
        "monthly_fee": 40.0,
        "processing_fee_pct": 5.95,
        "warranty_years": 1,
        "warranty_notes": "1-year standard warranty",
        "extended_warranty_available": True,
        "extended_warranty_notes": "2-year +$350 / 4-year +$650",
        "height_in": 79.5,
        "width_in": 53.9,
        "depth_in": 27.9,
        "weight_lbs": 410.0,
        "capacity_cu_ft": 39.0,
        "capacity_units": 828,
        "power_watts": 420,
        "operating_temp_low": 32.0,
        "operating_temp_high": 50.0,
        "connectivity": "4G",
        "payment_types": "EMV, NFC, Apple Pay, Google Pay, credit/debit",
        "ai_features": True,
        "ai_accuracy_pct": 99.0,
        "certifications": None,
        "delivery_days_min": 1,
        "delivery_days_max": 5,
        "delivery_notes": "Free shipping included",
        "highlights": (
            "Highest-capacity HAHA model — dual door, ~828 units\n"
            "Best suited for high-traffic venues (airports, gyms, hotels)\n"
            "39 cu ft storage across two temperature zones\n"
            "Efficient 420W draw for the capacity\n"
            "Extended warranty available"
        ),
        "product_url": "https://geniusvend.com/products/genius-vend-al-double-door-smart-cooler",
        "data_source": "https://vendguys.com/pages/haha-vending-feature-page",
        "data_confidence": "seeded",
    },

    # ── Micromart ──────────────────────────────────────────────────────────
    {
        "manufacturer": "Micromart",
        "reseller": None,
        "product_name": "Micromart Gen 5 Smart Fridge",
        "product_line": "Gen 5",
        "equipment_type": "smart_cooler",
        "price_low": 5995,
        "price_high": 6295,
        "price_notes": (
            "$6,295 single / $5,995 each for 3+. "
            "Lease: $230/month (36-month term). Platform fee $60/mo."
        ),
        "monthly_fee": 60.0,
        "processing_fee_pct": 4.1,
        "warranty_years": 3,
        "warranty_notes": (
            "3-year warranty on components; 5-year compressor warranty (parts & labor)"
        ),
        "extended_warranty_available": False,
        "extended_warranty_notes": None,
        "height_in": 79.6,
        "width_in": 30.5,
        "depth_in": 36.7,
        "weight_lbs": 350.0,
        "capacity_cu_ft": None,
        "capacity_units": 378,
        "power_watts": 408,
        "operating_temp_low": None,
        "operating_temp_high": None,
        "connectivity": "WiFi, Ethernet",
        "payment_types": "EMV, NFC, contactless, campus cards",
        "ai_features": True,
        "ai_accuracy_pct": None,
        "certifications": "NAMA, NSF, PCI DSS, UL",
        "delivery_days_min": None,
        "delivery_days_max": None,
        "delivery_notes": "Contact for lead time. Freight shipping.",
        "highlights": (
            "Best-in-class warranty: 3 years components + 5 years compressor\n"
            "Full NAMA, NSF, UL, and PCI DSS certifications\n"
            "4 high-speed AI cameras with anti-fog\n"
            "30 ePaper digital price tags (3-color, real-time updates)\n"
            "Volume pricing: $5,995 each for 3+ units\n"
            "Lease option: $230/month (36-month term)\n"
            "R290 refrigerant (eco-friendly)\n"
            "NAMA HealthLock certified door"
        ),
        "product_url": "https://www.micromart.com/pricing/smart-fridge",
        "data_source": "https://www.micromart.com/pricing/smart-fridge",
        "data_confidence": "seeded",
    },

    # ── Cantaloupe ─────────────────────────────────────────────────────────
    {
        "manufacturer": "Cantaloupe",
        "reseller": None,
        "product_name": "Smart Store 600 Single",
        "product_line": "SmartStores",
        "equipment_type": "smart_cooler",
        "price_low": 7495,
        "price_high": 7495,
        "price_notes": (
            "Subscription option available (monthly fee, no upfront cost). Accepts 110V or 220V."
        ),
        "monthly_fee": None,
        "processing_fee_pct": None,
        "warranty_years": None,
        "warranty_notes": "Contact Cantaloupe for warranty details",
        "extended_warranty_available": False,
        "extended_warranty_notes": None,
        "height_in": 72.0,
        "width_in": 32.0,
        "depth_in": 23.5,
        "weight_lbs": 300.0,
        "capacity_cu_ft": None,
        "capacity_units": 72,
        "power_watts": None,
        "operating_temp_low": None,
        "operating_temp_high": None,
        "connectivity": "4G, WiFi, Ethernet",
        "payment_types": "EMV, NFC, mobile wallet, campus cards, magstripe",
        "ai_features": True,
        "ai_accuracy_pct": 99.0,
        "certifications": None,
        "delivery_days_min": None,
        "delivery_days_max": None,
        "delivery_notes": "Up to 3-week onboarding period before shipment",
        "highlights": (
            "Cantaloupe SmartStore — established US micro market brand\n"
            "72 product slots / 6 shelves / 18 trays\n"
            "Shallower depth (23.5\") — fits tighter spaces\n"
            "~99% AI recognition accuracy\n"
            "Subscription model available — $0 upfront\n"
            "Supports campus card / closed-loop payment systems"
        ),
        "product_url": "https://store.cantaloupe.com/products/smart-store-600-single",
        "data_source": "https://store.cantaloupe.com/collections/coolers-and-freezers",
        "data_confidence": "seeded",
    },
    {
        "manufacturer": "Cantaloupe",
        "reseller": None,
        "product_name": "Smart Store 700 Single",
        "product_line": "SmartStores",
        "equipment_type": "smart_cooler",
        "price_low": 9495,
        "price_high": 9495,
        "price_notes": "Subscription option available. High-capacity flagship model.",
        "monthly_fee": None,
        "processing_fee_pct": None,
        "warranty_years": None,
        "warranty_notes": "Contact Cantaloupe for warranty details",
        "extended_warranty_available": False,
        "extended_warranty_notes": None,
        "height_in": 77.0,
        "width_in": 32.25,
        "depth_in": 31.0,
        "weight_lbs": 425.0,
        "capacity_cu_ft": None,
        "capacity_units": 94,
        "power_watts": None,
        "operating_temp_low": None,
        "operating_temp_high": None,
        "connectivity": "4G, WiFi, Ethernet",
        "payment_types": "EMV, NFC, mobile wallet, campus cards, magstripe",
        "ai_features": True,
        "ai_accuracy_pct": 99.0,
        "certifications": None,
        "delivery_days_min": None,
        "delivery_days_max": None,
        "delivery_notes": "Up to 3-week onboarding period before shipment",
        "highlights": (
            "Cantaloupe flagship — largest SmartStore model\n"
            "94 slots / 6 shelves / 24 trays\n"
            "Best for high-SKU variety locations\n"
            "Supports 110V or 220V power\n"
            "Subscription model available — $0 upfront"
        ),
        "product_url": "https://store.cantaloupe.com/products/smart-store-600-single-copy",
        "data_source": "https://store.cantaloupe.com/collections/coolers-and-freezers",
        "data_confidence": "seeded",
    },
    {
        "manufacturer": "Cantaloupe",
        "reseller": None,
        "product_name": "G319 Cooler",
        "product_line": "PicoCooler",
        "equipment_type": "smart_cooler",
        "price_low": 1795,
        "price_high": 4295,
        "price_notes": (
            "Price varies by configuration. Traditional cooler with Cantaloupe payment platform."
        ),
        "monthly_fee": None,
        "processing_fee_pct": None,
        "warranty_years": None,
        "warranty_notes": "Contact Cantaloupe for warranty details",
        "extended_warranty_available": False,
        "extended_warranty_notes": None,
        "height_in": 78.9,
        "width_in": 29.5,
        "depth_in": 27.9,
        "weight_lbs": None,
        "capacity_cu_ft": None,
        "capacity_units": None,
        "power_watts": None,
        "operating_temp_low": None,
        "operating_temp_high": None,
        "connectivity": "4G, WiFi, Ethernet",
        "payment_types": "EMV, NFC, mobile wallet, campus cards",
        "ai_features": False,
        "ai_accuracy_pct": None,
        "certifications": None,
        "delivery_days_min": None,
        "delivery_days_max": None,
        "delivery_notes": None,
        "highlights": (
            "Entry-level Cantaloupe cooler — lowest price point\n"
            "Traditional glass-door cooler with Cantaloupe payment system\n"
            "No AI vision — relies on traditional selection method\n"
            "Integrates with Cantaloupe's management platform"
        ),
        "product_url": "https://store.cantaloupe.com/products/g319-cooler",
        "data_source": "https://store.cantaloupe.com/collections/coolers-and-freezers",
        "data_confidence": "seeded",
    },

    # ── 365 Retail Markets ─────────────────────────────────────────────────
    {
        "manufacturer": "365 Retail Markets",
        "reseller": None,
        "product_name": "PicoCooler Vision",
        "product_line": "PicoCooler Vision",
        "equipment_type": "smart_cooler",
        "price_low": None,
        "price_high": None,
        "price_notes": "Contact 365 Retail Markets for pricing — not publicly listed",
        "monthly_fee": None,
        "processing_fee_pct": None,
        "warranty_years": None,
        "warranty_notes": "Contact 365 for warranty details",
        "extended_warranty_available": False,
        "extended_warranty_notes": None,
        "height_in": 78.75,
        "width_in": 30.0,
        "depth_in": 32.62,
        "weight_lbs": 340.0,
        "capacity_cu_ft": 23.41,
        "capacity_units": 300,
        "power_watts": None,
        "operating_temp_low": None,
        "operating_temp_high": None,
        "connectivity": "WiFi, Ethernet",
        "payment_types": "EMV, NFC, credit/debit",
        "ai_features": True,
        "ai_accuracy_pct": None,
        "certifications": None,
        "delivery_days_min": None,
        "delivery_days_max": None,
        "delivery_notes": "Contact 365 for lead time",
        "highlights": (
            "365 Retail Markets — largest micro market software company in the US\n"
            "5-camera AI/ML recognition system\n"
            "23.4 cu ft / ~300 x 20oz drinks capacity\n"
            "Min item size: 4\" wide × 4\" tall\n"
            "Integrates with 365Ops and ADM management platforms\n"
            "Pricing requires direct sales contact"
        ),
        "product_url": "https://365retailmarkets.com/picocooler-vision",
        "data_source": "https://365retailmarkets.com/picocooler-vision",
        "data_confidence": "seeded",
    },

    # ── SandStar ───────────────────────────────────────────────────────────
    {
        "manufacturer": "SandStar",
        "reseller": "AVS Companies",
        "product_name": "SandStar ARK",
        "product_line": "ARK Series",
        "equipment_type": "smart_cooler",
        "price_low": None,
        "price_high": None,
        "price_notes": "Contact SandStar or AVS Companies for pricing — demo required",
        "monthly_fee": None,
        "processing_fee_pct": None,
        "warranty_years": 5,
        "warranty_notes": "5-year warranty prominently marketed. Verify exact terms with SandStar.",
        "extended_warranty_available": False,
        "extended_warranty_notes": None,
        "height_in": 80.63,
        "width_in": 28.58,
        "depth_in": 31.93,
        "weight_lbs": 313.0,
        "capacity_cu_ft": None,
        "capacity_units": None,
        "power_watts": None,
        "operating_temp_low": None,
        "operating_temp_high": None,
        "connectivity": None,
        "payment_types": "EMV, NFC, contactless",
        "ai_features": True,
        "ai_accuracy_pct": None,
        "certifications": None,
        "delivery_days_min": None,
        "delivery_days_max": None,
        "delivery_notes": "Contact for delivery timeline",
        "highlights": (
            "Longest warranty in class — 5 years (vs. typical 1 year)\n"
            "No per-recognition fee — edge computing, subscription not required\n"
            "Proprietary computer vision with fast checkout\n"
            "Pricing and full specs require demo request\n"
            "Strong presence in Asian markets, expanding US footprint"
        ),
        "product_url": "https://avscompanies.com/product/sandstar-ark-ai-smart-cooler",
        "data_source": "https://avscompanies.com/product/sandstar-ark-ai-smart-cooler",
        "data_confidence": "seeded",
    },

    # ── WEIMI ───────────────────────────────────────────────────────────────
    {
        "manufacturer": "WEIMI",
        "reseller": None,
        "product_name": "WEIMI AI Vision Smart Fridge",
        "product_line": "AI Vision Series",
        "equipment_type": "smart_cooler",
        "price_low": 2698,
        "price_high": 3228,
        "price_notes": (
            "B2B/wholesale pricing from Guangzhou, China. Freight shipping from manufacturer."
        ),
        "monthly_fee": None,
        "processing_fee_pct": None,
        "warranty_years": 2,
        "warranty_notes": "18-month warranty with free spare parts (manufacturer stated)",
        "extended_warranty_available": False,
        "extended_warranty_notes": None,
        "height_in": None,
        "width_in": None,
        "depth_in": None,
        "weight_lbs": None,
        "capacity_cu_ft": None,
        "capacity_units": None,
        "power_watts": None,
        "operating_temp_low": None,
        "operating_temp_high": None,
        "connectivity": None,
        "payment_types": "EMV, NFC, QR code",
        "ai_features": True,
        "ai_accuracy_pct": None,
        "certifications": None,
        "delivery_days_min": None,
        "delivery_days_max": None,
        "delivery_notes": "International freight from Guangzhou, China. MOQ and lead time vary.",
        "highlights": (
            "Lowest price point among AI cooler manufacturers\n"
            "Direct from Chinese manufacturer — OEM/ODM available\n"
            "18-month warranty with free spare parts\n"
            "1,500 units/month production capacity\n"
            "Dimensions and detailed specs require inquiry\n"
            "Best for operators seeking lowest acquisition cost"
        ),
        "product_url": "https://www.weimivending.com/AI-camera-vending-machine-with-weight-sense-technology.html",
        "data_source": "https://www.weimivending.com/weimi-smart-fridge-vending-machine.html",
        "data_confidence": "seeded",
    },
    {
        "manufacturer": "WEIMI",
        "reseller": None,
        "product_name": "WEIMI Double Door Fresh Food",
        "product_line": "Fresh Food Series",
        "equipment_type": "smart_cooler",
        "price_low": 2179,
        "price_high": 2473,
        "price_notes": "B2B/wholesale pricing. Freight from Guangzhou, China.",
        "monthly_fee": None,
        "processing_fee_pct": None,
        "warranty_years": 2,
        "warranty_notes": "18-month warranty with free spare parts",
        "extended_warranty_available": False,
        "extended_warranty_notes": None,
        "height_in": None,
        "width_in": None,
        "depth_in": None,
        "weight_lbs": None,
        "capacity_cu_ft": None,
        "capacity_units": None,
        "power_watts": None,
        "operating_temp_low": None,
        "operating_temp_high": None,
        "connectivity": None,
        "payment_types": "EMV, NFC, QR code",
        "ai_features": True,
        "ai_accuracy_pct": None,
        "certifications": None,
        "delivery_days_min": None,
        "delivery_days_max": None,
        "delivery_notes": "International freight from Guangzhou, China",
        "highlights": (
            "Double-door design for fresh food / prepared meals\n"
            "Lowest acquisition cost for double-door format\n"
            "AI weight-sensor technology\n"
            "Good for fresh food, salads, meal-prep venues\n"
            "OEM/ODM customization available"
        ),
        "product_url": "https://www.weimivending.com/weimi-smart-fridge-vending-machine.html",
        "data_source": "https://www.weimivending.com/weimi-smart-fridge-vending-machine.html",
        "data_confidence": "seeded",
    },

    # ── Ambient / Snack Machines ───────────────────────────────────────────
    {
        "manufacturer": "Crane Merchandising Systems",
        "reseller": None,
        "product_name": "Merchant Combo 5591",
        "product_line": "Merchant",
        "equipment_type": "ambient",
        "price_low": 5000,
        "price_high": 7500,
        "price_notes": "Approximate; pricing varies by configuration and authorized distributor",
        "monthly_fee": None,
        "processing_fee_pct": None,
        "warranty_years": 1,
        "warranty_notes": "Standard 1-year warranty; extended options available via distributors",
        "extended_warranty_available": True,
        "extended_warranty_notes": None,
        "height_in": 72.0,
        "width_in": 38.6,
        "depth_in": 33.0,
        "weight_lbs": 540.0,
        "capacity_cu_ft": None,
        "capacity_units": 450,
        "power_watts": 600,
        "operating_temp_low": None,
        "operating_temp_high": None,
        "connectivity": "4G, WiFi, Ethernet",
        "payment_types": "EMV, NFC, credit/debit, campus cards",
        "ai_features": False,
        "ai_accuracy_pct": None,
        "certifications": "UL, NSF, NAMA",
        "delivery_days_min": None,
        "delivery_days_max": None,
        "delivery_notes": "Contact authorized Crane distributor for availability",
        "highlights": (
            "Industry-leading US manufacturer — most installed base in North America\n"
            "Combo format: snacks + cold/ambient beverages in one footprint\n"
            "Crane branded payment solutions integration\n"
            "Strong parts/service network across the US\n"
            "High capacity (~450 selections)"
        ),
        "product_url": "https://www.cranems.com/products/merchant-combo",
        "data_source": "https://www.cranems.com",
        "data_confidence": "seeded",
    },
    {
        "manufacturer": "AMS",
        "reseller": None,
        "product_name": "Sensit Touch 39",
        "product_line": "Sensit Touch",
        "equipment_type": "ambient",
        "price_low": 4500,
        "price_high": 6500,
        "price_notes": "Made in USA; pricing through authorized AMS dealers",
        "monthly_fee": None,
        "processing_fee_pct": None,
        "warranty_years": 2,
        "warranty_notes": "2-year parts warranty; made in Yakima, WA",
        "extended_warranty_available": True,
        "extended_warranty_notes": None,
        "height_in": 72.0,
        "width_in": 29.5,
        "depth_in": 35.0,
        "weight_lbs": 480.0,
        "capacity_cu_ft": None,
        "capacity_units": 390,
        "power_watts": 550,
        "operating_temp_low": None,
        "operating_temp_high": None,
        "connectivity": "4G, WiFi",
        "payment_types": "EMV, NFC, credit/debit",
        "ai_features": False,
        "ai_accuracy_pct": None,
        "certifications": "UL, NSF, NAMA, Made in USA",
        "delivery_days_min": None,
        "delivery_days_max": None,
        "delivery_notes": "Ships from Yakima, WA; lead time through dealers",
        "highlights": (
            "Made in the USA — Yakima, WA\n"
            "2-year parts warranty (longer than most competitors)\n"
            "Touchscreen interface with iCart inventory management\n"
            "Modular design — easy to service and reconfigure\n"
            "Strong reputation for reliability in break room deployments"
        ),
        "product_url": "https://ams-vending.com/vending-machines/sensit-touch",
        "data_source": "https://ams-vending.com",
        "data_confidence": "seeded",
    },
    {
        "manufacturer": "Jofemar",
        "reseller": None,
        "product_name": "Vision ES Plus",
        "product_line": "Vision",
        "equipment_type": "ambient",
        "price_low": None,
        "price_high": None,
        "price_notes": "Contact US distributor for pricing — manufactured in Spain",
        "monthly_fee": None,
        "processing_fee_pct": None,
        "warranty_years": 1,
        "warranty_notes": "Standard warranty; European build quality",
        "extended_warranty_available": False,
        "extended_warranty_notes": None,
        "height_in": 72.0,
        "width_in": 29.1,
        "depth_in": 33.5,
        "weight_lbs": 440.0,
        "capacity_cu_ft": None,
        "capacity_units": 360,
        "power_watts": 450,
        "operating_temp_low": None,
        "operating_temp_high": None,
        "connectivity": "4G, WiFi",
        "payment_types": "EMV, NFC, contactless",
        "ai_features": False,
        "ai_accuracy_pct": None,
        "certifications": "CE, UL",
        "delivery_days_min": None,
        "delivery_days_max": None,
        "delivery_notes": "Imported from Spain; lead times vary by US distributor",
        "highlights": (
            "European premium build quality — Jofemar is a leading Spanish manufacturer\n"
            "Narrow footprint (29.1\") suits tight locations\n"
            "Quiet compressor system\n"
            "Modular shelf system for flexible product mix\n"
            "Strong presence in hospitality and office micro markets"
        ),
        "product_url": "https://www.jofemar.com/en/vending-machines/vision-es-plus",
        "data_source": "https://www.jofemar.com",
        "data_confidence": "seeded",
    },

    # ── Micro Market Kiosks ────────────────────────────────────────────────
    {
        "manufacturer": "365 Retail Markets",
        "reseller": None,
        "product_name": "NanoMarket",
        "product_line": "NanoMarket",
        "equipment_type": "kiosk",
        "price_low": None,
        "price_high": None,
        "price_notes": "Contact 365 Retail Markets for pricing",
        "monthly_fee": None,
        "processing_fee_pct": None,
        "warranty_years": None,
        "warranty_notes": "Contact 365 for warranty details",
        "extended_warranty_available": False,
        "extended_warranty_notes": None,
        "height_in": None,
        "width_in": None,
        "depth_in": None,
        "weight_lbs": None,
        "capacity_cu_ft": None,
        "capacity_units": None,
        "power_watts": None,
        "operating_temp_low": None,
        "operating_temp_high": None,
        "connectivity": "WiFi, Ethernet, 4G",
        "payment_types": "EMV, NFC, campus cards, credit/debit",
        "ai_features": False,
        "ai_accuracy_pct": None,
        "certifications": "PCI DSS",
        "delivery_days_min": None,
        "delivery_days_max": None,
        "delivery_notes": "Contact 365 Retail Markets for lead time",
        "highlights": (
            "Compact self-checkout kiosk from the #1 US micro market software company\n"
            "Integrates directly with 365Ops and ADM management platforms\n"
            "Touchscreen with full product catalog and images\n"
            "Supports closed-loop campus card payments\n"
            "Ideal for offices and smaller venue micro market setups"
        ),
        "product_url": "https://365retailmarkets.com/nanomarket",
        "data_source": "https://365retailmarkets.com",
        "data_confidence": "seeded",
    },
    {
        "manufacturer": "Cantaloupe",
        "reseller": None,
        "product_name": "Cantaloupe Kiosk",
        "product_line": "Kiosk",
        "equipment_type": "kiosk",
        "price_low": None,
        "price_high": None,
        "price_notes": "Contact Cantaloupe for pricing",
        "monthly_fee": None,
        "processing_fee_pct": None,
        "warranty_years": None,
        "warranty_notes": "Contact Cantaloupe for warranty details",
        "extended_warranty_available": False,
        "extended_warranty_notes": None,
        "height_in": None,
        "width_in": None,
        "depth_in": None,
        "weight_lbs": None,
        "capacity_cu_ft": None,
        "capacity_units": None,
        "power_watts": None,
        "operating_temp_low": None,
        "operating_temp_high": None,
        "connectivity": "WiFi, Ethernet, 4G",
        "payment_types": "EMV, NFC, mobile wallet, campus cards",
        "ai_features": False,
        "ai_accuracy_pct": None,
        "certifications": "PCI DSS",
        "delivery_days_min": None,
        "delivery_days_max": None,
        "delivery_notes": "Contact Cantaloupe for lead time",
        "highlights": (
            "Cantaloupe self-checkout kiosk for full micro market setups\n"
            "Integrates with Cantaloupe's management and reporting platform\n"
            "Supports subscriptions, promotions, and loyalty programs\n"
            "Works alongside Cantaloupe SmartStore coolers for full-store solution"
        ),
        "product_url": "https://cantaloupe.com/products/kiosk",
        "data_source": "https://cantaloupe.com",
        "data_confidence": "seeded",
    },
    {
        "manufacturer": "Avanti Markets",
        "reseller": None,
        "product_name": "Avanti Self-Checkout Kiosk",
        "product_line": None,
        "equipment_type": "kiosk",
        "price_low": None,
        "price_high": None,
        "price_notes": "Contact Avanti Markets for pricing",
        "monthly_fee": None,
        "processing_fee_pct": None,
        "warranty_years": None,
        "warranty_notes": "Contact Avanti for warranty details",
        "extended_warranty_available": False,
        "extended_warranty_notes": None,
        "height_in": None,
        "width_in": None,
        "depth_in": None,
        "weight_lbs": None,
        "capacity_cu_ft": None,
        "capacity_units": None,
        "power_watts": None,
        "operating_temp_low": None,
        "operating_temp_high": None,
        "connectivity": "WiFi, Ethernet",
        "payment_types": "EMV, NFC, credit/debit, campus cards",
        "ai_features": False,
        "ai_accuracy_pct": None,
        "certifications": "PCI DSS",
        "delivery_days_min": None,
        "delivery_days_max": None,
        "delivery_notes": "Contact Avanti Markets for lead time",
        "highlights": (
            "Avanti Markets — one of the largest US micro market operators/providers\n"
            "Touchscreen self-checkout with full inventory management integration\n"
            "Supports health and wellness product programs\n"
            "Strong operator support network and back-office software"
        ),
        "product_url": "https://www.avantmarkets.com/kiosk",
        "data_source": "https://www.avantmarkets.com",
        "data_confidence": "seeded",
    },

    # ── Micro Market Complete Solutions ────────────────────────────────────
    {
        "manufacturer": "365 Retail Markets",
        "reseller": None,
        "product_name": "365 Micro Market",
        "product_line": "Core",
        "equipment_type": "micro_market",
        "price_low": None,
        "price_high": None,
        "price_notes": "Full micro market package — contact 365 for pricing",
        "monthly_fee": None,
        "processing_fee_pct": None,
        "warranty_years": None,
        "warranty_notes": "Contact 365 for warranty and support terms",
        "extended_warranty_available": False,
        "extended_warranty_notes": None,
        "height_in": None,
        "width_in": None,
        "depth_in": None,
        "weight_lbs": None,
        "capacity_cu_ft": None,
        "capacity_units": None,
        "power_watts": None,
        "operating_temp_low": None,
        "operating_temp_high": None,
        "connectivity": "WiFi, Ethernet, 4G",
        "payment_types": "EMV, NFC, mobile wallet, campus cards, credit/debit",
        "ai_features": False,
        "ai_accuracy_pct": None,
        "certifications": "PCI DSS, NAMA",
        "delivery_days_min": None,
        "delivery_days_max": None,
        "delivery_notes": "Contact 365 Retail Markets for deployment timeline",
        "highlights": (
            "Market leader — 365 Retail Markets powers more US micro markets than any competitor\n"
            "Full platform: kiosk + coolers + software + back-office reporting (365Ops)\n"
            "Supports fresh food, hot food, snacks, beverages in one location\n"
            "Advanced data analytics and remote management\n"
            "Integrates with HR/payroll systems for subsidized breakrooms\n"
            "PCI DSS certified payment processing"
        ),
        "product_url": "https://365retailmarkets.com/micro-market",
        "data_source": "https://365retailmarkets.com",
        "data_confidence": "seeded",
    },
    {
        "manufacturer": "Cantaloupe",
        "reseller": None,
        "product_name": "Cantaloupe Micro Market",
        "product_line": "Micro Market",
        "equipment_type": "micro_market",
        "price_low": None,
        "price_high": None,
        "price_notes": "Full micro market package — contact Cantaloupe for pricing",
        "monthly_fee": None,
        "processing_fee_pct": None,
        "warranty_years": None,
        "warranty_notes": "Contact Cantaloupe for support and warranty details",
        "extended_warranty_available": False,
        "extended_warranty_notes": None,
        "height_in": None,
        "width_in": None,
        "depth_in": None,
        "weight_lbs": None,
        "capacity_cu_ft": None,
        "capacity_units": None,
        "power_watts": None,
        "operating_temp_low": None,
        "operating_temp_high": None,
        "connectivity": "WiFi, Ethernet, 4G",
        "payment_types": "EMV, NFC, mobile wallet, campus cards, magstripe",
        "ai_features": False,
        "ai_accuracy_pct": None,
        "certifications": "PCI DSS",
        "delivery_days_min": None,
        "delivery_days_max": None,
        "delivery_notes": "Contact Cantaloupe for deployment timeline",
        "highlights": (
            "Cantaloupe (formerly USA Technologies) — major US micro market and vending platform\n"
            "Integrates SmartStore coolers + kiosk + software in one ecosystem\n"
            "Subscription and revenue-share models available\n"
            "Robust analytics via Cantaloupe management portal\n"
            "Supports loyalty, subsidies, and promotional programs"
        ),
        "product_url": "https://cantaloupe.com/micro-market",
        "data_source": "https://cantaloupe.com",
        "data_confidence": "seeded",
    },
    {
        "manufacturer": "Avanti Markets",
        "reseller": None,
        "product_name": "Avanti Micro Market",
        "product_line": None,
        "equipment_type": "micro_market",
        "price_low": None,
        "price_high": None,
        "price_notes": "Full micro market package — contact Avanti Markets for pricing",
        "monthly_fee": None,
        "processing_fee_pct": None,
        "warranty_years": None,
        "warranty_notes": "Contact Avanti for support and warranty details",
        "extended_warranty_available": False,
        "extended_warranty_notes": None,
        "height_in": None,
        "width_in": None,
        "depth_in": None,
        "weight_lbs": None,
        "capacity_cu_ft": None,
        "capacity_units": None,
        "power_watts": None,
        "operating_temp_low": None,
        "operating_temp_high": None,
        "connectivity": "WiFi, Ethernet",
        "payment_types": "EMV, NFC, credit/debit, campus cards",
        "ai_features": False,
        "ai_accuracy_pct": None,
        "certifications": "PCI DSS",
        "delivery_days_min": None,
        "delivery_days_max": None,
        "delivery_notes": "Contact Avanti Markets for deployment timeline",
        "highlights": (
            "One of the largest US micro market operators and technology providers\n"
            "Full-service market: kiosk + coolers + racks + software\n"
            "Strong focus on healthy and fresh food options\n"
            "Dedicated operator support and back-office management\n"
            "Wellness programs and subsidized breakroom options available"
        ),
        "product_url": "https://www.avantmarkets.com/micro-market",
        "data_source": "https://www.avantmarkets.com",
        "data_confidence": "seeded",
    },
]


def seed() -> None:
    with Session(engine) as db:
        added = 0
        skipped = 0
        for unit_data in UNITS:
            exists = (
                db.query(EquipmentUnit)
                .filter(
                    EquipmentUnit.manufacturer == unit_data["manufacturer"],
                    EquipmentUnit.product_name == unit_data["product_name"],
                )
                .first()
            )
            if exists:
                skipped += 1
                continue
            db.add(EquipmentUnit(**unit_data))
            added += 1
        db.commit()
    print(f"Equipment seed complete: {added} added, {skipped} already existed.")


if __name__ == "__main__":
    seed()
