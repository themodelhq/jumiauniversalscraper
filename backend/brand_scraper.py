"""
Brand Website Search Pipeline
Extracted from scraper_gui.py — no GUI dependencies.
Provides: search_brand_website(query) -> dict
"""

import random, time as _time
import os, re, json, urllib.parse

#!/usr/bin/env python3
"""
Universal Product Scraper - Enhanced GUI Application v4.1
Supports: Amazon, Noon, GSM Arena, Brand Website Search & any website
Outputs to: BOBTemplate (CSV) or VendorCenterTemplate (XLSX)
Features: HTML descriptions + short descriptions, HD images in HTML, GTIN extraction
"""

import threading
import os
import csv
import time
import shutil

from product_scraper import scrape_product, detect_website
# ── Template paths (place alongside this script) ─────────────────────────────


# ════════════════════════════════════════════════════════════════════════════
# Case-insensitive result normaliser
# ════════════════════════════════════════════════════════════════════════════

def _normalise(result: dict) -> dict:
    """
    Return a copy of *result* where every key is normalised so lookups work
    regardless of what capitalisation product_scraper.py uses.
    Strategy: build a lowercase-key -> canonical-key map and merge duplicates
    so that e.g. both 'description' and 'Description' become 'Description'.
    Also promotes common alternate key names to the canonical names the
    rest of this file expects.
    """
    # Canonical key name for each lowercase variant
    _CANON = {
        'product name':           'Product Name',
        'title':                  'Product Name',
        'name':                   'Product Name',
        'brand':                  'Brand',
        'manufacturer':           'Brand',
        'price':                  'Price',
        'currency':               'Currency',
        'category':               'Category',
        'key features':           'Key Features',
        'features':               'Key Features',
        'highlights':             'Key Features',
        'about this item':        'About This Item',
        'about':                  'About This Item',
        'tech & additional info': 'Tech & Additional Info',
        'specifications':         'Tech & Additional Info',
        'specs':                  'Tech & Additional Info',
        'product details':        'Tech & Additional Info',
        'technical details':      'Tech & Additional Info',
        'description':            'Description',
        'product description':    'Description',
        'overview':               'Description',
        'rating':                 'Rating',
        'reviews count':          'Reviews Count',
        'review count':           'Reviews Count',
        'sku':                    'SKU',
        'model':                  'SKU',
        'model number':           'SKU',
        'model no':               'SKU',
        'item model number':      'SKU',
        'gtin':                   'GTIN',
        'ean':                    'GTIN',
        'upc':                    'GTIN',
        'barcode':                'GTIN',
        'gtin_barcode':           'GTIN',
        'availability':           'Availability',
        'stock':                  'Availability',
        'images':                 'Images',
        'image':                  'Images',
        'image urls':             'Images',
        'image url':              'Images',
        'photos':                 'Images',
        'url':                    'URL',
        'link':                   'URL',
        'website':                'Website',
        'source':                 'Website',
        'weight':                 'Weight',
        'product weight':         'Weight',
        'dimensions':             'Dimensions',
        'product measures':       'Dimensions',
        'size':                   'Dimensions',
        'warranty':               'Warranty',
        'product warranty':       'Warranty',
        'colour':                 'Colour',
        'color':                  'Colour',
        'product line':           'Product Line',
        'search query':           'Search Query',
        'error':                  'Error',
    }
    out = {}
    for k, v in result.items():
        canon = _CANON.get(k.lower().strip(), k)  # keep original if no mapping
        if canon not in out or (v and not out[canon]):  # prefer non-empty
            out[canon] = v
    return out


# ════════════════════════════════════════════════════════════════════════════
# HTML builders
# ════════════════════════════════════════════════════════════════════════════

def _strip_brand_from_name(name: str, brand: str) -> str:
    """Remove leading brand name from product name (case-insensitive)."""
    if brand and name.lower().startswith(brand.lower()):
        stripped = name[len(brand):].lstrip(" -\u2013\u2014_,")
        return stripped if stripped else name
    return name


def build_html_description(result: dict) -> str:
    """
    Build a promotional HTML description:
      - Product heading and brand
      - HD product images embedded inline (feature/story images for Samsung,
        gallery images for other brands)
      - Key features as a styled bullet list (specs for Samsung)
      - Full specifications as a two-column table
    """
    name        = result.get("Product Name", "")
    brand       = result.get("Brand", "")
    clean_name  = _strip_brand_from_name(name, brand)
    key_feats   = (result.get("Key Features", "")
                  or result.get("About This Item", "")
                  or result.get("Features", "")
                  or result.get("Highlights", ""))
    tech_info   = (result.get("Tech & Additional Info", "")
                  or result.get("Specifications", "")
                  or result.get("Product Details", "")
                  or result.get("Product Attribute", ""))
    desc_plain  = result.get("Description", "")
    images_raw  = result.get("Images", "")

    # ── Samsung: Description field holds pre-built feature HTML ─────────────
    # _postprocess_samsung builds a rich feature-blocks HTML and stores it in
    # Description.  Use it directly instead of the generic spec-table layout.
    _is_samsung = "samsung" in brand.lower() if brand else False
    if _is_samsung and desc_plain.strip().startswith("<div"):
        # Description is already the complete styled feature HTML
        return (
            '<div style="font-family:Arial,sans-serif;max-width:820px;margin:0 auto;padding:16px;">\n'
            f'  <h2 style="font-size:18px;color:#1e293b;margin-bottom:4px;">{clean_name}</h2>\n'
            f'  <p style="font-size:13px;color:#6b7280;margin-top:0;">Brand: <strong>{brand}</strong></p>\n'
            + desc_plain.strip() +
            '\n</div>'
        ).strip()

    # Prefer promotional images from the brand's description section;
    # fall back to the generic Images field if none found there.
    import re as _re
    desc_img_urls = _re.findall(
        r'https?://\S+\.(?:jpg|jpeg|png|webp|gif)(?:\?\S*)?',
        desc_plain, flags=_re.IGNORECASE)
    if desc_img_urls:
        img_urls = list(dict.fromkeys([u.strip() for u in desc_img_urls]))[:6]
    else:
        img_urls = [u.strip() for u in images_raw.split(",") if u.strip()][:6]

    # ── Images block ─────────────────────────────────────────────────────────
    img_html = ""
    if img_urls:
        imgs_inner = "\n".join(
            f'  <img src="{u}" alt="{name}" '
            f'style="max-width:100%;height:auto;display:block;'
            f'border:1px solid #e5e7eb;border-radius:8px;background:#fff;" />'
            for u in img_urls
        )
        img_html = (
            '\n<div style="display:flex;flex-wrap:wrap;gap:14px;'
            'justify-content:center;margin:20px 0;">\n'
            + imgs_inner + '\n</div>\n'
        )

    # ── Feature / Key features section ───────────────────────────────────────
    feats_html = ""
    if key_feats:
        lines = [l.strip() for l in key_feats.replace(";", "\n").splitlines() if l.strip()]
        if lines:
            li_items = "\n".join(f"  <li>{l}</li>" for l in lines)
            feats_html = (
                '\n<div style="margin:18px 0;">\n'
                '  <h3 style="font-family:Arial,sans-serif;font-size:15px;'
                'color:#1e293b;margin-bottom:8px;">Key Features</h3>\n'
                '  <ul style="font-family:Arial,sans-serif;font-size:13px;'
                'color:#374151;line-height:1.8;padding-left:22px;margin:0;">\n'
                + li_items + '\n  </ul>\n</div>\n'
            )

    # ── Specifications table ─────────────────────────────────────────────────
    specs_html = ""
    # For Samsung: Key Features IS the specs — don't duplicate in spec table
    _is_samsung = "samsung" in brand.lower() if brand else False
    spec_source = "" if _is_samsung else (tech_info or desc_plain)
    if spec_source:
        rows = []
        for line in spec_source.replace(";", "\n").splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                label, _, value = line.partition(":")
                rows.append((label.strip(), value.strip()))
            else:
                rows.append(("", line))
        if rows:
            tr_rows = ""
            for idx, (label, value) in enumerate(rows):
                bg = "#f9fafb" if idx % 2 == 0 else "#ffffff"
                label_td = (
                    f'<td style="font-weight:600;color:#374151;padding:7px 12px;'
                    f'white-space:nowrap;width:38%;'
                    f'border-bottom:1px solid #e5e7eb;">{label}</td>'
                ) if label else (
                    '<td style="padding:7px 12px;border-bottom:1px solid #e5e7eb;"></td>'
                )
                value_td = (
                    f'<td style="color:#4b5563;padding:7px 12px;'
                    f'border-bottom:1px solid #e5e7eb;">{value}</td>'
                )
                tr_rows += f'<tr style="background:{bg};">{label_td}{value_td}</tr>\n'

            specs_html = (
                '\n<div style="margin:18px 0;">\n'
                '  <h3 style="font-family:Arial,sans-serif;font-size:15px;'
                'color:#1e293b;margin-bottom:8px;">Specifications</h3>\n'
                '  <table style="width:100%;border-collapse:collapse;'
                'font-family:Arial,sans-serif;font-size:13px;'
                'border:1px solid #e5e7eb;border-radius:6px;overflow:hidden;">\n'
                + tr_rows
                + '  </table>\n</div>\n'
            )

    html = (
        '<div style="font-family:Arial,sans-serif;max-width:820px;margin:0 auto;padding:16px;">\n'
        f'  <h2 style="font-size:18px;color:#1e293b;margin-bottom:4px;">{clean_name}</h2>\n'
        f'  <p style="font-size:13px;color:#6b7280;margin-top:0;">Brand: <strong>{brand}</strong></p>\n'
        + img_html + feats_html + specs_html +
        '</div>'
    )
    return html.strip()


def build_html_short_description(result: dict) -> str:
    """
    Compact HTML bullet list of key features for the short_description column.
    Falls back to a plain text excerpt if no features are available.
    """
    key_feats = (result.get("Key Features", "")
                 or result.get("About This Item", "")
                 or result.get("Features", "")
                 or result.get("Highlights", ""))
    if not key_feats:
        plain = (result.get("Description", "")
                 or result.get("Tech & Additional Info", "")
                 or result.get("Product Attribute", ""))
        if not plain:
            return ""
        # Wrap in HTML paragraph so the column always contains HTML, not raw text
        import html as _html_mod
        escaped = _html_mod.escape(plain[:500])
        return (
            f'<p style="font-family:Arial,sans-serif;font-size:13px;' 
            f'color:#374151;line-height:1.7;margin:0;">{escaped}</p>'
        )

    lines = [l.strip() for l in key_feats.replace(";", "\n").splitlines() if l.strip()]
    if not lines:
        return key_feats

    li_items = "\n".join(f"  <li>{l}</li>" for l in lines)
    return (
        '<ul style="font-family:Arial,sans-serif;font-size:13px;'
        'color:#374151;line-height:1.8;padding-left:22px;margin:0;">\n'
        + li_items + '\n</ul>'
    )


# ════════════════════════════════════════════════════════════════════════════
# GTIN extractor
# ════════════════════════════════════════════════════════════════════════════

def _validate_gtin_str(v: str) -> str:
    """
    Return v (digits only) if it is a structurally valid EAN-8/12/13/14.
    For EAN-13 also verifies the checksum digit.
    Rejects placeholder GTINs (e.g. Samsung's 00001000000000).
    Returns empty string if invalid.
    """
    import re
    v = re.sub(r'[^\d]', '', str(v)).strip()
    if not v or len(v) not in (8, 12, 13, 14):
        return ""
    # Reject placeholder/dummy values: all-zeros, near-zero, or >=80% zeros
    if int(v) < 1000 or v.count('0') >= len(v) * 0.8:
        return ""
    # EAN-13 checksum validation (GS1 standard)
    if len(v) == 13:
        d = [int(x) for x in v]
        chk = (10 - sum(x * (1 if i % 2 == 0 else 3)
                        for i, x in enumerate(d[:-1])) % 10) % 10
        if chk != d[-1]:
            return ""
    return v


def _extract_gtin(r: dict) -> str:
    """
    Best-effort GTIN/EAN/UPC/Barcode extraction from a scraped result dict.
    Every candidate is validated (digit-only, correct length, EAN-13 checksum).
    """
    import re

    # 1. Direct field checks — validate each value before accepting
    for key in ("GTIN", "gtin", "EAN", "ean", "UPC", "upc",
                "Barcode", "barcode", "GTIN_Barcode", "gtin_barcode",
                "gtin13", "gtin14", "gtin12", "gtin8"):
        val = _validate_gtin_str(r.get(key, "") or "")
        if val:
            return val

    # 2. Labelled pattern scan across text fields — validate each hit
    label_pattern = re.compile(
        r'(?:GTIN|EAN|EAN[-\s]?13|UPC|Barcode|Barcode\s*No|'
        r'GTIN[-\s]?Code|EAN[-\s]?Code|UPC[-\s]?Code)'
        r'[^\d]{0,15}(\d{8,14})',
        re.IGNORECASE
    )
    for key in ("Tech & Additional Info", "About This Item",
                "Description", "Key Features", "Product Attribute"):
        text = r.get(key, "") or ""
        for m in label_pattern.finditer(text):
            val = _validate_gtin_str(m.group(1))
            if val:
                return val

    return ""


# ════════════════════════════════════════════════════════════════════════════
# Colour extractor
# ════════════════════════════════════════════════════════════════════════════

def _extract_colour(r: dict) -> str:
    for key in ("Colour", "Color", "color", "colour"):
        if r.get(key):
            return r[key]
    name = r.get("Product Name", "")
    colours = ["Black", "White", "Silver", "Gold", "Blue", "Red", "Green", "Yellow",
               "Purple", "Pink", "Grey", "Gray", "Bronze", "Rose Gold", "Midnight", "Starlight"]
    for c in colours:
        if c.lower() in name.lower():
            return c
    return ""


# ════════════════════════════════════════════════════════════════════════════
# HD image processor
# ════════════════════════════════════════════════════════════════════════════

def _ensure_hd_images(result: dict) -> dict:
    """
    Upgrades image URLs to the highest available resolution.
    Covers Amazon, Noon / Cloudinary, and generic CDN size suffixes.
    """
    import re
    raw = result.get("Images", "")
    if not raw:
        return result

    hd_urls = []
    for url in (u.strip() for u in raw.split(",") if u.strip()):
        # Amazon size tokens
        url = re.sub(r'\._[A-Z]{2}\d+_', "._SL1500_", url)
        url = re.sub(r'\._AC_[^.]+_', "._AC_SL1500_", url)
        # Noon / Cloudinary
        if "cloudinary" in url or "noon" in url:
            url = re.sub(r'w_\d+', "w_2000", url)
            url = re.sub(r'q_\d+', "q_100", url)
            if "w_" not in url:
                url = url.replace("/upload/", "/upload/w_2000,q_100/")
        # Generic small-size suffixes
        url = re.sub(r'[_-](thumb|small|medium|sm|md)(\.\w+)$',
                     lambda m: m.group(2), url, flags=re.IGNORECASE)
        hd_urls.append(url)

    result["Images"] = ", ".join(hd_urls)
    return result


# ════════════════════════════════════════════════════════════════════════════
# Brand website search  — self-contained scraper with full bypass stack
# Layers (tried in order until one succeeds):
#   1. Direct URL construction — no search engine needed
#   2. Multiple search APIs (DDG lite, Bing, StartPage, Brave, Google)
#   3. cloudscraper   — bypasses Cloudflare & JS challenges
#   4. Playwright     — full headless Chromium, handles any JS/bot protection
# ════════════════════════════════════════════════════════════════════════════

import random, time as _time

# ── Rotating user-agent pool ────────────────────────────────────────────────
_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

def _random_ua():
    try:
        from fake_useragent import UserAgent
        return UserAgent().chrome
    except Exception:
        return random.choice(_UA_POOL)

def _headers(ua=None):
    """Build realistic browser headers with a random or given user-agent."""
    ua = ua or _random_ua()
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

# Kept for backward-compat references elsewhere in the file
_SCRAPE_HEADERS = _headers()


# ── Layer 1: Direct URL construction ────────────────────────────────────────
# Builds plausible product page URLs from the query without any search engine.

# ── Brand URL Patterns ──────────────────────────────────────────────────────
# Each brand lists its best product-page URL templates in priority order.
# {slug}        = hyphenated slug from query (brand word dropped)
# {slug_nobrand}= same as {slug}
# {slug_full}   = full query as slug (brand word kept)
# {slug_compact}= slug with all hyphens removed (for sites like Huawei/Vivo)
#
# Samsung real URL structure (confirmed from provided link):
#   samsung.com/{region}/smartphones/{series}/{model-slug}/
#   e.g. africa_en/smartphones/galaxy-a/galaxy-a06-black-128gb-sm-a065fzkhafb/
# We try the most common series names and regions.

_BRAND_URL_PATTERNS = {
    "samsung": [
        # Africa regions (highest priority — user is Africa-based)
        "https://www.samsung.com/africa_en/smartphones/galaxy-a/{slug}/",
        "https://www.samsung.com/africa_en/smartphones/galaxy-s/{slug}/",
        "https://www.samsung.com/africa_en/smartphones/galaxy-m/{slug}/",
        "https://www.samsung.com/africa_en/smartphones/galaxy-f/{slug}/",
        "https://www.samsung.com/africa_en/smartphones/{slug}/",
        # Nigeria / Ghana / Kenya / South Africa
        "https://www.samsung.com/ng/smartphones/galaxy-a/{slug}/",
        "https://www.samsung.com/ng/smartphones/galaxy-s/{slug}/",
        "https://www.samsung.com/ng/smartphones/{slug}/",
        "https://www.samsung.com/gh/smartphones/{slug}/",
        "https://www.samsung.com/ke/smartphones/{slug}/",
        "https://www.samsung.com/za/smartphones/{slug}/",
        # UK / US / Global
        "https://www.samsung.com/uk/smartphones/galaxy-a/{slug}/",
        "https://www.samsung.com/uk/smartphones/galaxy-s/{slug}/",
        "https://www.samsung.com/uk/smartphones/{slug}/",
        "https://www.samsung.com/us/smartphones/{slug}/",
        "https://www.samsung.com/global/galaxy/{slug}/",
    ],
    "apple": [
        # Apple URLs use model name directly, no category in path
        "https://www.apple.com/{slug}/",            # /iphone-15-pro/
        "https://www.apple.com/shop/buy-{slug}",    # /shop/buy-iphone-15-pro
        "https://www.apple.com/uk/{slug}/",
        "https://www.apple.com/ng/{slug}/",
    ],
    "nokia": [
        # Nokia uses nokia- prefix in slugs
        "https://www.nokia.com/phones/en_gb/nokia-{slug}/",
        "https://www.nokia.com/phones/en_int/nokia-{slug}/",
        "https://www.nokia.com/phones/{slug}/",
    ],
    # ── LG ─────────────────────────────────────────────────────────────────────
    # LG Africa URL format (confirmed from real pages):
    #   lg.com/africa/{category}/lg-{model}
    #   lg.com/{region}/{category}/lg-{model}
    # Categories: tvs, refrigerators, air-conditioners, washing-machines,
    #             soundbars, audio, monitors, mobile-phones
    # Model slug is LOWERCASE model code, e.g. lg-gc-x257cses, lg-65nano796ne
    "lg": [
        # Africa (primary — covers Nigeria, Ghana, Kenya, etc.)
        "https://www.lg.com/africa/tvs/lg-{slug}/",
        "https://www.lg.com/africa/refrigerators/lg-{slug}/",
        "https://www.lg.com/africa/air-conditioners/lg-{slug}/",
        "https://www.lg.com/africa/washing-machines/lg-{slug}/",
        "https://www.lg.com/africa/soundbars/lg-{slug}/",
        "https://www.lg.com/africa/monitors/lg-{slug}/",
        # Nigeria
        "https://www.lg.com/ng/tvs/lg-{slug}/",
        "https://www.lg.com/ng/refrigerators/lg-{slug}/",
        "https://www.lg.com/ng/air-conditioners/lg-{slug}/",
        "https://www.lg.com/ng/washing-machines/lg-{slug}/",
        # Ghana / Kenya / South Africa
        "https://www.lg.com/gh/tvs/lg-{slug}/",
        "https://www.lg.com/ke/tvs/lg-{slug}/",
        "https://www.lg.com/za/tvs/lg-{slug}/",
        "https://www.lg.com/za/refrigerators/lg-{slug}/",
        # East Africa
        "https://www.lg.com/eastafrica/tvs/lg-{slug}/",
        "https://www.lg.com/eastafrica/refrigerators/lg-{slug}/",
        "https://www.lg.com/eastafrica/air-conditioners/lg-{slug}/",
        # UK / US fallback
        "https://www.lg.com/uk/tvs/lg-{slug}/",
        "https://www.lg.com/uk/refrigerators/lg-{slug}/",
        "https://www.lg.com/uk/washing-machines/lg-{slug}/",
        "https://www.lg.com/us/tvs/lg-{slug}/",
        "https://www.lg.com/us/refrigerators/lg-{slug}/",
        "https://www.lg.com/uk/mobile-phones/{slug}/",
        "https://www.lg.com/us/mobile-phones/{slug}.html",
        "https://www.lg.com/ng/mobile-phones/{slug}/",
    ],
    # ── Hisense ────────────────────────────────────────────────────────────────
    # Hisense UK product URL format (confirmed from real pages):
    #   uk.hisense.com/products/{category}/{subcategory}/{INTERNAL_CODE}/p/{numeric_id}
    # Example: uk.hisense.com/products/cooling/freestanding-refrigerators/
    #   cross-door-refrigerators/REFRIG-BCD-605W-RQ768N4GBE-HSN/p/000000000020012750
    # Global site: global.hisense.com/{category}/{model}
    # South Africa: hisense.co.za/product/{slug}
    "hisense": [
        # UK Hisense — confirmed deep URL structure (requires search)
        "https://uk.hisense.com/products/cooling/freestanding-refrigerators/cross-door-refrigerators/p/",
        "https://uk.hisense.com/products/tv/uhd-tv/p/",
        "https://uk.hisense.com/products/tv/qled-tv/p/",
        # Global site — category/model slug
        "https://global.hisense.com/products/tvs/{slug}/",
        "https://global.hisense.com/products/refrigerators/{slug}/",
        "https://global.hisense.com/products/air-conditioners/{slug}/",
        "https://global.hisense.com/products/washing-machines/{slug}/",
        # South Africa
        "https://hisense.co.za/product/{slug}/",
        # USA
        "https://global.hisense.com/product/{slug}/",
        "https://www.hisense-usa.com/televisions/{slug}/",
        "https://www.hisense-usa.com/refrigerators/{slug}/",
    ],
    # ── Huawei (Solar/Power via FusionSolar / solar.huawei.com) ───────────────
    # Huawei solar/power products are on solar.huawei.com (FusionSolar), NOT consumer.huawei.com
    # Confirmed product URL: solar.huawei.com/en/products/{model-slug}/
    # Example: solar.huawei.com/en/products/sun5000-series/
    #          solar.huawei.com/en/products/sun2000-3-4-5-6-8-10ktl-m1/
    # Residential products: solar.huawei.com/en/products/residential/
    "huawei": [
        # FusionSolar product pages (Power Solution category)
        "https://solar.huawei.com/en/products/{slug}/",
        "https://solar.huawei.com/en/products/{slug_compact}/",
        "https://solar.huawei.com/professionals/all-products",
        # Consumer phones (original patterns kept)
        "https://consumer.huawei.com/en/phones/{slug}/",
        "https://consumer.huawei.com/en/phones/{slug_compact}/",
        "https://consumer.huawei.com/ng/phones/{slug}/",
    ],
    # ── Growatt (solar inverters & batteries on en.growatt.com) ───────────────
    # Confirmed product URL format: en.growatt.com/products/{model-slug}
    # Examples (confirmed from real search results):
    #   en.growatt.com/products/sph-3000-6000tl-bl-up
    #   en.growatt.com/products/spe-8000-12000-es
    #   en.growatt.com/products/spf-6000-es-plus
    # Slugs are hyphenated lowercase model names (spaces/slashes become hyphens)
    "growatt": [
        "https://en.growatt.com/products/{slug}",
        "https://en.growatt.com/products/{slug_compact}",
        "https://en.growatt.com/products/",
    ],
    # ── Deye (inverters on deyeinverter.com) ──────────────────────────────────
    # Confirmed product URL: deyeinverter.com/product/hybrid-inverter-1/
    # Category-based structure: /product/{category}/
    # Model pages at: deyeinverter.com/product/{category-slug}/
    "deye": [
        "https://www.deyeinverter.com/product/{slug}/",
        "https://www.deyeinverter.com/product/hybrid-inverter-1/",
        "https://www.deyeinverter.com/product/off-grid-inverter/",
        "https://www.deyeinverter.com/product/on-grid-inverter/",
        "https://www.deyeinverter.com/product/",
    ],
    # ── Jinko Solar (panels on jinkosolar.com) ────────────────────────────────
    # Confirmed product URL format: jinkosolar.com/en/site/{series-slug}
    # Examples (confirmed from real search results):
    #   jinkosolar.com/en/site/tiger
    #   jinkosolar.com/en/site/tigerpro
    # Also: jinkosolar.com/en/site/newsdetail/{id} for news
    "jinko": [
        "https://www.jinkosolar.com/en/site/{slug}",
        "https://www.jinkosolar.com/en/site/tiger",
        "https://www.jinkosolar.com/en/site/tigerpro",
        "https://www.jinkosolar.com/en/",
    ],
    # ── Pylontech (batteries on en.pylontech.com.cn) ─────────────────────────
    # Confirmed product URL format: en.pylontech.com.cn/products/{model-slug}
    # Examples (confirmed from real search results):
    #   en.pylontech.com.cn/products/fidus-battery
    #   en.pylontech.com.cn/products/fidus-battery-plus
    # Slugs are hyphenated lowercase product names
    "pylontech": [
        "https://en.pylontech.com.cn/products/{slug}",
        "https://en.pylontech.com.cn/products/{slug_compact}",
        "https://en.pylontech.com.cn/products/",
    ],
    # ── TSTY ──────────────────────────────────────────────────────────────────
    # TSTY is a Chinese solar/power brand with no well-known English website.
    # Fouani-first approach is recommended; no reliable direct URL pattern.
    "tsty": [],
    # ── Maxi (Nigerian small appliances brand) ────────────────────────────────
    # Maxi is a Nigerian small appliances brand. No dedicated product pages found.
    # Fouani-first approach is recommended.
    "maxi": [],
    # ── Actiu (Spanish office furniture on actiu.com) ─────────────────────────
    # Confirmed product URL formats (from real search results):
    #   actiu.com/en/furniture/{category}/{product-slug}/
    #   actiu.com/en/tables/{category}/{product-slug}/
    #   actiu.com/en/seats-contract/{category}/{product-slug}/
    # Examples confirmed:
    #   actiu.com/en/tables/office-desks/twist/
    #   actiu.com/en/seats-contract/office-chairs/stay/
    # Catalog site (separate domain): catalogo.actiu.com/en/furniture/{category}/{product}/
    "actiu": [
        "https://www.actiu.com/en/furniture/{slug}/",
        "https://www.actiu.com/en/tables/office-desks/{slug}/",
        "https://www.actiu.com/en/seats-contract/office-chairs/{slug}/",
        "https://www.actiu.com/en/seats-contract/multi-purpose-chairs/{slug}/",
        "https://www.actiu.com/en/furniture/storage/{slug}/",
        "https://www.actiu.com/en/furniture/office-desks/{slug}/",
        "https://catalogo.actiu.com/en/furniture/office-chairs/{slug}/",
    ],
    "sony": [
        # Sony uses /en/articles/{slug} or /en/{slug}
        "https://www.sony.com/en/articles/{slug}",
        "https://www.sony.com/en/{slug}/",
        "https://www.sony.co.uk/en_GB/products/mobiles/{slug}.html",
    ],
    "huawei": [
        # Huawei slugs are compact (no hyphens): mate60pro
        "https://consumer.huawei.com/en/phones/{slug}/",
        "https://consumer.huawei.com/en/phones/{slug_compact}/",
        "https://consumer.huawei.com/ng/phones/{slug}/",
    ],
    "xiaomi": [
        # Xiaomi uses brand+model compact: xiaomi14ultra
        "https://www.mi.com/global/product/{slug_compact}",
        "https://www.mi.com/global/product/{slug}",
        "https://www.xiaomi.com/uk/product/{slug}",
        "https://www.mi.com/en/product/{slug_compact}",
    ],
    "oppo": [
        "https://www.oppo.com/en/smartphones/{slug}/",
        "https://www.oppo.com/ng/smartphones/{slug}/",
        "https://www.oppo.com/uk/smartphones/{slug}/",
    ],
    "oneplus": [
        # OnePlus uses oneplus- prefix: oneplus-12
        "https://www.oneplus.com/uk/oneplus-{slug}",
        "https://www.oneplus.com/us/oneplus-{slug}",
        "https://www.oneplus.com/global/oneplus-{slug}",
        "https://www.oneplus.com/uk/{slug}",
    ],
    "google": [
        "https://store.google.com/product/{slug}",
        "https://store.google.com/us/product/{slug}",
        "https://store.google.com/ng/product/{slug}",
    ],
    "tecno": [
        "https://www.tecno-mobile.com/ng/product/{slug}/",
        "https://www.tecno-mobile.com/en/product/{slug}/",
        "https://www.tecno-mobile.com/en/{slug}.html",
    ],
    "infinix": [
        # Infinix uses infinix- prefix: infinix-note-40-pro
        "https://www.infinixmobility.com/product/infinix-{slug}",
        "https://www.infinixmobility.com/product/{slug}",
        "https://www.infinix.com/ng/product/infinix-{slug}/",
        "https://www.infinix.com/global/product/infinix-{slug}/",
    ],
    "itel": [
        # Itel uses itel- prefix: itel-s24
        "https://www.itel-mobile.com/product/itel-{slug}/",
        "https://www.itel-mobile.com/product/{slug}/",
        "https://www.itel.com/ng/product/itel-{slug}/",
        "https://www.itel.com/global/product/itel-{slug}/",
    ],
    "motorola": [
        # Motorola uses motorola- prefix in slug
        "https://www.motorola.com/us/smartphones-motorola-{slug}-series/motorola-{slug}/p",
        "https://www.motorola.com/us/smartphones/motorola-{slug}/p",
        "https://www.motorola.com/uk/smartphones/motorola-{slug}/p",
        "https://www.motorola.com/ng/smartphones/motorola-{slug}/p",
    ],
    "realme": [
        # Realme uses realme- prefix: realme-gt-6
        "https://www.realme.com/global/realme-{slug}/",
        "https://www.realme.com/ng/realme-{slug}/",
        "https://www.realme.com/en/realme-{slug}/",
        "https://www.realme.com/ng/realme-{slug}",
    ],
    "honor": [
        # Honor uses honor- prefix: honor-magic6-pro
        "https://www.hihonor.com/uk/phones/honor-{slug}/",
        "https://www.hihonor.com/global/phones/honor-{slug}/",
        "https://www.hihonor.com/ng/phones/honor-{slug}/",
        "https://www.hihonor.com/uk/phones/{slug}/",
    ],
    "vivo": [
        # Vivo slugs are compact: v30pro
        "https://www.vivo.com/en/products/{slug_compact}.html",
        "https://www.vivo.com/en/products/{slug}.html",
        "https://www.vivo.com/ng/products/{slug}.html",
    ],
    "asus": [
        "https://www.asus.com/uk/phones/{slug}/",
        "https://www.asus.com/us/phones/{slug}/",
    ],
    "poco": [
        "https://www.poco.net/global/phones/{slug}/",
        "https://www.mi.com/global/product/poco-{slug}",
    ],
    "tcl": [
        "https://www.tcl.com/global/en/phones/{slug}.html",
        "https://www.tcl.com/us/en/phones/{slug}.html",
    ],
    "alcatel": [
        "https://www.alcatelmobile.com/product/{slug}/",
    ],
    "zte": [
        "https://www.ztedevices.com/en/product/{slug}/",
    ],
    "htc": [
        "https://www.htc.com/uk/smartphones/{slug}/",
        "https://www.htc.com/us/smartphones/{slug}/",
    ],
    "lenovo": [
        "https://www.lenovo.com/uk/en/phones/{slug}/",
        "https://www.lenovo.com/us/en/phones/{slug}/",
    ],
    "blackberry": [
        "https://www.blackberry.com/us/en/phones/{slug}",
    ],

    # ════════════════════════════════════════════════════════════════════════
    # ── TVs ──────────────────────────────────────────────────────────────────
    # ════════════════════════════════════════════════════════════════════════

    # ── Sony TVs (BRAVIA) ──────────────────────────────────────────────────
    # Confirmed product URL: sony.com/en/articles/{model-slug}
    # Examples: sony.com/en/articles/bravia-8-oled-tv, /en/articles/x95l-bravia-xr
    # TV model slugs are marketing names not model codes
    # Also: store.sony.com/products/televisions/{model}.html
    "sony": [
        # TVs and Xperia phones share the same sony.com articles path
        "https://www.sony.com/en/articles/{slug}",
        "https://www.sony.com/en/articles/{slug}/",
        "https://store.sony.com/products/televisions/{slug}.html",
        "https://www.sony.co.za/en_ZA/content/sony-product/{slug}.html",
        "https://www.sony.co.uk/en_GB/content/sony-product/{slug}.html",
        # Xperia phones
        "https://www.sony.com/en/products/xperia/{slug}/",
        "https://www.sony.co.uk/en_GB/products/mobiles/{slug}.html",
    ],

    # ── TCL TVs & ACs (already existed with phone paths — expanded) ─────────
    # TCL product URL: tcl.com/global/en/televisions/{slug}.html
    # (already has phone patterns; adding TV/AC patterns)

    # ── Skyworth TVs (growing in SA / Africa) ────────────────────────────────
    # Confirmed from search: skyworth.com/en/product/{category}/{slug}
    "skyworth": [
        "https://www.skyworth.com/en/product/television/{slug}",
        "https://www.skyworth.com/en/product/{slug}",
        "https://www.skyworth.co.za/product/{slug}/",
    ],

    # ════════════════════════════════════════════════════════════════════════
    # ── AIR CONDITIONERS ─────────────────────────────────────────────────────
    # ════════════════════════════════════════════════════════════════════════

    # ── Daikin ACs ───────────────────────────────────────────────────────────
    # Confirmed from search: daikin.co.uk/en/products/{category}/{slug}
    # UK site used as primary since Africa uses same product line
    "daikin": [
        "https://www.daikin.co.uk/en/products/air-conditioners/{slug}",
        "https://www.daikin.co.uk/en/products/{slug}",
        "https://www.daikin.com/products/{slug}/",
        "https://www.daikin-me.com/products/residential/{slug}/",   # Middle East/Africa
        "https://www.daikin.com.ng/products/{slug}/",               # Nigeria
    ],

    # ── Panasonic ACs & electronics ──────────────────────────────────────────
    # Confirmed pattern: panasonic.com/global/consumer/air-conditioner/{slug}.html
    # Also: shop.panasonic.com/products/{slug}
    "panasonic": [
        "https://www.panasonic.com/global/consumer/air-conditioner/{slug}.html",
        "https://www.panasonic.com/global/consumer/{slug}.html",
        "https://www.panasonic.com/africa/consumer/air-conditioner/{slug}.html",
        "https://www.panasonic.com/ng/consumer/{slug}.html",
        "https://shop.panasonic.com/products/{slug}",
        "https://shop.panasonic.com/products/{slug_compact}",
    ],

    # ── Midea ACs, washing machines, refrigerators ───────────────────────────
    # Confirmed from search: midea.com/global/products/{category}/{slug}
    # Also: midea.co.za/product/{slug}
    "midea": [
        "https://www.midea.com/global/products/Air-Conditioner/{slug}",
        "https://www.midea.com/global/products/Washing-Machine/{slug}",
        "https://www.midea.com/global/products/Refrigerator/{slug}",
        "https://www.midea.com/global/products/{slug}",
        "https://www.midea.co.za/product/{slug}/",
        "https://www.midea.com/ng/products/{slug}",
    ],

    # ── Gree ACs ─────────────────────────────────────────────────────────────
    # Gree is popular in Nigeria; product pages at gree.com
    "gree": [
        "https://www.gree.com/products/residential/{slug}",
        "https://www.gree.com/products/{slug}",
        "https://greecomfort.com/product/{slug}/",
        "https://gree-global.com/products/{slug}/",
    ],

    # ── Samsung ACs (same samsung.com site, /air-conditioners/ category) ─────
    # Already handled via Samsung's category-aware routing in _direct_urls.
    # samsung entry NOT needed here; covered by the main "samsung" block.

    # ════════════════════════════════════════════════════════════════════════
    # ── REFRIGERATORS & WASHING MACHINES ─────────────────────────────────────
    # ════════════════════════════════════════════════════════════════════════

    # ── Haier / Haier Thermocool ─────────────────────────────────────────────
    # Haier Thermocool is the Nigeria-specific brand (joint venture).
    # haier.com/global URLs are the primary source.
    "haier": [
        "https://www.haier.com/global/refrigerators/{slug}/",
        "https://www.haier.com/global/washing-machines/{slug}/",
        "https://www.haier.com/global/air-conditioners/{slug}/",
        "https://www.haier.com/global/household-appliances/{slug}/",
        "https://www.haier.com/ng/{slug}/",
        "https://www.thermocool.com.ng/product/{slug}/",
    ],

    # ── Bosch home appliances ────────────────────────────────────────────────
    # Confirmed: bosch-home.com/ng/products/{slug}
    # Also: bosch-home.com/za/products/{slug}
    "bosch": [
        "https://www.bosch-home.com/ng/products/{slug}.html",
        "https://www.bosch-home.com/za/products/{slug}.html",
        "https://www.bosch-home.com/global/products/{slug}.html",
        "https://www.bosch-home.com/uk/products/{slug}.html",
    ],

    # ── Whirlpool appliances ─────────────────────────────────────────────────
    "whirlpool": [
        "https://www.whirlpool.com/washers/{slug}.html",
        "https://www.whirlpool.com/refrigerators/{slug}.html",
        "https://www.whirlpool.co.za/washers/{slug}",
        "https://www.whirlpool.co.za/refrigerators/{slug}",
    ],

    # ── Beko appliances ──────────────────────────────────────────────────────
    # Beko strong in Africa; beko.com/ng/ exists
    "beko": [
        "https://www.beko.com/ng/products/{slug}",
        "https://www.beko.com/za/products/{slug}",
        "https://www.beko.com/global/products/{slug}",
        "https://www.beko.co.uk/all-products/{slug}",
    ],

    # ── Electrolux appliances ─────────────────────────────────────────────────
    "electrolux": [
        "https://www.electrolux.co.za/products/{slug}",
        "https://www.electrolux.co.za/{slug}/",
        "https://www.electrolux.com/en/products/{slug}/",
        "https://www.electrolux.co.uk/products/{slug}/",
    ],

    # ── Indesit (popular budget appliances in Africa) ─────────────────────────
    "indesit": [
        "https://www.indesit.com/en-gb/washing-machines/{slug}",
        "https://www.indesit.com/en-za/washing-machines/{slug}",
        "https://www.indesit.com/en-gb/refrigerators/{slug}",
    ],

    # ── Balmuda (premium small appliances) ────────────────────────────────────
    # Very niche; search is primary path
    "balmuda": [
        "https://www.balmuda.com/en/product/{slug}",
    ],

    # ════════════════════════════════════════════════════════════════════════
    # ── AUDIO / SPEAKERS / SOUNDBARS ─────────────────────────────────────────
    # ════════════════════════════════════════════════════════════════════════

    # ── JBL (Harman/Samsung) ─────────────────────────────────────────────────
    # Confirmed product URL format (from real pages):
    #   jbl.com/{MODEL-CODE-UPPERCASE}.html
    # Examples confirmed:
    #   jbl.com/FLIP-7.html, jbl.com/CHARGE-6.html
    #   jbl.com/AUTHENTICS-500.html, jbl.com/BOOMBOX-4.html
    # The slug = UPPERCASE model code with hyphens
    "jbl": [
        "https://www.jbl.com/{slug_full_upper}.html",
        "https://www.jbl.com/{slug}.html",
        "https://www.jbl.com/{slug_compact}.html",
        "https://global.jbl.com/{slug_full_upper}.html",
        "https://global.jbl.com/{slug}.html",
    ],

    # ── Sony Audio (soundbars, speakers, headphones) ──────────────────────────
    # Already handled by the "sony" entry above.

    # ── Bose ─────────────────────────────────────────────────────────────────
    # Confirmed: bose.com/en_us/products/{category}/{slug}
    # Examples: /en_us/products/speakers/portable-speakers/soundlink-flex
    "bose": [
        "https://www.bose.com/en_us/products/speakers/{slug}",
        "https://www.bose.com/en_us/products/speakers/bluetooth-portable-speakers/{slug}",
        "https://www.bose.com/en_us/products/{slug}",
        "https://www.bose.co.uk/en_gb/products/speakers/{slug}",
        "https://www.bose.co.za/en_za/products/speakers/{slug}",
    ],

    # ── Sonos ─────────────────────────────────────────────────────────────────
    # Confirmed: sonos.com/en-us/products/{slug}
    "sonos": [
        "https://www.sonos.com/en-us/products/{slug}",
        "https://www.sonos.com/en-gb/products/{slug}",
        "https://www.sonos.com/en-za/products/{slug}",
    ],

    # ── Yamaha Audio ─────────────────────────────────────────────────────────
    # Confirmed: uk.yamaha.com/en/products/audio_visual/{slug}
    "yamaha": [
        "https://uk.yamaha.com/en/products/audio_visual/{slug}",
        "https://usa.yamaha.com/products/audio_visual/{slug}",
        "https://africa.yamaha.com/en/products/audio_visual/{slug}",
    ],

    # ── Marshall ─────────────────────────────────────────────────────────────
    "marshall": [
        "https://www.marshallheadphones.com/en_gb/speakers/{slug}/",
        "https://www.marshallheadphones.com/en_us/speakers/{slug}/",
    ],

    # ── Harman Kardon ─────────────────────────────────────────────────────────
    "harman": [
        "https://www.harmankardon.com/wireless-speakers/{slug}.html",
        "https://www.harmankardon.com/soundbars/{slug}.html",
    ],

    # ── Anker Soundcore ──────────────────────────────────────────────────────
    "anker": [
        "https://www.soundcore.com/products/{slug}",
        "https://www.anker.com/products/{slug}",
    ],

    # ════════════════════════════════════════════════════════════════════════
    # ── POWER SOLUTION / SOLAR PANELS & INVERTERS ────────────────────────────
    # ════════════════════════════════════════════════════════════════════════

    # ── LONGi Solar (top solar panels in Nigeria/Africa) ─────────────────────
    # Confirmed: longi-solar.com/en/products/{slug}/
    # Product lines: Hi-MO 6, Hi-MO 7, Hi-MO X10
    "longi": [
        "https://www.longi-solar.com/en/products/{slug}/",
        "https://www.longi.com/en/products/{slug}/",
        "https://www.longi-solar.com/en/products/",
    ],

    # ── Canadian Solar ────────────────────────────────────────────────────────
    # Confirmed: canadiansolar.com/{slug}.html
    # Product series e.g. canadiansolar.com/hiku7.html
    "canadian": [
        "https://www.canadiansolar.com/{slug}.html",
        "https://www.canadiansolar.com/{slug}/",
        "https://www.canadiansolar.com/solar-panels.html",
    ],

    # ── Trina Solar ──────────────────────────────────────────────────────────
    # Confirmed: trinasolar.com/en-global/product/{slug}.html
    "trina": [
        "https://www.trinasolar.com/en-global/product/{slug}.html",
        "https://www.trinasolar.com/en-global/product/{slug}/",
        "https://www.trinasolar.com/en-global/product/",
    ],

    # ── JA Solar ─────────────────────────────────────────────────────────────
    # Confirmed: jasolar.com/html/en/product/{slug}
    "jasolar": [
        "https://www.jasolar.com/html/en/product/{slug}",
        "https://www.jasolar.com/html/en/product/{slug}/",
    ],

    # ── SMA Solar (premium inverters) ────────────────────────────────────────
    # Confirmed: sma.de/en/products/solar-inverters/{slug}.html
    "sma": [
        "https://www.sma.de/en/products/solar-inverters/{slug}.html",
        "https://www.sma.de/en/products/{slug}.html",
        "https://www.sma.de/en/products/solar-inverters/",
    ],

    # ── Victron Energy (inverters/chargers) ───────────────────────────────────
    # Confirmed: victronenergy.com/inverters/{slug}
    "victron": [
        "https://www.victronenergy.com/inverters/{slug}",
        "https://www.victronenergy.com/battery-monitors/{slug}",
        "https://www.victronenergy.com/solar-charge-controllers/{slug}",
        "https://www.victronenergy.com/batteries/{slug}",
        "https://www.victronenergy.com/",
    ],

    # ── Luminous inverters/batteries ─────────────────────────────────────────
    "luminous": [
        "https://www.luminousindia.com/products/{slug}",
        "https://www.luminousindia.com/products/{slug}/",
        "https://www.luminous-global.com/products/{slug}/",
    ],

    # ── Felicity Solar (popular local Nigeria brand) ──────────────────────────
    "felicity": [
        "https://felicitysolarng.com/product/{slug}/",
        "https://www.felicitysolar.com/product/{slug}/",
        "https://felicitysolarng.com/product-category/",
    ],

    # ── Suntech Solar panels ──────────────────────────────────────────────────
    "suntech": [
        "https://www.suntech-power.com/en/products/{slug}/",
        "https://www.suntech-power.com/en/",
    ],

    # ── Risen Solar panels ────────────────────────────────────────────────────
    "risen": [
        "https://www.risen-solar.com/products/{slug}/",
        "https://en.risen-solar.com/products/{slug}/",
    ],

    # ── SMALL APPLIANCES / FANS ───────────────────────────────────────────────

    # ── Scanfrost (popular Nigerian brand) ────────────────────────────────────
    "scanfrost": [
        "https://scanfrost.com.ng/product/{slug}/",
        "https://www.scanfrost.com.ng/product/{slug}/",
    ],

    # ── Nexus (Nigerian small appliances) ────────────────────────────────────
    "nexus": [
        "https://www.nexuselectronics.com.ng/product/{slug}/",
        "https://nexuselectronics.com.ng/product/{slug}/",
    ],

    # ── Polystar (Nigerian appliances) ───────────────────────────────────────
    "polystar": [
        "https://polystar.com.ng/product/{slug}/",
        "https://www.polystar.com.ng/product/{slug}/",
    ],

    # ── Bruhm (Nigerian/African appliances) ──────────────────────────────────
    "bruhm": [
        "https://bruhmafrica.com/product/{slug}/",
        "https://www.bruhmafrica.com/product/{slug}/",
    ],
}



# ── Fouani-first brands/categories ──────────────────────────────────────────
# For these brands (across categories: ACs, Audio, Furnitures, Power Solution,
# Refrigerator, Small Appliances/Fans, TVs, Washing Machines), we search
# fouanistore.com BEFORE trying the brand's official website.
_FOUANI_FIRST_BRANDS = {
    "lg", "hisense", "actiu",
    "huawei", "growatt", "deye", "jinko", "pylontech", "tsty",
    "maxi",
}


def _search_fouani(query: str) -> dict:
    """
    Search fouanistore.com for a product matching `query`.

    NOTE: fouanistore.com returns 403 "Host not in allowlist" from all
    cloud/server IPs at the reverse-proxy level.  Return {} immediately to
    avoid burning timeout cycles, until the IP block is lifted.
    """
    return {}

def _make_slug(query: str) -> str:
    """
    Convert query to URL slug.
    'Samsung Galaxy A06 Black 128GB SM-A065FZKHAFB' -> 'galaxy-a06-black-128gb-sm-a065fzkhafb'

    IMPORTANT: Preserves hyphens within model codes (SM-A065FZKHAFB -> sm-a065fzkhafb).
    This matches Samsung africa_en confirmed URL format exactly.
    """
    import re
    # Remove brand word (first word)
    q = re.sub(r'^\S+\s+', '', query).strip()
    # Lowercase
    q = q.lower()
    # Replace any non-alphanumeric char EXCEPT hyphens with a hyphen
    q = re.sub(r'[^a-z0-9\-]+', '-', q)
    # Collapse multiple hyphens
    q = re.sub(r'-+', '-', q)
    return q.strip('-')


def _make_slug_variants(query: str) -> dict:
    """
    Return multiple slug variants needed by different brand URL patterns.
    Returns dict with keys: slug, slug_compact, slug_full, slug_brand_prefix.
    """
    import re
    brand   = query.split()[0].lower()
    slug    = _make_slug(query)   # no brand, hyphenated
    compact = slug.replace('-', '')                         # no hyphens: 'galaxya06black'
    full    = re.sub(r'[^a-z0-9]+', '-',
                     query.lower()).strip('-')               # brand included: 'samsung-galaxy-a06'
    brand_prefix = brand + '-' + slug                       # 'samsung-galaxy-a06-black'
    return {
        'slug':          slug,
        'slug_compact':  compact,
        'slug_full':     full,
        'slug_brand':    brand_prefix,
        'slug_full_upper': slug.upper(),                     # 'FLIP-7', 'CHARGE-6' for JBL etc.
    }


# Samsung Galaxy series -> URL subcategory mapping
_SAMSUNG_SERIES = {
    "galaxy-s": ["galaxy-s","galaxy s"],
    "galaxy-z": ["galaxy-z","galaxy z","fold","flip"],
    "galaxy-m": ["galaxy-m","galaxy m"],
    "galaxy-f": ["galaxy-f","galaxy f"],
    "galaxy-a": ["galaxy-a","galaxy a"],  # fallback — most common
}


def _detect_samsung_series(query: str) -> str:
    """Detect Samsung Galaxy series from query string, return URL subcategory."""
    q = query.lower()
    if any(x in q for x in ["galaxy s", "galaxy-s", " s24", " s23", " s22", " s21",
                             " s20"," s10"," s9 "," s8 "]):
        return "galaxy-s"
    if any(x in q for x in ["fold","flip","galaxy z","galaxy-z"," z fold"," z flip"]):
        return "galaxy-z"
    if any(x in q for x in ["galaxy m","galaxy-m"," m35"," m34"," m33"," m32",
                             " m31"," m15"," m14"," m13"," m12"]):
        return "galaxy-m"
    if any(x in q for x in ["galaxy f","galaxy-f"," f15"," f14"," f13"," f12"]):
        return "galaxy-f"
    if any(x in q for x in ["galaxy a","galaxy-a"," a06"," a16"," a25"," a35",
                             " a55"," a05"," a15"," a24"," a34"," a54"]):
        return "galaxy-a"
    # Default: use galaxy-a (most common budget series)
    return "galaxy-a"


def _direct_urls(query: str) -> list:
    """
    Return candidate product page URLs for a query using known brand patterns.
    Applies smart series detection for Samsung, brand-prefix variants for others.
    Returns up to 12 deduplicated URLs in priority order.
    """
    brand    = query.split()[0].lower()
    # Handle multi-word brand names where first word isn't the dict key
    _brand_aliases = {
        "ja": "jasolar",     # "JA Solar JAM72S30" -> use "jasolar" patterns
        "canadian": "canadian",   # "Canadian Solar" stays as "canadian"
        "trina": "trina",
        "ha": "haier",       # edge case
    }
    brand = _brand_aliases.get(brand, brand)
    variants = _make_slug_variants(query)
    slug     = variants['slug']

    # Samsung: use confirmed URL format from africa_en.
    # Confirmed structure: samsung.com/{region}/smartphones/{series}/{full-slug}/
    # where full-slug = entire product name+color+storage+model in lowercase with hyphens
    # e.g. galaxy-a06-black-128gb-sm-a065fzkhafb
    # The FULL slug (including color, storage, model code) is the correct URL.
    if brand == "samsung":
        series = _detect_samsung_series(query)
        import re as _re_slug, urllib.parse as _up_s
        q_low_s = query.lower()
        q_enc = _up_s.quote_plus(query)

        # Detect non-phone Samsung products (ACs, washing machines, TVs, fridges)
        _sam_cat = None
        if any(x in q_low_s for x in ["air condition","aircon"," ac ","split unit","wind-free"]):
            _sam_cat = "air-conditioners"
        elif any(x in q_low_s for x in ["washing machine","washer","ecobubble","addwash"]):
            _sam_cat = "washing-machines"
        elif any(x in q_low_s for x in ["refrigerator","fridge","bespoke fridge","twin cooling"]):
            _sam_cat = "refrigerators"
        elif any(x in q_low_s for x in [" tv "," oled "," qled "," neo qled "," uhd "," 4k tv"," 8k tv","lifestyle tv"]):
            _sam_cat = "tvs"

        if _sam_cat:
            # Samsung appliance: lg.com-style pattern but on samsung.com
            _sam_slug = _re_slug.sub(r'[^a-z0-9\-]+', '-',
                                      query[len("samsung"):].strip().lower()).strip('-')
            _sam_slug = _re_slug.sub(r'-+', '-', _sam_slug)
            urls = []
            seen = set()
            def _samadd(u):
                if u not in seen: seen.add(u); urls.append(u)
            for region in ["africa_en","ng","gh","ke","za","uk","us"]:
                _samadd(f"https://www.samsung.com/{region}/{_sam_cat}/{_sam_slug}/")
            # Samsung search as fallback
            _samadd(f"https://www.samsung.com/africa_en/search/?searchvalue={q_enc}")
            _samadd(f"https://www.samsung.com/ng/search/?searchvalue={q_enc}")
            return urls

        # Detect if the query already contains a full model code (SM-XXXXXX)
        _has_model_code = bool(_re_slug.search(r'\bsm-[a-z0-9]{6,}\b', slug, _re_slug.IGNORECASE))

        urls = []
        seen = set()
        def _sadd(u):
            if u not in seen: seen.add(u); urls.append(u)

        q_enc = _up_s.quote_plus(query)

        if _has_model_code:
            # ── Full query with model code: direct URL first (exact match) ──
            # Confirmed format: africa_en/smartphones/{series}/{full-slug}/
            _sadd(f"https://www.samsung.com/africa_en/smartphones/{series}/{slug}/")
            _sadd(f"https://www.samsung.com/africa_en/smartphones/{slug}/")
            # African country fallbacks
            for region in ["ng", "gh", "ke", "za"]:
                _sadd(f"https://www.samsung.com/{region}/smartphones/{series}/{slug}/")
            # Samsung search as backup (finds canonical URL if slug is slightly off)
            for region in ["africa_en", "ng"]:
                _sadd(f"https://www.samsung.com/{region}/search/?searchvalue={q_enc}")
            # UK/US last
            for region in ["uk", "us"]:
                _sadd(f"https://www.samsung.com/{region}/smartphones/{series}/{slug}/")
        else:
            # ── Partial query (no model code): search FIRST, then direct URLs ──
            # Samsung's search resolves partial queries to the canonical product URL.
            # Direct slug URLs won't work without the storage+model-code suffix.
            for region in ["africa_en", "ng", "gh", "ke"]:
                _sadd(f"https://www.samsung.com/{region}/search/?searchvalue={q_enc}")
            # Direct URL attempts (may work if Samsung redirects to canonical)
            _sadd(f"https://www.samsung.com/africa_en/smartphones/{series}/{slug}/")
            _sadd(f"https://www.samsung.com/africa_en/smartphones/{slug}/")
            for region in ["ng", "uk"]:
                _sadd(f"https://www.samsung.com/{region}/smartphones/{series}/{slug}/")

        _sadd(f"https://www.samsung.com/global/galaxy/{slug}/")
        return urls

    # ── LG: detect product category from query and pick right URL subcategory ──
    # LG Africa confirmed format: lg.com/{region}/{category}/lg-{model}/
    # The model slug for LG is the model code ONLY (no brand word), lowercased.
    if brand == "lg":
        import re as _re_lg, urllib.parse as _up_lg
        q_low = query.lower()
        q_enc = _up_lg.quote_plus(query)

        # Detect category from query keywords
        _lg_cat = "tvs"  # default
        if any(x in q_low for x in ["refrigerator","fridge"," ref ","gc-","gb-","gn-","cross door","sxs","french door"]):
            _lg_cat = "refrigerators"
        elif any(x in q_low for x in ["air condition","aircon"," ac ","air-con","split unit","inverter-v","s4nw","s3nw","cassette"]):
            _lg_cat = "air-conditioners"
        elif any(x in q_low for x in ["washing","washer","wm ","f4v","f2v","f4r","f2r"]):
            _lg_cat = "washing-machines"
        elif any(x in q_low for x in ["soundbar","sound bar","speaker"," audio"]):
            _lg_cat = "soundbars"
        elif any(x in q_low for x in ["monitor"]):
            _lg_cat = "monitors"

        # LG model slug: strip brand, lowercase, hyphens (e.g. GC-X257CSES -> gc-x257cses)
        _lg_slug = _re_lg.sub(r'[^a-z0-9\-]+', '-', query[len("lg"):].strip().lower()).strip('-')
        _lg_slug = _re_lg.sub(r'-+', '-', _lg_slug)

        urls = []
        seen = set()
        def _ladd(u):
            if u not in seen: seen.add(u); urls.append(u)

        # Africa first (primary market)
        _ladd(f"https://www.lg.com/africa/{_lg_cat}/lg-{_lg_slug}/")
        _ladd(f"https://www.lg.com/ng/{_lg_cat}/lg-{_lg_slug}/")
        _ladd(f"https://www.lg.com/gh/{_lg_cat}/lg-{_lg_slug}/")
        _ladd(f"https://www.lg.com/ke/{_lg_cat}/lg-{_lg_slug}/")
        _ladd(f"https://www.lg.com/za/{_lg_cat}/lg-{_lg_slug}/")
        _ladd(f"https://www.lg.com/eastafrica/{_lg_cat}/lg-{_lg_slug}/")
        # UK/US fallback
        _ladd(f"https://www.lg.com/uk/{_lg_cat}/lg-{_lg_slug}/")
        _ladd(f"https://www.lg.com/us/{_lg_cat}/lg-{_lg_slug}/")
        # Search fallback
        _ladd(f"https://www.lg.com/africa/search/?keyword={q_enc}")
        _ladd(f"https://www.lg.com/ng/search/?keyword={q_enc}")
        return urls

    # ── Huawei: route solar/power queries to solar.huawei.com ─────────────────
    if brand == "huawei":
        import re as _re_hw, urllib.parse as _up_hw
        q_low = query.lower()
        q_enc = _up_hw.quote_plus(query)
        # Detect if this is a solar/power query (not a phone query)
        _is_solar = any(x in q_low for x in [
            "solar","inverter","sun2000","sun5000","sun6000","sun8000","sun10000",
            "battery","storage","pv","fusionsolar","ktl","hybrid","power solution",
        ])
        if _is_solar:
            # Solar/Power products -> solar.huawei.com
            _hw_slug = _re_hw.sub(r'[^a-z0-9\-]+', '-',
                                   query[len("huawei"):].strip().lower()).strip('-')
            _hw_slug = _re_hw.sub(r'-+', '-', _hw_slug)
            urls = []
            seen = set()
            def _hadd(u):
                if u not in seen: seen.add(u); urls.append(u)
            _hadd(f"https://solar.huawei.com/en/products/{_hw_slug}/")
            _hadd(f"https://solar.huawei.com/en/products/{_hw_slug.replace('-', '')}/")
            _hadd(f"https://solar.huawei.com/professionals/all-products")
            _hadd(f"https://solar.huawei.com/en/products/?search={q_enc}")
            return urls

    # ── Hisense: category-aware routing to official website ──────────────────
    # Hisense UK deep URLs require a numeric internal ID — not guessable.
    # Best approach: use global.hisense.com with the right category + model slug,
    # plus hisense.co.za as a secondary, then fall through to search engines.
    if brand == "hisense":
        import re as _re_hi, urllib.parse as _up_hi
        q_low_hi = query.lower()
        q_enc_hi = _up_hi.quote_plus(query)

        # Detect category
        _hi_cat = "tvs"   # default
        if any(x in q_low_hi for x in ["refrigerator","fridge","cross door","sxs","side by side","french door","rc-","rd-","rb-"]):
            _hi_cat = "refrigerators"
        elif any(x in q_low_hi for x in ["air condition","aircon","split"," ac ","air-con","cassette","heat pump","window ac","window unit","portable ac"]):
            _hi_cat = "air-conditioners"
        elif any(x in q_low_hi for x in ["washing","washer","wm ","wfqy","wfpv"]):
            _hi_cat = "washing-machines"
        elif any(x in q_low_hi for x in ["microwave","oven","cooker","dishwasher"]):
            _hi_cat = "cooking"

        # Hisense model slug: strip brand word, lowercase, hyphens
        _hi_slug = _re_hi.sub(r'[^a-z0-9\-]+', '-',
                               query[len("hisense"):].strip().lower()).strip('-')
        _hi_slug = _re_hi.sub(r'-+', '-', _hi_slug)

        urls = []
        seen = set()
        def _hiadd(u):
            if u not in seen: seen.add(u); urls.append(u)

        # Global Hisense site — correct category slug first
        _hiadd(f"https://global.hisense.com/products/{_hi_cat}/{_hi_slug}/")
        # South Africa (has clean product pages)
        _hiadd(f"https://hisense.co.za/product/{_hi_slug}/")
        # USA Hisense (if TV or appliance)
        if _hi_cat == "tvs":
            _hiadd(f"https://www.hisense-usa.com/televisions/{_hi_slug}/")
        elif _hi_cat == "refrigerators":
            _hiadd(f"https://www.hisense-usa.com/refrigerators/{_hi_slug}/")
        # UK Hisense search (the deep numeric URL requires search — use their search page)
        _hiadd(f"https://uk.hisense.com/search?text={q_enc_hi}")
        # Global search fallback
        _hiadd(f"https://global.hisense.com/search?q={q_enc_hi}")
        return urls

    patterns = _BRAND_URL_PATTERNS.get(brand, [
        f"https://www.{brand}.com/products/{{slug}}/",
        f"https://www.{brand}.com/uk/products/{{slug}}/",
        f"https://www.{brand}.com/smartphones/{{slug}}/",
    ])

    urls = []
    seen = set()
    for p in patterns:
        try:
            u = p.format(**variants)
        except KeyError:
            u = p.format(slug=slug)
        if u not in seen:
            seen.add(u)
            urls.append(u)

    return urls


# ── Layer 2: Multi-engine search with bypass ────────────────────────────────

_SEARCH_ENGINES = [
    # (url_template, result_href_pattern, needs_decode)
    ("https://html.duckduckgo.com/html/?q={q}",             r'href="(https?://[^"]+)"', False),
    ("https://lite.duckduckgo.com/lite/?q={q}",             r'href="(https?://[^"]+)"', False),
    ("https://www.bing.com/search?q={q}&setmkt=en-US",      r'"url":"(https?://[^"]+)"', False),
    ("https://search.yahoo.com/search?p={q}",               r'href="(https?://[^"]+)"', False),
    ("https://api.mojeek.com/search?q={q}&t=10&fmt=json",   r'"url":"(https?://[^"]+)"', False),
    ("https://www.startpage.com/sp/search?query={q}",       r'href="(https?://[^"]+)"', False),
]

def _search_for_urls(query: str, brand_name: str) -> list:
    """
    Try multiple search engines with rotating UAs, sessions, and delays.
    Returns a deduplicated list of candidate URLs belonging to the brand.
    """
    import re, urllib.parse, requests

    candidates = []
    encoded_q  = urllib.parse.quote_plus(query + " official site")

    _BRAND_DOMAINS = {
        "samsung":  ["samsung.com"],
        "tecno":    ["tecno-mobile.com","tecno.com"],
        "infinix":  ["infinixmobility.com","infinix.com"],
        "itel":     ["itel-mobile.com","itel.com"],
        "realme":   ["realme.com"],
        "honor":    ["hihonor.com","honor.com"],
        "oneplus":  ["oneplus.com"],
        "xiaomi":   ["mi.com","xiaomi.com"],
        "poco":     ["poco.net","mi.com"],
        "google":   ["store.google.com","google.com"],
        "apple":    ["apple.com","store.apple.com"],
        "huawei":   ["solar.huawei.com","consumer.huawei.com","huawei.com"],
        "sony":     ["sony.com","store.sony.com","sony.co.uk","sony.co.za"],
        "nokia":    ["nokia.com"],
        "motorola": ["motorola.com"],
        "vivo":     ["vivo.com"],
        "oppo":     ["oppo.com"],
        "asus":     ["asus.com"],
        "tcl":      ["tcl.com"],
        "zte":      ["ztedevices.com","zte.com"],
        "skyworth": ["skyworth.com","skyworth.co.za"],
        "daikin":    ["daikin.co.uk","daikin.com","daikin-me.com","daikin.com.ng"],
        "panasonic": ["panasonic.com","shop.panasonic.com"],
        "midea":     ["midea.com","midea.co.za"],
        "gree":      ["gree.com","greecomfort.com","gree-global.com"],
        "haier":     ["haier.com","thermocool.com.ng"],
        "bosch":     ["bosch-home.com"],
        "whirlpool": ["whirlpool.com","whirlpool.co.za"],
        "beko":      ["beko.com","beko.co.uk"],
        "electrolux":["electrolux.com","electrolux.co.za","electrolux.co.uk"],
        "indesit":   ["indesit.com"],
        "jbl":       ["jbl.com","global.jbl.com"],
        "bose":      ["bose.com","bose.co.uk","bose.co.za"],
        "sonos":     ["sonos.com"],
        "yamaha":    ["yamaha.com","uk.yamaha.com","usa.yamaha.com"],
        "marshall":  ["marshallheadphones.com"],
        "harman":    ["harmankardon.com"],
        "anker":     ["soundcore.com","anker.com"],
        "longi":     ["longi-solar.com","longi.com"],
        "canadian":  ["canadiansolar.com"],
        "trina":     ["trinasolar.com"],
        "jasolar":   ["jasolar.com"],
        "ja":        ["jasolar.com"],
        "sma":       ["sma.de","sma-sunny.com"],
        "victron":   ["victronenergy.com"],
        "luminous":  ["luminousindia.com","luminous-global.com"],
        "felicity":  ["felicitysolarng.com","felicitysolar.com"],
        "suntech":   ["suntech-power.com"],
        "risen":     ["risen-solar.com"],
        "scanfrost": ["scanfrost.com.ng"],
        "nexus":     ["nexuselectronics.com.ng"],
        "polystar":  ["polystar.com.ng"],
        "bruhm":     ["bruhmafrica.com"],
        "lg":       ["lg.com"],
        "hisense":  ["uk.hisense.com","global.hisense.com","hisense.co.za","hisense-usa.com","hisense.com"],
        "growatt":  ["en.growatt.com","growatt.com"],
        "deye":     ["deyeinverter.com","deye.com.cn"],
        "jinko":    ["jinkosolar.com"],
        "pylontech":["en.pylontech.com.cn","pylontech.com.cn"],
        "actiu":    ["actiu.com","catalogo.actiu.com"],
        "maxi":     ["maxiappliances.com","maxinigeria.com"],
        "tsty":     ["tsty.com.cn"],
    }
    accepted_domains = _BRAND_DOMAINS.get(brand_name,
                                          [f"{brand_name}.com", f"www.{brand_name}.com"])
    primary_domain = accepted_domains[0]
    site_q = urllib.parse.quote_plus(f"site:{primary_domain} {query}")

    attempts = []
    for tmpl, pat, _ in _SEARCH_ENGINES:
        attempts.append((tmpl.format(q=encoded_q), pat))
        attempts.append((tmpl.format(q=site_q),    pat))

    def _is_brand_url(u):
        u_low = u.lower()
        return (any(d in u_low for d in accepted_domains)
                and not any(x in u_low for x in
                            ["duckduckgo","bing.com","yahoo.","google.",
                             "cache:","translate","mojeek","startpage",
                             "/search?","login","account"]))

    def _search_one(search_url, pattern):
        found_urls = []
        try:
            sess = requests.Session()
            resp = sess.get(search_url, headers=_headers(), timeout=8,
                            allow_redirects=True)
            if resp.status_code == 403:
                # IP-level block — cloudscraper won't help, bail immediately
                if b"not in allowlist" in resp.content:
                    return found_urls
                try:
                    import cloudscraper
                    cs   = cloudscraper.create_scraper(
                        browser={"browser":"chrome","platform":"windows"})
                    resp = cs.get(search_url, timeout=12)
                except Exception:
                    return found_urls
            for u in re.findall(pattern, resp.text):
                u = u.split("&")[0]
                if _is_brand_url(u) and u.startswith("http"):
                    found_urls.append(u)
        except Exception:
            pass
        return found_urls

    from concurrent.futures import ThreadPoolExecutor, as_completed as _se_done
    seen_u = set()
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(_search_one, su, pat): (su, pat)
                for su, pat in attempts}
        for fut in _se_done(futs):
            for u in fut.result():
                if u not in seen_u:
                    seen_u.add(u)
                    candidates.append(u)
            if len(candidates) >= 5:
                break

    return candidates

# ── Layer 3: requests fetch (with cloudscraper fallback) ────────────────────

# Domains that require Playwright immediately — requests/cloudscraper always fail
_PLAYWRIGHT_ONLY_DOMAINS = {
    "noon.com", "www.noon.com",
}

# Noon Arabic-locale endpoints block Playwright too.
# Rewrite to English locale — same products, more permissive bot detection.
_NOON_AR_TO_EN = {
    "/egypt-ar/":   "/egypt-en/",
    "/saudi-ar/":   "/saudi-en/",
    "/uae-ar/":     "/uae-en/",
    "/kuwait-ar/":  "/kuwait-en/",
    "/bahrain-ar/": "/bahrain-en/",
    "/oman-ar/":    "/oman-en/",
    "/qatar-ar/":   "/qatar-en/",
    "/jordan-ar/":  "/jordan-en/",
    "/iraq-ar/":    "/iraq-en/",
}

def _normalise_noon_url(url: str) -> str:
    """Rewrite noon Arabic-locale URLs to English-locale equivalents."""
    for ar, en in _NOON_AR_TO_EN.items():
        if ar in url:
            return url.replace(ar, en, 1)
    return url


def _scrape_noon_via_api(url: str) -> dict:
    """
    Scrape a Noon product using their catalog API endpoints.
    This completely bypasses Akamai Bot Manager which blocks HTML scraping.

    Noon product URLs contain a SKU code: /N43384078A/p/
    The catalog API at noon.com/_svc/catalog/api/ doesn't go through the WAF.
    Tries v3 then v2 API, returns empty dict on failure.
    """
    import re, json
    try:
        import requests as _req
    except ImportError:
        return {}

    url = _normalise_noon_url(url)

    # Extract SKU (noon IDs: N followed by digits+letters, ending in A/B/etc.)
    sku_m = re.search(r'/([A-Z][0-9A-Z]{6,14}[A-Z0-9])/p[/?]', url)
    if not sku_m:
        return {}
    sku = sku_m.group(1)

    # Extract region from URL path  e.g. egypt-en, uae-en, saudi-en
    path_m = re.search(r'noon\.com/([a-z]+-[a-z]+)/', url)
    region = path_m.group(1) if path_m else "egypt-en"

    # API-realistic headers — these endpoints accept JSON and are less protected
    api_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": f"https://www.noon.com/{region}/",
        "Origin": "https://www.noon.com",
        "x-locale": region,
        "x-country-code": region.split("-")[0].upper() if "-" in region else "EG",
    }

    # Try multiple API endpoint variants
    api_attempts = [
        f"https://www.noon.com/_svc/catalog/api/v3/u/{region}/pdp?type=sku&id={sku}",
        f"https://www.noon.com/_svc/catalog/api/v2/u/{region}/product/{sku}",
        f"https://www.noon.com/_svc/catalog/api/v3/u/{region}/product?type=sku&id={sku}",
    ]

    data = None
    for api_url in api_attempts:
        try:
            resp = _req.get(api_url, headers=api_headers, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                break
        except Exception:
            continue

    if not data:
        return {}

    # Parse the API response into our canonical result dict
    result = {
        "URL": url, "Website": "www.noon.com",
        "Product Name": "", "Brand": "", "Price": "", "Currency": "",
        "Category": "", "Key Features": "", "About This Item": "",
        "Tech & Additional Info": "", "Description": "",
        "Rating": "", "Reviews Count": "",
        "SKU": sku, "GTIN": "", "Availability": "", "Images": "",
        "Warranty": "", "Weight": "", "Dimensions": "", "Colour": "",
    }

    # Navigate nested response — v3 wraps in {"status":"ok","model":{...},"offers":[...]}
    model   = data.get("model") or data.get("product") or data.get("data") or {}
    offers  = data.get("offers") or []
    if isinstance(offers, list) and offers:
        offer = offers[0]
    elif isinstance(offers, dict):
        offer = offers
    else:
        offer = {}

    # Product Name
    result["Product Name"] = (model.get("name") or model.get("title") or
                              data.get("name") or "").strip()
    # Brand
    brand = model.get("brand") or {}
    result["Brand"] = (brand.get("name") if isinstance(brand, dict) else str(brand)).strip()

    # Price
    price = (offer.get("price") or offer.get("selling_price") or
             model.get("price") or "")
    result["Price"]    = str(price).strip()
    result["Currency"] = (offer.get("currency") or offer.get("currency_code") or "").strip()

    # SKU / model number
    result["SKU"] = (model.get("sku") or model.get("model_number") or sku).strip()

    # GTIN / barcode
    gtin_raw = (model.get("gtin") or model.get("ean") or model.get("barcode") or
                model.get("upc") or "")
    if gtin_raw:
        result["GTIN"] = _validate_gtin_str(str(gtin_raw))

    # Category
    cats = model.get("categories") or model.get("category_path") or []
    if isinstance(cats, list):
        result["Category"] = " > ".join(
            c.get("name","") if isinstance(c,dict) else str(c)
            for c in cats if c
        )
    elif isinstance(cats, str):
        result["Category"] = cats

    # Description
    result["Description"] = (model.get("description") or
                             model.get("long_description") or "")[:1000]

    # Key Features / Highlights
    highlights = (model.get("highlights") or model.get("key_features") or
                  model.get("features") or [])
    if isinstance(highlights, list):
        result["Key Features"] = "; ".join(str(h) for h in highlights if h)[:500]
    elif isinstance(highlights, str):
        result["Key Features"] = highlights[:500]

    # Specifications
    specs = model.get("specs") or model.get("attributes") or model.get("specifications") or []
    spec_parts = []
    if isinstance(specs, list):
        for s in specs:
            if isinstance(s, dict):
                label = s.get("label") or s.get("key") or s.get("name") or ""
                value = s.get("value") or s.get("val") or ""
                if label and value:
                    spec_parts.append(f"{label}: {value}")
    elif isinstance(specs, dict):
        for k, v in specs.items():
            spec_parts.append(f"{k}: {v}")
    result["Tech & Additional Info"] = "; ".join(spec_parts[:30])

    # Images — Noon uses Cloudinary
    images = (model.get("images") or model.get("image_keys") or
              model.get("image_urls") or [])
    img_urls = []
    for img in (images if isinstance(images, list) else [images]):
        if isinstance(img, dict):
            src = img.get("url") or img.get("key") or ""
        else:
            src = str(img)
        if src and src.startswith("http"):
            img_urls.append(src)
        elif src:
            # Noon image keys: convert to full Cloudinary URL
            img_urls.append(f"https://f.nooncdn.com/p/{src}")
    # Upgrade to HD
    hd_imgs = []
    for u in img_urls[:8]:
        import re as _re_img
        u = _re_img.sub(r'w_\d+', 'w_2000', u)
        u = _re_img.sub(r'q_\d+', 'q_100', u)
        hd_imgs.append(u)
    result["Images"] = ", ".join(hd_imgs)

    # Availability
    result["Availability"] = (offer.get("quantity_label") or
                               offer.get("availability") or
                               ("In Stock" if offer else ""))

    # Rating
    rating = model.get("average_rating") or model.get("rating") or ""
    result["Rating"] = str(rating) if rating else ""
    reviews = model.get("total_ratings") or model.get("reviews_count") or ""
    result["Reviews Count"] = str(reviews) if reviews else ""

    return result


def _is_fouani_url(url: str) -> bool:
    """Return True if the URL is a fouanistore.com product page."""
    return "fouanistore.com" in url.lower()


def _scrape_fouani(url: str) -> dict:
    """
    Scrape a Fouani product page via __NEXT_DATA__ JSON.

    NOTE: fouanistore.com returns 403 "Host not in allowlist" from all
    cloud/server IPs (Render, DigitalOcean, etc.) at the reverse-proxy level.
    Both requests and Playwright fail identically.  Return {} immediately
    to avoid burning timeout cycles, until the IP block is lifted.
    """
    return {}

def _fetch_html_requests(url: str) -> str:
    """
    Fetch page HTML using requests -> cloudscraper fallback.
    Returns raw HTML string, or raises on failure.
    Noon.com raises immediately to force Playwright escalation (Akamai protected).
    """
    import requests, urllib.parse as _up

    # Rewrite noon Arabic-locale URLs before any fetch
    url = _normalise_noon_url(url)

    # Domains that use Akamai/advanced bot protection — skip requests entirely
    netloc = _up.urlparse(url).netloc.lower().lstrip("www.")
    if netloc in _PLAYWRIGHT_ONLY_DOMAINS or any(d in netloc for d in _PLAYWRIGHT_ONLY_DOMAINS):
        raise IOError(f"Skipping requests for {netloc} — using Playwright directly")

    session = requests.Session()
    resp = session.get(url, headers=_headers(), timeout=15, allow_redirects=True)

    if resp.status_code in (403, 429, 503):
        # IP-level block ("Host not in allowlist") — cloudscraper won't help
        if b"not in allowlist" in resp.content:
            resp.raise_for_status()
        # Try cloudscraper
        try:
            import cloudscraper
            cs   = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "desktop": True})
            resp = cs.get(url, timeout=25)
        except Exception:
            resp.raise_for_status()   # re-raise original error

    resp.raise_for_status()
    return resp.text


# ── Layer 4: Playwright fetch ────────────────────────────────────────────────

def _ensure_playwright_browsers() -> bool:
    """
    Check that Playwright's Chromium browser is installed.
    If missing (common on Windows portable installs), attempt to install it
    automatically via `playwright install chromium`.
    Returns True if browsers are available, False otherwise.
    This is called once at startup and cached.
    """
    global _PLAYWRIGHT_AVAILABLE
    if _PLAYWRIGHT_AVAILABLE is not None:
        return _PLAYWRIGHT_AVAILABLE

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            # Try to get the executable path — raises if not installed
            info = pw.chromium.launch(headless=True)
            info.close()
        _PLAYWRIGHT_AVAILABLE = True
        return True
    except Exception as _e:
        err_str = str(_e).lower()
        # [WinError 2] / "executable doesn't exist" / "no such file"
        _is_missing = any(x in err_str for x in [
            "winerror 2", "winError 2", "[error 2]",
            "executable doesn't exist", "executable not found",
            "no such file", "cannot find the file",
            "browsertype.launch", "failed to launch",
        ])
        if not _is_missing:
            _PLAYWRIGHT_AVAILABLE = False
            return False

        # Browser binary missing — try to install it automatically
        try:
            import subprocess, sys
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                _PLAYWRIGHT_AVAILABLE = True
                return True
        except Exception:
            pass

        _PLAYWRIGHT_AVAILABLE = False
        return False


# Cache: None = not yet checked, True = available, False = unavailable
_PLAYWRIGHT_AVAILABLE = None


def _fetch_html_playwright(url: str, wait_ms: int = 3000) -> str:
    """
    Fetch a page with a headless Chromium browser.
    Handles JS rendering, Cloudflare challenges, and bot-detection.
    Returns full rendered HTML.

    On Windows portable installs where Playwright's Chromium is not present,
    raises a clear IOError with installation instructions rather than a cryptic
    [WinError 2] message.
    """
    # ── Check browser availability before attempting launch ──────────────────
    # This prevents the cryptic [WinError 2] on Windows portable installs.
    if not _ensure_playwright_browsers():
        raise IOError(
            "Playwright Chromium browser is not installed.\n\n"
            "To fix this, open a Command Prompt and run:\n"
            "    python -m playwright install chromium\n\n"
            "Or if using the portable .exe, run:\n"
            "    playwright install chromium\n\n"
            "This only needs to be done once."
        )
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    # Detect if this is a noon URL early so we can apply extra stealth
    _is_noon_url = "noon.com" in url.lower()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--no-first-run",
                "--disable-default-apps",
                # Extra stealth for Akamai detection
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )
        ctx = browser.new_context(
            user_agent=_random_ua(),
            viewport={"width": random.randint(1280, 1440),
                      "height": random.randint(768, 900)},
            locale="en-US",
            timezone_id="America/New_York",
            java_script_enabled=True,
            ignore_https_errors=True,
            # Extra headers that make Playwright look like a real browser
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            }
        )

        # Comprehensive automation signal masking
        ctx.add_init_script("""
            // Remove webdriver flag
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            // Add realistic plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    return [
                        {name:'Chrome PDF Plugin',filename:'internal-pdf-viewer',description:'Portable Document Format'},
                        {name:'Chrome PDF Viewer',filename:'mhjfbmdgcfjbbpaeojofohoefgiehjai',description:''},
                        {name:'Native Client',filename:'internal-nacl-plugin',description:''},
                    ];
                }
            });
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
            Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
            Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
            window.chrome = {
                runtime: {},
                loadTimes: function(){},
                csi: function(){},
                app: {}
            };
            // Correct permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        page = ctx.new_page()

        # Human-like mouse movement
        try:
            page.mouse.move(random.randint(100, 500), random.randint(100, 400))
        except Exception:
            pass

        try:
            import urllib.parse as _up3
            # Normalise noon Arabic-locale URLs before navigation
            url = _normalise_noon_url(url)
            _netloc = _up3.urlparse(url).netloc.lower().lstrip("www.")
            _is_noon = "noon.com" in _netloc

            if _is_noon:
                # ── Noon Akamai bypass: visit homepage first to get valid session ──
                # Akamai trusts requests from sessions that have visited the homepage.
                # Direct product page visits get blocked; homepage visits don't.
                _noon_region = _up3.urlparse(url).path.split('/')[1]  # e.g. egypt-en
                _noon_home = f"https://www.noon.com/{_noon_region}/"
                try:
                    page.goto(_noon_home, timeout=20000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)   # let Akamai set cookies
                    # Simulate human reading the homepage briefly
                    page.evaluate("window.scrollBy(0, 300)")
                    page.wait_for_timeout(800)
                except Exception:
                    pass   # if homepage fails, still try product page
                # Now navigate to the product page — Akamai cookie is set
                page.set_extra_http_headers({
                    "Referer":          _noon_home,
                    "Accept-Language":  "en-US,en;q=0.9",
                })
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(wait_ms + 2000)
                page.evaluate("window.scrollBy(0, 500)")
                page.wait_for_timeout(600)
                page.evaluate("window.scrollBy(0, -100)")
                page.wait_for_timeout(400)
            else:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(wait_ms)
                page.evaluate("window.scrollBy(0, 400)")
                page.wait_for_timeout(400)
            html = page.content()
        except PWTimeout:
            html = page.content()  # return whatever loaded
        finally:
            browser.close()

    return html


# ── Page parser (shared by all fetch layers) ─────────────────────────────────

# Noise keywords that indicate a page is NOT a product detail page
_NON_PRODUCT_TITLE_PATTERNS = [
    r'^\s*\|', r'\|\s*$',          # "| Samsung UK"  /  "Samsung | Home"
    r'^home\b', r'^homepage',
    r'search results', r'category',
    r'sign in', r'log in', r'register',
    r'cart', r'basket', r'checkout',
    r'contact us', r'about us', r'support',
    r'sitemap', r'privacy', r'terms',
    r'404', r'not found', r'error',
    r'official\s*(site|website|store|page|samsung|apple|nokia|sony|huawei|xiaomi)',
    r'^(official|welcome\s+to)',
    r'\b(uk|us|eu|global|international)\s*$',
    r'^(shop|store|buy|order)\b',
    r'all\s+products', r'our\s+range',
    r'\bwelcome\b', r'\bnewsletter\b',
    # Geographic/regional page titles (Samsung Africa, Middle East, etc.)
    r'^africa\s*$', r'^middle\s+east\s*$', r'^nigeria\s*$',
    r'^ghana\s*$', r'^kenya\s*$', r'^south\s+africa\s*$',
    r'^egypt\s*$', r'^morocco\s*$', r'^ethiopia\s*$',
    r'^(africa|asia|europe|america|oceania)\b',  # continent names alone
    r'^(north|south|east|west|central)\s+(africa|asia|america|europe)\s*$',
]

# Image URL patterns that indicate logo / icon / UI asset — never product images
_JUNK_IMAGE_PATTERNS = [
    'logo', 'icon', 'favicon', 'sprite', 'banner', 'bg-', 'background',
    'placeholder', 'blank', 'pixel', 'tracking', 'spacer', 'arrow',
    'button', 'badge', 'star', 'rating', 'social', 'twitter', 'facebook',
    'clientlib', 'resources/images', 'ui/', 'assets/img/icon',
    '/etc.client', 'common/resources',
]

# Minimum image dimension heuristic from URL — reject tiny thumbnails
_JUNK_SIZE_PATTERNS = [
    r'[_-](\d{1,2})x(\d{1,2})[_.]',   # _16x16.  _32x32.
    r'[_-]thumb',
    r'\.gif$',
]


def _has_template_pollution(r: dict) -> bool:
    """Return True if result contains un-rendered JS template strings {{...}}."""
    import re as _re_tp
    _TMPL = _re_tp.compile(r'\{\{[^}]{3,}\}\}')
    count = sum(len(_TMPL.findall(str(r.get(f, "") or "")))
                for f in ("Key Features", "Price", "Description", "Tech & Additional Info"))
    return count >= 2


def _is_product_page(result: dict, query: str) -> bool:
    """
    Return True only if the parsed result looks like a genuine product detail page.
    Rejects homepages, category pages, search results, nav-only pages,
    and pages whose title shares no words with the search query.
    """
    import re
    name  = result.get("Product Name", "").strip()
    brand = query.split()[0].lower()

    # Must have a product name that doesn't look like a site title
    if not name or len(name) < 3:
        return False
    for pat in _NON_PRODUCT_TITLE_PATTERNS:
        if re.search(pat, name, re.IGNORECASE):
            return False
    # Name must not be just the brand name alone
    if name.lower().rstrip(".:,") == brand:
        return False

    # ── Query-relevance check ────────────────────────────────────────────
    # The product name must share meaningful words with the query.
    # If the query contains a model identifier (digit-containing word like "a06",
    # "s24", "fold7") the product name MUST contain that model word too.
    # This prevents "Galaxy Z Fold7" being accepted for query "Samsung Galaxy A06 Black".
    import re as _re_qr
    query_words = {w.lower() for w in query.split() if len(w) > 3}
    name_lower  = name.lower()

    if query_words and not any(w in name_lower for w in query_words):
        return False

    # Stricter check: if query has model words (digits or short alphanumeric codes),
    # the product name must contain at least one of them.
    # "A06", "S24", "Fold7", "M35", "128GB" etc. are model identifiers.
    model_words = {w.lower() for w in query.split()
                   if _re_qr.search(r'\d', w)}   # any word with a digit
    if model_words:
        if not any(mw in name_lower for mw in model_words):
            return False   # e.g. "Galaxy Z Fold7" rejected for query "Samsung Galaxy A06 Black"

    # ── Template pollution check ─────────────────────────────────────────
    if _has_template_pollution(result):
        return False  # JS not yet executed — needs Playwright

    # ── Content quality check ────────────────────────────────────────────
    # GTIN alone is not sufficient — it can be scraped from unrelated page content.
    # Require at least one of: description, features, images, SKU, or price.
    has_real_content = any([
        result.get("Key Features"),
        result.get("Tech & Additional Info"),
        result.get("Description") and len(result.get("Description", "")) > 60,
        result.get("SKU"),
        result.get("Price"),
        result.get("Images"),
    ])
    return has_real_content


def _filter_product_images(imgs: list, query: str) -> list:
    """
    Remove logos, icons, UI assets, and unrelated images.
    Keep only images that are plausibly product photos.
    """
    import re
    query_words = [w.lower() for w in query.split() if len(w) > 2]
    kept = []
    for src in imgs:
        src_low = src.lower()
        # Reject known junk patterns
        if any(p in src_low for p in _JUNK_IMAGE_PATTERNS):
            continue
        # Reject obviously tiny images from URL
        junk_size = any(re.search(p, src_low) for p in _JUNK_SIZE_PATTERNS)
        if junk_size:
            continue
        # Must be a proper image file
        if not any(ext in src_low for ext in ['.jpg','.jpeg','.png','.webp']):
            continue
        kept.append(src)
    # If filtering removed everything, return original minus definite junk
    if not kept:
        kept = [s for s in imgs if not any(p in s.lower() for p in
                ['logo','icon','favicon','clientlib','resources/images'])]
    return kept[:8]


def _validate_gtin(v) -> str:
    """Alias for _validate_gtin_str — used by _extract_gtin_from_page."""
    return _validate_gtin_str(v)


def _extract_gtin_from_page(html: str, url: str) -> str:
    """
    Dedicated GTIN/EAN/UPC/Barcode extractor — works on any website.
    6 extraction methods tried in order:
      1. JSON-LD structured data
      2. itemprop attributes on any tag (span/div/td/li/meta)
      3. Meta tags (og:upc, product:ean, etc.)
      4. Table rows + definition lists (broad label matching)
      5. Regex scan of raw HTML (labelled patterns)
      6. Contextual EAN-13 checksum scan near product keywords
    """
    import re, json as _json
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")

    # 1. JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = _json.loads(script.string or "")
            if isinstance(data, list): data = data[0] if data else {}
            if isinstance(data, dict):
                for gf in ("gtin13","gtin14","gtin12","gtin8","gtin","ean","upc","barcode"):
                    v = _validate_gtin(data.get(gf, ""))
                    if v: return v
                offers = data.get("offers", {})
                if isinstance(offers, list) and offers: offers = offers[0]
                if isinstance(offers, dict):
                    for gf in ("gtin13","gtin14","gtin12","gtin8","gtin","ean","upc"):
                        v = _validate_gtin(offers.get(gf, ""))
                        if v: return v
        except Exception:
            pass

    # 2. itemprop on ANY tag
    _GTIN_IPROPS = frozenset({
        "gtin","gtin13","gtin14","gtin12","gtin8",
        "ean","upc","barcode","identifier","productid","productID",
    })
    for tag in soup.find_all(attrs={"itemprop": True}):
        ip = re.sub(r'[\s_\-]', '', tag.get("itemprop", "")).lower()
        if ip in _GTIN_IPROPS:
            raw = tag.get("content", "") or tag.get_text(strip=True)
            v = _validate_gtin(raw)
            if v: return v

    # 3. Meta tags
    _META_KEYS = frozenset({
        "gtin","gtin13","gtin14","gtin12","gtin8","ean","upc","barcode",
        "product:ean","product:upc","product:gtin","og:upc","og:ean",
        "twitter:data1","item_number","product_id",
    })
    for tag in soup.find_all("meta"):
        key = (tag.get("property","") or tag.get("name","") or "").lower().strip()
        if key in _META_KEYS:
            v = _validate_gtin(tag.get("content",""))
            if v: return v

    # 4. Table rows and definition lists — broad label matching
    _GTIN_LABELS = (
        "ean","upc","gtin","barcode","barcode no","barcode number",
        "ean code","ean-13","ean13","upc code","gtin code","gtin no",
        "product code","item code","stock code","part no","part number",
        "article number","article no","reference","isbn",
    )
    for row in soup.select("table tr"):
        cells = row.select("td, th")
        if len(cells) >= 2:
            label = cells[0].get_text(strip=True).lower()
            value = cells[1].get_text(strip=True)
            if any(lbl in label for lbl in _GTIN_LABELS):
                v = _validate_gtin(value)
                if v: return v
    for dl in soup.select("dl"):
        for dt, dd in zip(dl.select("dt"), dl.select("dd")):
            label = dt.get_text(strip=True).lower()
            value = dd.get_text(strip=True)
            if any(lbl in label for lbl in _GTIN_LABELS):
                v = _validate_gtin(value)
                if v: return v

    # 5. Regex scan — labelled patterns in raw HTML
    label_re = re.compile(
        r'(?:GTIN|EAN|UPC|Barcode|Barcode\s*No|Barcode\s*Number|'
        r'EAN[\s\-]?13|EAN[\s\-]?Code|UPC[\s\-]?Code|GTIN[\s\-]?Code|'
        r'GTIN[\s\-]?No|Product[\s\-]?Code|Item[\s\-]?No|'
        r'Part[\s\-]?No|Article[\s\-]?No)[^\d]{0,15}(\d{8,14})',
        re.IGNORECASE
    )
    m = label_re.search(html)
    if m:
        v = _validate_gtin(m.group(1))
        if v: return v

    # 6. Contextual EAN-13 checksum scan near product keywords
    context_re = re.compile(
        r'(?:product|item|sku|model|phone|smartphone|mobile|tablet|'
        r'galaxy|iphone|spark|note|pixel|find|edge|nova|reno|a\d+|s\d+)'
        r'.{0,300}?\b(\d{12,13})\b',
        re.IGNORECASE | re.DOTALL
    )
    for m in context_re.finditer(html[:80000]):
        v = _validate_gtin(m.group(1))
        if v: return v

    return ""



def _lookup_gtin_by_model(sku: str, brand: str, product_name: str) -> str:
    """
    Look up GTIN via free barcode databases using model number.
    Tries: barcodelookup.com scrape, buycott.com, Open Food Facts (electronics subset).
    """
    import re
    try:
        import requests as _req
    except ImportError:
        return ""

    if not sku and not product_name:
        return ""

    search_term = sku or product_name
    attempts = [
        f"https://www.barcodelookup.com/search#text={search_term.replace(' ','+')}",
        f"https://www.buycott.com/upc/search/{search_term.replace(' ','+')}",
    ]

    for url in attempts:
        try:
            resp = _req.get(url, headers=_headers(), timeout=10)
            m = re.search(r'\b(\d{12,13})\b', resp.text)
            if m:
                candidate = m.group(1)
                digits = [int(d) for d in candidate]
                if len(digits) == 13:
                    checksum = (10 - sum(d * (1 if i % 2 == 0 else 3)
                                         for i, d in enumerate(digits[:-1])) % 10) % 10
                    if checksum == digits[-1]:
                        return candidate
        except Exception:
            continue

    return ""


def _parse_product_html(html: str, url: str) -> dict:
    """
    Parse product page HTML -> canonical result dict.
    Priority: JSON-LD structured data -> CSS selectors -> meta tags.
    Applies strict product-page validation and image filtering.
    """
    import re as _re, json as _json, urllib.parse
    from bs4 import BeautifulSoup

    result = {
        "URL": url, "Website": urllib.parse.urlparse(url).netloc,
        "Product Name": "", "Brand": "", "Price": "", "Currency": "",
        "Category": "", "Key Features": "", "About This Item": "",
        "Tech & Additional Info": "", "Description": "",
        "Rating": "", "Reviews Count": "",
        "SKU": "", "GTIN": "", "Availability": "", "Images": "",
        "Warranty": "", "Weight": "", "Dimensions": "", "Colour": "",
    }

    soup = BeautifulSoup(html, "lxml")
    base = urllib.parse.urlparse(url).scheme + "://" + urllib.parse.urlparse(url).netloc

    # ── JSON-LD — extracted BEFORE stripping scripts ──────────────────────
    jsonld_data = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            d = _json.loads(script.string or "")
            if isinstance(d, list):   jsonld_data.extend(d)
            elif isinstance(d, dict): jsonld_data.append(d)
        except Exception:
            pass

    # Skip definite non-product schema types; accept everything else
    # (better to over-extract from unknown types than miss a product)
    _NON_PRODUCT_LD = {"WebSite","SiteNavigationElement","Organization",
                       "BreadcrumbList","WebPage","SearchResultsPage",
                       "ItemList","FAQPage","Article","NewsArticle",
                       "WebApplication","VideoObject","ImageObject",
                       "AggregateRating","Review","Person","Event"}
    for data in jsonld_data:
        if not isinstance(data, dict): continue
        t = data.get("@type","")
        if isinstance(t, list): t = t[0] if t else ""
        # Normalise all prefix/URI variants to bare type name:
        # "http://schema.org/Product" -> "Product"
        # "schema:Product"            -> "Product"
        # "Product"                   -> "Product"
        t_norm = str(t).split("/")[-1].split(":")[-1].strip()
        if t_norm and t_norm in _NON_PRODUCT_LD:
            continue
        if not result["Product Name"] and data.get("name"):
            result["Product Name"] = str(data["name"]).strip()
        if not result["Brand"]:
            b = data.get("brand",{})
            if isinstance(b, dict): b = b.get("name","")
            if b: result["Brand"] = str(b).strip()
        if not result["SKU"] and data.get("sku"):
            result["SKU"] = str(data["sku"]).strip()
        if not result["GTIN"]:
            for gf in ("gtin13","gtin14","gtin12","gtin8","gtin","ean","upc"):
                v = _validate_gtin_str(str(data.get(gf,"")))
                if v: result["GTIN"] = v; break
        ld_desc = str(data.get("description","")).strip()
        if ld_desc and len(ld_desc) > len(result.get("Description","")):
            result["Description"] = ld_desc[:1000]
        if not result["Price"]:
            offers = data.get("offers",{})
            if isinstance(offers, list) and offers: offers = offers[0]
            if isinstance(offers, dict):
                raw_price = str(offers.get("price","")).strip()
                # Reject template variables (e.g. Samsung's {{item.finalPrice}})
                if raw_price and not _re.search(r'\{\{', raw_price):
                    result["Price"]    = raw_price
                    result["Currency"] = str(offers.get("priceCurrency",""))
                # GTIN can also live inside offers
                if not result["GTIN"]:
                    for gf in ("gtin13","gtin14","gtin12","gtin8","gtin","ean","upc"):
                        v = _validate_gtin_str(str(offers.get(gf,"")))
                        if v: result["GTIN"] = v; break
        # Images from JSON-LD
        imgs_ld = result["Images"].split(", ") if result["Images"] else []
        for key in ("image","images"):
            val = data.get(key,[])
            if isinstance(val, str): val = [val]
            for src in val:
                if isinstance(src, dict): src = src.get("url","")
                if src and src not in imgs_ld:
                    imgs_ld.append(str(src))
        result["Images"] = ", ".join(imgs_ld[:8])
        # additionalProperty -> specs
        specs = result["Tech & Additional Info"].split("; ") if result["Tech & Additional Info"] else []
        for prop in data.get("additionalProperty",[]):
            if isinstance(prop, dict):
                n = prop.get("name",""); v = prop.get("value","")
                if n and v:
                    entry = f"{n}: {v}"
                    if entry not in specs: specs.append(entry)
        result["Tech & Additional Info"] = "; ".join(specs[:30])

    # ── Strip layout/nav noise before CSS parsing ────────────────────────
    # Remove navigation, header, footer, and any element whose class/id
    # strongly suggests it is site chrome rather than product content.
    # NOTE: do NOT add [class*='nav'] here — many brand sites (e.g. Samsung)
    # wrap the H1 product title in elements whose class contains "nav"
    # (e.g. product-navigation-container). JSON-LD already extracted the name
    # but the CSS fallback selectors still need the H1 to be in the DOM.
    for tag in soup(["script","style","noscript","svg","path","footer","aside"]):
        tag.decompose()
    for tag in soup.select("header, nav, "
                            "[class*='cookie'], [class*='modal'], "
                            "[class*='popup'], [class*='overlay'], "
                            "[class*='also-bought'], [class*='recently-viewed']"):
        tag.decompose()

    # ── Product Name ─────────────────────────────────────────────────────
    if not result["Product Name"]:
        netloc_lower = urllib.parse.urlparse(url).netloc.lower()
        # Brand-specific + generic product name selectors
        _name_sels = [
            # itemprop (schema.org — works on any site)
            "[itemprop='name']",
            # Samsung africa_en / global
            "h1.pdp-title", "h1[class*='pdp__title']", "h1[class*='pdp-title']",
            "[class*='product__name'] h1", "[class*='pd-title'] h1",
            # Noon
            "[data-testid='product-name']", "h1[class*='productTitle']",
            "h1[class*='product-name']", "[class*='productName'] h1",
            # Nokia
            "h1[class*='heading']", ".product-header__title",
            # Tecno / Infinix / Itel
            ".product-name h1", "h1.product-title", "h1.product-name",
            # Apple
            ".hero-headline", ".product-hero h1", "h1[class*='hero']",
            # Generic (broad)
            "h1[class*='pdp']", "h1[class*='product']",
            "#product-title", "#productTitle", "#product-name",
            ".product__title",
            "[class*='product-detail'] h1", "[class*='product-info'] h1",
            "[class*='product-page'] h1",
            # Amazon
            "#productTitle",
            # Last resort: any h1
            "h1",
        ]
        for sel in _name_sels:
            el = soup.select_one(sel)
            if el:
                txt = el.get_text(" ", strip=True)
                if txt and len(txt) > 3 and len(txt) < 250:
                    result["Product Name"] = txt; break

    # Only use og:title if it looks like a product (contains model-number-like words)
    if not result["Product Name"]:
        og = soup.find("meta", property="og:title")
        if og:
            t = og.get("content","").strip()
            # Reject if it looks like a site/page title
            is_junk = any(_re.search(p, t, _re.IGNORECASE)
                          for p in _NON_PRODUCT_TITLE_PATTERNS)
            if t and not is_junk:
                result["Product Name"] = t

    # Last resort: <title> — aggressively cleaned
    if not result["Product Name"]:
        t_tag = soup.find("title")
        if t_tag:
            raw = t_tag.get_text(strip=True)
            # Remove site name suffix/prefix (anything after | or –)
            for sep in ["|", "–", "—", "-", ":"]:
                parts = raw.split(sep)
                if len(parts) > 1:
                    # Pick the longest part that isn't a brand-only string
                    candidate = max(parts, key=len).strip()
                    if len(candidate) > 5:
                        raw = candidate
                        break
            is_junk = any(_re.search(p, raw, _re.IGNORECASE)
                          for p in _NON_PRODUCT_TITLE_PATTERNS)
            if raw and not is_junk:
                result["Product Name"] = raw

    # ── Brand ─────────────────────────────────────────────────────────────
    if not result["Brand"]:
        for sel in ["[itemprop='brand']",
                    "meta[property='product:brand']",
                    "meta[name='brand']",
                    ".product-brand","[class*='brand-name']"]:
            el = soup.select_one(sel)
            if el:
                b = el.get("content","") or el.get_text(strip=True)
                b = b.strip()
                if b and len(b) < 40: result["Brand"] = b; break

    # ── Price ─────────────────────────────────────────────────────────────
    if not result["Price"]:
        for sel in ["[itemprop='price']",
                    "meta[property='product:price:amount']",
                    ".price__current",".pdp-price",
                    "[class*='price--final']","[class*='price--sale']",
                    "[class*='current-price']","[class*='selling-price']",
                    "[class*='offer-price']"]:
            el = soup.select_one(sel)
            if el:
                p = el.get("content","") or el.get_text(strip=True)
                p = _re.sub(r'[^\d.,]','',p).strip()
                if p and len(p) <= 10: result["Price"] = p; break

    # ── Images — strict filtering ─────────────────────────────────────────
    all_imgs = result["Images"].split(", ") if result["Images"] else []

    # og:image (high priority — usually the hero product shot)
    for og in soup.find_all("meta", property="og:image"):
        src = og.get("content","").strip()
        if src and src not in all_imgs: all_imgs.append(src)

    # Product-specific image containers — brand-specific + generic
    for sel in [
        # Samsung africa_en gallery
        "[class*='pdp__gallery'] img", "[class*='pdp-gallery'] img",
        "[class*='product-gallery'] img",
        # Noon (Cloudinary images)
        "[class*='productImage'] img", "[data-testid='product-image'] img",
        # Generic high-priority
        "[class*='gallery'] img",
        "[class*='product-image'] img",
        "[class*='pdp-image'] img",
        "[class*='product-photo'] img",
        "[class*='product-media'] img",
        "[id*='gallery'] img",
        "[id*='product-image'] img",
        ".swiper-slide img",
        "img[itemprop='image']",
        "img[data-zoom-image]",
        "[class*='product-detail'] img",
        "[class*='product-viewer'] img",
        # Samsung product description/story/marketing images
        "[class*='product-story'] img",
        "[class*='product-content'] img",
        "[class*='pdp-description'] img",
        "[class*='feature-image'] img",
        "[class*='highlight'] img",
        # Amazon
        "#imgTagWrappingDiv img", "#altImages img", "#main-image img",
    ]:
        for img in soup.select(sel):
            srcset = img.get("srcset","") or img.get("data-srcset","")
            if srcset:
                parts = [p.strip().split()[0] for p in srcset.split(",") if p.strip()]
                src = parts[-1] if parts else ""   # highest resolution
            else:
                src = (img.get("src") or img.get("data-src") or
                       img.get("data-lazy-src") or img.get("data-original") or "").strip()
            if not src: continue
            if src.startswith("//"): src = "https:" + src
            elif src.startswith("/"): src = base + src
            if src.startswith("http") and src not in all_imgs:
                all_imgs.append(src)
            if len(all_imgs) >= 12: break
        if len(all_imgs) >= 12: break

    # Apply strict filtering to remove logos/icons/junk
    result["Images"] = ", ".join(_filter_product_images(all_imgs, ""))

    # ── Description ──────────────────────────────────────────────────────
    # CSS description — keep longest found; run even if JSON-LD gave something shorter
    for sel in [
        "[itemprop='description']",
        # Samsung africa_en
        "[class*='pdp__description']", "[class*='pdp-description']",
        "[class*='product-summary__desc']",
        "[class*='pd-description'] p",
        # Noon
        "[data-testid='product-description']", "[class*='description-content']",
        # Nokia
        ".product-header__description",
        # Generic
        ".pdp-description", ".product-description",
        "[class*='product-detail__desc']",
        "[class*='product-overview']",
        "#product-description", "#description",
        "[class*='product-details'] p",
        "[class*='product-info'] p",
    ]:
        el = soup.select_one(sel)
        if el:
            t = el.get_text(" ", strip=True)
            if len(t) > max(60, len(result.get("Description",""))):
                result["Description"] = t[:1000]
    # Meta fallback only if still empty
    if not result["Description"]:
        for attr, key in [("property","og:description"),("name","description")]:
            el = soup.find("meta", {attr: key})
            if el:
                t = el.get("content","").strip()
                if len(t) > 30: result["Description"] = t; break

    # ── Key Features — strict: only from product content areas ───────────
    if not result["Key Features"]:
        feats = []
        # Only look inside product-specific containers to avoid nav scraping
        # Only match block-level wrappers (div/section/main/article/form)
        # — never headings or inline elements which don't contain the full feature list
        product_containers = [
            el for el in soup.select(
                "div[class*='product-detail'], div[class*='pdp'],  "
                "div[class*='product-info'], div[class*='product-page'], "
                "div[class*='product-content'], section[class*='product'], "
                "main[class*='product'], article[class*='product'], "
                "div[id*='product-detail'], div[id*='product-info'], "
                "div[id*='product-content'], main"
            )
            # Must be a real container: at least 200 chars of text
            if len(el.get_text()) > 200
        ]
        search_scope = product_containers if product_containers else [soup]

        for scope in search_scope:
            for sel in [
                # Samsung africa_en specific
                "[class*='pdp__feature'] li", "[class*='pdp-feature'] li",
                "[class*='key-feature'] li", "[class*='keyFeature'] li",
                "[class*='short-description'] li",
                "[class*='pd-description__feature'] li",
                # Noon specific
                "[class*='feature-'] li", "[data-testid='feature-item']",
                ".sc-product-features li",
                # Nokia / Tecno / Infinix / Itel
                ".key-specs__item", ".spec-item", "[class*='spec-highlight']",
                ".product-specs li", "[class*='phone-spec'] li",
                # Apple
                ".feature-card li", ".tile-copy li",
                # Amazon
                "#feature-bullets li", "#featurebullets_feature_div li",
                ".a-unordered-list li",
                # Generic high-confidence
                "ul[class*='feature'] li", "ul[class*='spec'] li",
                "ul[class*='highlight'] li", "ul[class*='key'] li",
                "ul[class*='bullet'] li", "ul[class*='benefit'] li",
                "[class*='feature-item']", "[class*='spec-item']",
                "[class*='highlight-item']", "[class*='key-point']",
                ".specs-list li", "[class*='feature-list'] li",
                "[class*='selling-point']",
                "[class*='product-feature'] li", "[class*='product-highlight'] li",
                "[class*='product-spec'] li", "[class*='product-bullet'] li",
                # Generic fallback
                "ul li", "ol li",
            ]:
                for item in scope.select(sel):
                    txt = item.get_text(" ", strip=True)
                    # Reject nav-like items (very short, or contain links to other pages)
                    if (txt and 8 < len(txt) < 300
                            and txt not in feats
                            and not any(noise in txt.lower() for noise in
                                        ["discover","sign in","cart","checkout",
                                         "shop picks","get more","smartthings"])):
                        feats.append(txt)
                if feats: break
            if feats: break

        # Strip un-rendered JS template vars {{...}} before saving
        import re as _re_feat
        _TMPL_F = _re_feat.compile(r'\{\{[^}]+\}\}')
        clean_feats = []
        for feat in feats[:12]:
            # Skip features that contain template vars entirely or start with one
            if _TMPL_F.search(feat):
                continue
            if feat.strip() and len(feat.strip()) > 5:
                clean_feats.append(feat.strip())
        result["Key Features"] = "; ".join(clean_feats)

    # ── Specifications ────────────────────────────────────────────────────
    specs_raw = result["Tech & Additional Info"].split("; ") if result["Tech & Additional Info"] else []

    def _add_spec(label, value):
        entry = f"{label}: {value}"
        if entry not in specs_raw: specs_raw.append(entry)
        ll = label.lower()
        if "weight" in ll and not result["Weight"]: result["Weight"] = value
        if any(x in ll for x in ["dimension","size","measurement"]) and not result["Dimensions"]:
            result["Dimensions"] = value
        if "warranty" in ll and not result["Warranty"]: result["Warranty"] = value
        if any(x in ll for x in ["model","sku","item no","part no","model no"]) and not result["SKU"]:
            result["SKU"] = value
        if any(x in ll for x in ["ean","gtin","upc","barcode","ean code","ean-13",
                                       "upc code","barcode no","gtin code","gtin no",
                                       "product code","item code","stock code"]) and not result["GTIN"]:
            v_gtin = _re.sub(r'[^\d]', '', value).strip()
            if _re.fullmatch(r'\d{8,14}', v_gtin):
                result["GTIN"] = v_gtin
        if any(x in ll for x in ["colour","color"]) and not result["Colour"]:
            result["Colour"] = value

    # For Samsung: JSON-LD additionalProperty already has clean specs.
    # Skip generic table/dl parsing to avoid duplicates.
    _is_samsung_page = "samsung.com" in url.lower()
    if not _is_samsung_page:
        for tbl in soup.select("table"):
            for row in tbl.select("tr"):
                cells = row.select("td, th")
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    if label and value and len(value) < 200:
                        _add_spec(label, value)

        for dl in soup.select("dl"):
            for dt, dd in zip(dl.select("dt"), dl.select("dd")):
                label = dt.get_text(strip=True); value = dd.get_text(strip=True)
                if label and value and len(value) < 200:
                    _add_spec(label, value)

    # Samsung-specific: only parse spec table when JSON-LD had no additionalProperty
    if _is_samsung_page and not specs_raw:
        for tbl in soup.select("[class*=\'pd-spec\'] table, [class*=\'spec\'] table"):
            for row in tbl.select("tr"):
                cells = row.select("td, th")
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    if label and value and len(value) < 200:
                        _add_spec(label, value)

    for spec_row in soup.select("[class*=\'spec-row\'],[class*=\'spec-item\'],"
                                 "[class*=\'specification-row\'],[class*=\'spec-list\'] li,"
                                 "[class*=\'pdp__spec\'] tr,[class*=\'pd-spec\'] tr"):
        # Handle both "label | value" text and table rows
        cells = spec_row.select("td, th")
        if len(cells) >= 2:
            _add_spec(cells[0].get_text(strip=True), cells[1].get_text(strip=True))
        else:
            parts = spec_row.get_text("|", strip=True).split("|")
            if len(parts) >= 2:
                _add_spec(parts[0].strip(), parts[1].strip())

    # Noon-specific: specs often in a key-value div structure
    for spec_row in soup.select("[class*='specification'] [class*='item'],"
                                 "[class*='spec-table'] [class*='row'],"
                                 "[data-testid*='spec']"):
        label_el = spec_row.select_one("[class*='label'],[class*='key'],[class*='name']")
        value_el = spec_row.select_one("[class*='value'],[class*='val'],[class*='data']")
        if label_el and value_el:
            _add_spec(label_el.get_text(strip=True), value_el.get_text(strip=True))

    result["Tech & Additional Info"] = "; ".join(specs_raw[:30])

    # ── GTIN — dedicated extractor as final pass ──────────────────────────
    if not result["GTIN"]:
        result["GTIN"] = _extract_gtin_from_page(html, url)

    # ── SKU from URL ──────────────────────────────────────────────────────
    if not result["SKU"]:
        # Extract model code from URL.
        # Samsung africa_en: .../galaxy-a06-black-128gb-sm-a065fzkhafb/
        # The SM-XXXXXX model code is always at the END of the slug, after the last hyphen.
        url_path = urllib.parse.urlparse(url).path.rstrip('/')
        slug_end = url_path.split('/')[-1]   # last path segment
        # Try SM- / GT- / SM- style codes at the END of the slug
        _sku_end = _re.search(r'-(sm|gt|sg|sc|shv)-([a-z0-9]+)$', slug_end, _re.IGNORECASE)
        if _sku_end:
            result["SKU"] = f"{_sku_end.group(1)}-{_sku_end.group(2)}".upper()
        else:
            # General model code pattern in URL path
            _sku_m = _re.search(r'(?:^|[/=\-])([A-Za-z]{2,3}-[A-Za-z0-9]{6,})(?:[/\-?]|$)', url)
            if _sku_m:
                _sku_cand = _sku_m.group(1).upper()
                if _re.match(r'^[A-Z]{2,3}-[A-Z0-9]{6,}$', _sku_cand):
                    result["SKU"] = _sku_cand

    # ── Category from breadcrumb ──────────────────────────────────────────
    if not result["Category"]:
        for sel in ["[class*='breadcrumb'] a","nav[aria-label*='breadcrumb'] a",
                    ".breadcrumbs a","[class*='crumb'] a"]:
            items = soup.select(sel)
            if items:
                cats = [a.get_text(strip=True) for a in items if a.get_text(strip=True)]
                if cats: result["Category"] = " > ".join(cats); break

    return result


# ── _scrape_page: tries requests -> cloudscraper -> Playwright ─────────────────

def _is_search_results_url(url: str) -> bool:
    """Return True if the URL is a brand search results page, not a product page."""
    url_low = url.lower()
    return any(p in url_low for p in [
        "/search?", "/search/?", "searchvalue=", "?q=", "/search/",
        "search?searchvalue", "?keywords=", "?keyword=",
    ])


def _is_samsung_url(url: str) -> bool:
    """Return True if the URL is a Samsung product page."""
    return "samsung.com" in url.lower()


def _postprocess_samsung(result: dict, html: str) -> dict:
    """
    Samsung-specific post-processor (runs after _parse_product_html).
    Uses EXACT class names confirmed from the samsung.com/africa_en page source.

    Key Features  ← Specs from section#specs (.pdd32-product-spec)
                    Each label:value pair becomes a bullet in short_description.
    Description   ← Feature blocks from div.feature-benefit
                    Each block: feature image + h2 heading + p description.
    Images        ← Gallery images from .hdd02-gallery + feature images.
    Product Name  ← h1.pdd39-anchor-nav__headline or input#navDisplayName
    SKU/Model     ← input#modelCode (exact model code always present)
    GTIN          ← barcode-DB lookup if still missing.
    """
    import re as _re
    from bs4 import BeautifulSoup as _BS

    try:
        soup = _BS(html, "lxml")

        # ── A. Product Name from confirmed Samsung selectors ─────────────────
        if not result.get("Product Name"):
            for sel in [
                "h1.pdd39-anchor-nav__headline",
                "input#navDisplayName",
                "h1.sg-product-display-name",
                "h2.pd-info__title",
            ]:
                el = soup.select_one(sel)
                if el:
                    name = (el.get("value") or el.get_text(" ", strip=True)).strip()
                    if name and len(name) > 2:
                        result["Product Name"] = name
                        break

        # ── B. SKU / Model Code from hidden input (always present) ───────────
        if not result.get("SKU"):
            mc = soup.select_one("input#modelCode, input#apiChangeModelCode")
            if mc and mc.get("value"):
                result["SKU"] = mc["value"].strip().upper()

        # ── C. Gallery Images from the main product gallery ─────────────────
        gallery_imgs = []
        # First: fully-loaded <picture><img src="..."> (first gallery image)
        for img in soup.select(".hdd02-gallery__list picture img[src], "
                                ".hdd02-gallery__item picture img[src]"):
            src = img.get("src","").strip()
            if src and src.startswith("http") and "gallery" in src:
                # Upgrade to highest res: replace size token with large
                src = _re.sub(r'\?\$[^$]+\$', '?$1164_776_PNG$', src)
                if src not in gallery_imgs:
                    gallery_imgs.append(src)

        # Then: lazy-loaded gallery images using data-desktop-src
        for img in soup.select(".hdd02-gallery__item img[data-desktop-src]"):
            src = img.get("data-desktop-src","").strip()
            if src:
                if src.startswith("//"): src = "https:" + src
                src = _re.sub(r'\?\$[^$]+\$', '?$1164_776_PNG$', src)
                if src not in gallery_imgs:
                    gallery_imgs.append(src)

        # ── D. Specifications from the confirmed spec section ────────────────
        # section.pdd32-product-spec > div.pdd32-product-spec__item
        # Each item has: button text = category, li items = label + desc pairs
        spec_pairs = []
        spec_section = soup.select_one("section.pdd32-product-spec")
        if spec_section:
            for item in spec_section.select("div.pdd32-product-spec__item"):
                # Get category from button text (skip Overview which duplicates)
                cat_btn = item.select_one("button.pdd32-product-spec__toggle-cta")
                # category = cat_btn.get_text(strip=True) if cat_btn else ""

                for row in item.select("li.pdd32-product-spec__content-item"):
                    label_el = row.select_one("p.pdd32-product-spec__content-item-title")
                    value_el = row.select_one("p.pdd32-product-spec__content-item-desc")
                    if value_el:
                        label = label_el.get_text(strip=True) if label_el else ""
                        value = value_el.get_text(strip=True)
                        if value:
                            entry = f"{label}: {value}" if label else value
                            if entry not in spec_pairs:
                                spec_pairs.append(entry)

        if spec_pairs:
            result["Key Features"] = "; ".join(spec_pairs[:40])
            result["Tech & Additional Info"] = "; ".join(spec_pairs[:40])

        # ── E. Feature blocks -> rich HTML Description ───────────────────────
        # Samsung features use div.feature-benefit with:
        #   h2.feature-benefit__title  = heading
        #   p.feature-benefit__desc    = description paragraph
        #   img.image__main[data-desktop-src] = feature image (lazy loaded)
        feature_blocks = []
        for fb in soup.select("div.feature-benefit"):
            heading_el = fb.select_one("h2.feature-benefit__title, "
                                        "h3.feature-benefit__title")
            heading = heading_el.get_text(" ", strip=True) if heading_el else ""

            desc_el = fb.select_one("p.feature-benefit__desc")
            body = desc_el.get_text(" ", strip=True) if desc_el else ""

            # Feature image: data-desktop-src on img.image__main inside feature
            img_src = ""
            img_el = fb.select_one("div.feature-benefit__img-wrap img.image__main")
            if img_el:
                src = (img_el.get("data-desktop-src") or
                       img_el.get("data-src") or
                       img_el.get("src") or "").strip()
                if src:
                    if src.startswith("//"): src = "https:" + src
                    elif src.startswith("/"): src = "https://images.samsung.com" + src
                    # Replace low-res size token with full resolution
                    src = _re.sub(r'\?\$[^$]+\$', '', src)  # strip size param
                    img_src = src

            if heading or body:
                feature_blocks.append({
                    "img": img_src, "heading": heading, "body": body
                })

        # Build self-contained HTML from feature blocks
        if feature_blocks:
            prod_name = result.get("Product Name","")
            parts = [
                '<div style="font-family:Arial,sans-serif;max-width:820px;margin:0 auto;">'
            ]
            for blk in feature_blocks:
                parts.append(
                    '<div style="margin:0 0 48px 0;padding-bottom:32px;'
                    'border-bottom:1px solid #f0f0f0;">'
                )
                if blk["img"]:
                    parts.append(
                        f'<img src="{blk["img"]}" alt="{prod_name}" '
                        f'style="width:100%;max-width:820px;height:auto;'
                        f'display:block;border-radius:8px;margin-bottom:20px;" />'
                    )
                if blk["heading"]:
                    parts.append(
                        f'<h3 style="font-family:Arial,sans-serif;font-size:22px;'
                        f'font-weight:700;color:#1e293b;margin:0 0 12px 0;">'
                        f'{blk["heading"]}</h3>'
                    )
                if blk["body"]:
                    parts.append(
                        f'<p style="font-family:Arial,sans-serif;font-size:15px;'
                        f'color:#4b5563;line-height:1.75;margin:0;">'
                        f'{blk["body"]}</p>'
                    )
                parts.append("</div>")
            parts.append("</div>")
            result["Description"] = "\n".join(parts)

            # Collect feature images for Images field
            feat_imgs = [b["img"] for b in feature_blocks if b["img"]]
            all_imgs = feat_imgs + [u for u in gallery_imgs if u not in feat_imgs]
            if all_imgs:
                result["Images"] = ", ".join(list(dict.fromkeys(all_imgs))[:10])
        elif gallery_imgs:
            # No feature content found — at least use gallery images
            result["Images"] = ", ".join(gallery_imgs[:8])

    except Exception:
        pass   # never crash on post-processing

    # ── F. GTIN — barcode lookup by model code if still missing ─────────────
    if not result.get("GTIN") and result.get("SKU"):
        result["GTIN"] = _lookup_gtin_by_model(
            result.get("SKU",""), result.get("Brand","Samsung"),
            result.get("Product Name",""))

    return result



def _extract_product_url_from_search(html: str, brand_name: str, query: str) -> str:
    """
    Parse a brand search results page and return the best matching product URL.
    Uses a multi-factor scoring system:
      +3 per model-specific query word found in URL (e.g. "a06", "s24", "spark")
      +1 per generic query word found in URL
      -5 for every model number in URL that is NOT in the query (wrong product)
    Works for Samsung, Tecno, Infinix, Nokia, and generic search pages.
    """
    from bs4 import BeautifulSoup
    import re as _re

    soup = BeautifulSoup(html, "lxml")

    # Split query into all words and model-specific words (short alphanumeric codes)
    all_query_words   = {w.lower() for w in query.split() if len(w) > 2}
    # Model words: things like "a06", "s24", "m35", "spark", "note40", "128gb"
    model_query_words = {w.lower() for w in query.split()
                         if _re.search(r'\d', w) or len(w) <= 6}

    # Domain aliases
    _BRAND_DOMAINS_MAP = {
        "samsung": ["samsung.com"], "tecno": ["tecno-mobile.com","tecno.com"],
        "infinix": ["infinixmobility.com","infinix.com"],
        "itel": ["itel-mobile.com","itel.com"], "honor": ["hihonor.com","honor.com"],
        "xiaomi": ["mi.com","xiaomi.com"], "nokia": ["nokia.com"],
        "apple": ["apple.com"], "huawei": ["consumer.huawei.com","huawei.com"],
    }
    brand_domains = _BRAND_DOMAINS_MAP.get(brand_name, [f"{brand_name}.com"])

    # Product URL indicators
    prod_patterns = ["/smartphones/","/product/","/products/","/buy/",
                     "/phone/","/galaxy/","/iphone/","/pixel/","/spark/",
                     "/note/","/detail/","/p/","/phones/"]

    # Common phone model patterns — used to detect model numbers in URLs
    # that are NOT in the query (wrong product)
    _MODEL_PATTERN = _re.compile(
        r'(?:galaxy-|iphone-|pixel-|spark-|note-|camon-|pop-|s\d+|a\d+|m\d+|f\d+|z\d+)'
        r'[-_]?(?:ultra|pro|plus|fe|lite|max)?[-_]?\d*',
        _re.IGNORECASE
    )

    candidates = []
    for a in soup.select("a[href]"):
        href = a.get("href","")
        if not href: continue
        href_low = href.lower()

        # Must point to brand domain or relative path
        is_brand = (any(d in href_low for d in brand_domains)
                    or href.startswith("/"))
        if not is_brand: continue
        # Must look like a product URL
        if not any(p in href_low for p in prod_patterns): continue
        # Skip search/category/support/blog pages
        if any(x in href_low for x in ["/search","/category","/support",
                                        "/help","/blog","/news","?q=",
                                        "/compare","/accessories"]): continue

        score = 0
        # +3 for each model-specific query word in URL (highest weight)
        for w in model_query_words:
            if w in href_low:
                score += 3
        # +1 for each generic query word in URL
        for w in all_query_words - model_query_words:
            if w in href_low:
                score += 1

        # -5 for model tokens in URL that are NOT in the query
        # This strongly penalises wrong products (e.g. S26 Ultra when querying A06)
        url_models = _MODEL_PATTERN.findall(href_low)
        for um in url_models:
            um_clean = _re.sub(r'[-_]', '', um.lower())
            # Check if any query word matches this model token
            if not any(_re.sub(r'[-_]', '', w) in um_clean or
                       um_clean in _re.sub(r'[-_]', '', w)
                       for w in all_query_words):
                score -= 5

        # Prefer Africa/local regions over US (US has different product lineup)
        if "africa_en" in href_low or "/africa_en/" in href_low:
            score += 3   # africa_en is user's confirmed primary region
        elif any(r in href_low for r in ["/ng/","/gh/","/ke/","/za/"]):
            score += 2
        elif "/us/" in href_low:
            score -= 1

        candidates.append((score, href))

    if not candidates:
        return ""

    # Pick the highest-scoring candidate
    candidates.sort(key=lambda x: x[0], reverse=True)
    best = candidates[0][1]

    # Make absolute
    if best.startswith("/"):
        domain = brand_domains[0]
        if brand_name == "samsung":
            best = f"https://www.samsung.com{best}"
        else:
            best = f"https://www.{domain}{best}"
    return best


def _scrape_page(url: str, query: str = "") -> dict:
    """
    Fetch and parse a product page using a layered bypass stack:
      1. requests + cloudscraper
      2. Playwright (headless Chromium) if requests fails or content is not
         a genuine product page
    If url is a brand search results page, extracts the first product URL
    from the search results and scrapes that instead.
    Validates result with _is_product_page before accepting.
    Falls back to _lookup_gtin_by_model if GTIN not found on page.
    """
    html      = None
    last_err  = ""
    url = _normalise_noon_url(url)   # rewrite noon arabic->english locale
    brand_name = (query.split()[0].lower() if query else
                  __import__("urllib.parse", fromlist=["urlparse"])
                  .urlparse(url).netloc.split(".")[1]
                  if "." in __import__("urllib.parse", fromlist=["urlparse"])
                  .urlparse(url).netloc else "")

    # ── Layer 0: Noon catalog API (bypasses Akamai entirely) ─────────────────
    # Noon's HTML page is protected by Akamai Bot Manager.
    # Their internal catalog API at /_svc/catalog/api/ doesn't go through the WAF
    # and returns structured JSON with complete product data.
    if "noon.com" in url.lower():
        try:
            api_result = _scrape_noon_via_api(url)
            if api_result.get("Product Name"):
                if not api_result.get("GTIN"):
                    api_result["GTIN"] = _lookup_gtin_by_model(
                        api_result.get("SKU",""), api_result.get("Brand",""),
                        api_result.get("Product Name",""))
                return api_result
        except Exception as _noon_api_err:
            last_err = f"Noon API: {_noon_api_err}"

    # ── Layer 0b: Fouani __NEXT_DATA__ extraction ────────────────────────────
    # DISABLED: fouanistore.com returns 403 "Host not in allowlist" from all
    # cloud server IPs (Render, DigitalOcean, etc.) — requests and Playwright
    # both fail. Skip to avoid wasting timeout cycles.
    if False and _is_fouani_url(url):
        try:
            fouani_result = _scrape_fouani(url)
            if fouani_result.get("Product Name"):
                if not fouani_result.get("GTIN"):
                    fouani_result["GTIN"] = _lookup_gtin_by_model(
                        fouani_result.get("SKU", ""),
                        fouani_result.get("Brand", ""),
                        fouani_result.get("Product Name", ""))
                return fouani_result
        except Exception as _fouani_err:
            last_err = f"Fouani: {_fouani_err}"

    # Layer 1: requests / cloudscraper
    try:
        html = _fetch_html_requests(url)
    except Exception as e:
        last_err = str(e)

    if html:
        # If this is a search results page, extract the real product URL first
        if _is_search_results_url(url):
            product_url = _extract_product_url_from_search(html, brand_name, query)
            if product_url and product_url != url:
                return _scrape_page(product_url, query)
            # Search gave us no product URL — fall through to Playwright
            last_err = f"Search page at {url[:60]} yielded no product URLs"
        else:
            result = _parse_product_html(html, url)
            if _is_samsung_url(url):
                result = _postprocess_samsung(result, html)
            if _is_product_page(result, query or url):
                if not result.get("GTIN"):
                    result["GTIN"] = _lookup_gtin_by_model(
                        result.get("SKU",""), result.get("Brand",""),
                        result.get("Product Name",""))
                return result
            last_err = ("requests fetched page but it is not a product detail page "
                        f"(name='{result.get('Product Name','')}') — trying Playwright")

    # Layer 2: Playwright
    try:
        # Search result pages need extra wait for JS to render product links
        _pw_wait = 4500 if _is_search_results_url(url) else None
        html = _fetch_html_playwright(url, **({'wait_ms': _pw_wait} if _pw_wait else {}))

        # Search results page via Playwright — extract product URL and recurse
        if _is_search_results_url(url):
            product_url = _extract_product_url_from_search(html, brand_name, query)
            if product_url and product_url != url:
                return _scrape_page(product_url, query)
            # Search page found no matching product link — do NOT parse the search
            # page itself as a product (it would return featured/unrelated products).
            r = {"URL": url, "Website": "", "Product Name": "", "Brand": "",
                 "Images": "", "Key Features": "", "Description": "",
                 "Tech & Additional Info": "", "SKU": "", "GTIN": "",
                 "Price": "", "Currency": "", "Category": "",
                 "Warranty": "", "Weight": "", "Dimensions": "", "Colour": ""}
            r["Error"] = f"Search page yielded no product URL for '{query}'"
            return r

        result = _parse_product_html(html, url)
        if _is_samsung_url(url):
            result = _postprocess_samsung(result, html)
        if not result.get("GTIN"):
            result["GTIN"] = _lookup_gtin_by_model(
                result.get("SKU",""), result.get("Brand",""),
                result.get("Product Name",""))
        return result
    except Exception as e:
        r = {"URL": url, "Website": "", "Product Name": "", "Brand": "",
             "Images": "", "Key Features": "", "Description": "",
             "Tech & Additional Info": "", "SKU": "", "GTIN": "",
             "Price": "", "Currency": "", "Category": "",
             "Warranty": "", "Weight": "", "Dimensions": "", "Colour": ""}
        r["Error"] = (
            f"All fetch layers failed. requests: {last_err} | playwright: {e}"
            + (
                "\n\nPlaywright Chromium is not installed. "
                "Open a terminal and run:  python -m playwright install chromium"
                if any(x in str(e).lower() for x in [
                    "winerror 2", "cannot find the file", "executable",
                    "chromium is not installed", "playwright chromium"
                ])
                else ""
            )
        )
        return r


# ── _search_and_scrape: full bypass search pipeline ──────────────────────────

def _search_and_scrape(query: str, progress_cb=None) -> dict:
    """
    Find and scrape the brand's official product page.
    Layer order:
      1. Direct URL construction (official brand website, no search engine)
      2. Multi-engine search (site-specific brand domains)
      3. Playwright fallback on brand search pages
      4. General web search (broad — finds any relevant page for the product)
      5. Fouani last resort (appliance/furniture brands only):
         5a. Fouani direct URL — find product ID via search, scrape direct URL
         5b. Fouani full-text search fallback (_search_fouani)
      6. Error return (only if all stages exhausted)
    """
    def _cb(pct, msg):
        if progress_cb: progress_cb(pct, msg)

    brand_name = query.split()[0].lower()

    result_stub = {
        "URL": "", "Website": "Brand Official",
        "Product Name": query, "Brand": query.split()[0] if query else "",
        "Search Query": query, "Price": "", "Currency": "",
        "Category": "", "Key Features": "", "About This Item": "",
        "Tech & Additional Info": "", "Description": "",
        "Rating": "", "Reviews Count": "",
        "SKU": "", "GTIN": "", "Availability": "", "Images": "",
        "Warranty": "", "Weight": "", "Dimensions": "", "Colour": "",
    }

    def _has_content(r):
        return _is_product_page(r, query)

    def _score_url(u):
        u_low = u.lower()
        score = 0
        for kw in ["/product/","/products/","/buy/","/shop/","/mobile/",
                   "/smartphone/","/phone/","/galaxy/","/iphone/","/pixel/",
                   "/detail/","/p/","/item/","/dp/"]:
            if kw in u_low: score += 3
        for word in query.split():
            if len(word) > 3 and word.lower() in u_low: score += 1
        for kw in ["/search","?q=","/category/","/blog/","/news/",
                   "/support/","/help/","/about","login","account"]:
            if kw in u_low: score -= 5
        return score

    # ── Stage 1: direct URL construction (official brand website first) ──────
    # Skip entirely when the query has no model code (a word ≥4 chars with a
    # digit). Direct URL templates only succeed when the slug contains an actual
    # model code (e.g. "x90l", "306dr"). Descriptive queries like
    # "Sony Bravia UHD 55 Inches" produce slugs that always 404, wasting
    # up to 300s of requests+Playwright cycles before Stage 4 can run.
    import re as _re_s1
    _has_model_code = any(
        len(w) >= 4 and _re_s1.search(r'\d', w)
        for w in query.split()
    )
    _cb(8, "Building direct product URLs…")
    direct = _direct_urls(query) if _has_model_code else []
    last_error = ""

    # Try up to 10 direct URLs so Samsung search URLs (at pos 4-8) get included
    _direct_limit = min(len(direct), 10)
    for i, url in enumerate(direct[:_direct_limit]):
        _cb(10 + i * 5, f"Trying URL {i+1}/{_direct_limit}: {url[:55]}…")
        try:
            r = _scrape_page(url, query=query)
            if _has_content(r):
                r["Search Query"] = query
                if not r.get("Brand"): r["Brand"] = query.split()[0]
                _cb(80, "Content found via direct URL")
                return _normalise(r)
            last_error = ("Direct URL " + url[:50] + " — not a product page (got: "
                          + repr(r.get("Product Name", "")) + ")")
        except Exception as exc:
            last_error = f"Direct URL error: {exc}"

    # ── Stage 2: multi-engine search ────────────────────────────────────────
    _cb(25, "Searching via multiple search engines…")
    candidate_urls = _search_for_urls(query, brand_name)

    if not candidate_urls:
        # Last resort: try Playwright on the brand's own search page.
        # Each brand uses a different search URL format.
        _cb(35, "Trying Playwright on brand search page…")
        try:
            import urllib.parse as _up2
            _q = _up2.quote_plus(query)
            _BRAND_SEARCH_URLS = {
                "samsung":  [f"https://www.samsung.com/africa_en/search/?searchvalue={_q}",
                             f"https://www.samsung.com/ng/search/?searchvalue={_q}",
                             f"https://www.samsung.com/gh/search/?searchvalue={_q}",
                             f"https://www.samsung.com/ke/search/?searchvalue={_q}",
                             f"https://www.samsung.com/uk/search/?searchvalue={_q}"],
                "apple":    [f"https://www.apple.com/shop/product/search?q={_q}"],
                "nokia":    [f"https://www.nokia.com/phones/search/?q={_q}"],
                "huawei":   [f"https://solar.huawei.com/en/products/?search={_q}",
                             f"https://consumer.huawei.com/en/search/?keyword={_q}"],
                "xiaomi":   [f"https://www.mi.com/global/search/?keywords={_q}"],
                "tecno":    [f"https://www.tecno-mobile.com/search?q={_q}"],
                "infinix":  [f"https://www.infinixmobility.com/search?q={_q}"],
                "itel":     [f"https://www.itel-mobile.com/search?q={_q}"],
                "lg":       [f"https://www.lg.com/africa/search/?keyword={_q}",
                             f"https://www.lg.com/ng/search/?keyword={_q}",
                             f"https://www.lg.com/uk/search/?keyword={_q}"],
                "hisense":  [f"https://uk.hisense.com/search?text={_q}",
                             f"https://global.hisense.com/search?q={_q}",
                             f"https://hisense.co.za/?s={_q}"],
                "growatt":  [f"https://en.growatt.com/search/?q={_q}",
                             f"https://en.growatt.com/products/?search={_q}"],
                "deye":     [f"https://www.deyeinverter.com/?s={_q}",
                             f"https://www.deyeinverter.com/product/?s={_q}"],
                "jinko":    [f"https://www.jinkosolar.com/en/site/search?q={_q}",
                             f"https://www.jinkosolar.com/en/"],
                "pylontech":[f"https://en.pylontech.com.cn/search?q={_q}",
                             f"https://en.pylontech.com.cn/products/"],
                "actiu":    [f"https://www.actiu.com/en/search/?q={_q}",
                             f"https://www.actiu.com/en/furniture/"],
                "maxi":     [f"https://fouanistore.com/search?q={_q}"],
                "tsty":     [f"https://fouanistore.com/search?q={_q}"],
            }
            _search_urls = _BRAND_SEARCH_URLS.get(
                brand_name,
                [f"https://www.{brand_name}.com/search?q={_q}",
                 f"https://www.{brand_name}.com/en/search?q={_q}"]
            )
            # Product URL keywords — covers /smartphones/, /product/, /buy/, /galaxy/ etc.
            _prod_kws = ["/product","/buy","/phone","/smartphone","/smartphones/",
                         "/galaxy","/iphone","/pixel","/spark","/note","/p/","/detail/"]

            for _surl in _search_urls:
                try:
                    # Quick probe: if requests returns 403 "Host not in
                    # allowlist", the domain blocks our server IP entirely.
                    # Launching Playwright would just waste ~12s for the same
                    # result — skip immediately.
                    try:
                        import requests as _req_probe
                        _probe = _req_probe.get(
                            _surl,
                            headers={"User-Agent": "Mozilla/5.0"},
                            timeout=4, allow_redirects=False
                        )
                        if (_probe.status_code == 403 and
                                b"not in allowlist" in _probe.content):
                            continue
                    except Exception:
                        pass
                    html = _fetch_html_playwright(_surl, wait_ms=2500)
                    from bs4 import BeautifulSoup as _BS
                    soup = _BS(html, "lxml")
                    links = []
                    for a in soup.select("a[href]"):
                        href = a.get("href", "")
                        href_low = href.lower()
                        if (any(d in href_low for d in [brand_name, "samsung.com",
                                "tecno-mobile.com","infinixmobility.com","itel-mobile.com",
                                "hihonor.com","mi.com","oneplus.com"])
                                and any(kw in href_low for kw in _prod_kws)):
                            full = ("https://www."+brand_name+".com"+href
                                    if href.startswith("/") else href)
                            links.append(full)
                    candidate_urls = list(dict.fromkeys(links[:8]))
                    if candidate_urls:
                        break
                except Exception:
                    continue
        except Exception as e:
            last_error = f"Playwright brand search: {e}"

    _cb(40, f"Found {len(candidate_urls)} candidate URL(s) — scraping…")
    candidate_urls.sort(key=_score_url, reverse=True)

    # ── Stage 3: scrape candidates sequentially (Playwright needs dedicated thread)
    for i, url in enumerate(candidate_urls[:5]):
        _cb(45 + i * 8, f"Scraping {i+1}/{min(len(candidate_urls),5)}: {url[:55]}…")
        try:
            r = _scrape_page(url, query=query)
            if r.get("Error"):
                last_error = r["Error"]; continue
            if _has_content(r):
                r["Search Query"] = query
                if not r.get("Brand"): r["Brand"] = query.split()[0]
                _cb(80, "Content found")
                return _normalise(r)
            last_error = ("Page at " + url[:50] + " not a product page (got: "
                          + repr(r.get("Product Name", "")) + ")")
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"

    # ── Stage 4: General web search fallback ────────────────────────────────
    # All brand-specific paths exhausted. Try broad multi-engine search using
    # the raw query — accepts results from ANY domain that is likely to contain
    # full product details (official brand pages, spec sites, retailers).
    # Multiple targeted query variants are tried in parallel across multiple
    # search engines to maximise the chance of finding a usable product page.
    _cb(75, "Trying general web search fallback…")
    try:
        import re as _re_gen, urllib.parse as _up_gen, requests as _req_gen
        from concurrent.futures import ThreadPoolExecutor as _TPE_gen, \
                                        as_completed as _asc_gen

        # Extract model-code words (digit-containing) for targeted queries
        _q_words   = query.split()
        _model_kws = [w for w in _q_words if _re_gen.search(r'\d', w) and len(w) >= 3]
        _model_str = " ".join(_model_kws)

        # ── Query variants — ordered from most to least targeted ────────────
        # Each variant is designed to surface a different type of result page.
        _gen_queries = [
            query,                                           # 1. exact query
            f"{query} specifications buy",                  # 2. specs + retail
        ]
        if _model_str:
            # 3. Model code only + brand (catches pages where name differs)
            _gen_queries.append(f"{brand_name} {_model_str} specifications")
            # 4. Model code + "price" (surfaces retailer pages with full product info)
            _gen_queries.append(f"{brand_name} {_model_str} price buy Nigeria")
        # 5. Full query targeting spec/review sites explicitly
        _gen_queries.append(f"{query} full specifications review")
        # 6. Brand site search — last resort before giving up
        _gen_queries.append(f"{query} site:{brand_name}.com")

        # ── Search engine templates ──────────────────────────────────────────
        _GEN_SEARCH_TEMPLATES = [
            "https://html.duckduckgo.com/html/?q={q}",
            "https://lite.duckduckgo.com/lite/?q={q}",
            "https://www.bing.com/search?q={q}&setmkt=en-US",
            "https://search.yahoo.com/search?p={q}",
            "https://www.startpage.com/sp/search?query={q}",
        ]

        # ── Domains known to have full product detail pages ──────────────────
        # Divided into tiers: brand official pages score highest,
        # spec/review sites score next, retailers score below that.
        _TIER1_DOMAINS = [
            # Official brand sites
            "samsung.com", "lg.com", "hisense.com", "sony.com",
            "apple.com", "nokia.com", "motorola.com", "huawei.com",
            "xiaomi.com", "mi.com", "tecno-mobile.com", "infinixmobility.com",
            "itel-mobile.com", "realme.com", "hihonor.com", "oppo.com",
            "oneplus.com", "vivo.com", "panasonic.com", "midea.com",
            "haier.com", "bosch-home.com", "daikin.com", "daikin.co.uk",
            "en.growatt.com", "deyeinverter.com", "jinkosolar.com",
            "en.pylontech.com.cn", "victronenergy.com", "sma.de",
            "jbl.com", "bose.com", "sonos.com", "harmankardon.com",
            "longi-solar.com", "canadiansolar.com", "trinasolar.com",
            "jasolar.com", "actiu.com", "scanfrost.com.ng",
        ]
        _TIER2_DOMAINS = [
            # Spec / review / comparison sites
            "gsmarena.com", "rtings.com", "techradar.com", "cnet.com",
            "notebookcheck.net", "phonearena.com", "91mobiles.com",
            "kimovil.com", "devicespecifications.com", "versus.com",
            "nanoreview.net", "gizmochina.com", "gadgets360.com",
            "techopedia.com", "techpowerup.com", "displayspecifications.com",
            "whathifi.com", "soundguys.com", "stereonet.com",
            "solarpanelstore.com", "energysage.com", "inverterreview.com",
        ]
        _TIER3_DOMAINS = [
            # Retailers with rich product data
            "jumia.com", "jumia.com.ng", "jumia.co.ke", "jumia.com.gh",
            "amazon.com", "amazon.co.uk", "amazon.de",
            "konga.com", "noon.com", "bhphotovideo.com",
            "newegg.com", "bestbuy.com", "currys.co.uk",
            "easyelectronics.com.ng", "slot.ng", "payporte.com",
            "alibaba.com", "aliexpress.com",
        ]
        _ALL_GOOD_DOMAINS = _TIER1_DOMAINS + _TIER2_DOMAINS + _TIER3_DOMAINS

        # ── URL scoring for Stage 4 ──────────────────────────────────────────
        _GEN_PROD_PATHS = {
            "/product/", "/products/", "/buy/", "/shop/",
            "/smartphones/", "/phones/", "/mobile/", "/phone/",
            "/tvs/", "/television/", "/oled/", "/qled/",
            "/refrigerators/", "/washing-machines/", "/air-conditioners/",
            "/speakers/", "/soundbars/", "/audio/",
            "/inverters/", "/batteries/", "/solar/",
            "/p/", "/item/", "/dp/", "/sku/",
            "/detail/", "/details/", "/product-detail/",
            "/galaxy/", "/iphone/", "/pixel/",
            "/catalog/product/", "/en/product/",
        }
        _GEN_SKIP_PATHS = {
            "/search?", "/search/?", "?q=", "?s=", "?query=",
            "/category/", "/categories/", "/catalog?",
            "/blog/", "/news/", "/article/", "/press/",
            "/support/", "/help/", "/faq/", "/about",
            "/login", "/account", "/cart", "/wishlist",
            "/compare/", "/accessories/", "/spare-parts/",
            "duckduckgo", "bing.com", "yahoo.", "google.",
            "cache:", "translate", "mojeek", "startpage",
            "javascript:", "mailto:", "facebook.com", "twitter.com",
            "instagram.com", "youtube.com", "wikipedia.org",
        }

        def _score_gen_url(u: str) -> int:
            u_low = u.lower()
            # Hard reject — skip/noise pages
            if any(kw in u_low for kw in _GEN_SKIP_PATHS):
                return -999
            s = 0
            # Tier 1 (official brand) — highest value
            if any(d in u_low for d in _TIER1_DOMAINS):
                s += 12
                # Extra bonus if it's actually the queried brand's site
                if brand_name in u_low:
                    s += 5
            # Tier 2 (spec sites) — next best for getting product details
            elif any(d in u_low for d in _TIER2_DOMAINS):
                s += 7
            # Tier 3 (retailers) — useful but lower priority than spec sites
            elif any(d in u_low for d in _TIER3_DOMAINS):
                s += 4
            else:
                # Unknown domain — only include if URL looks like a product page
                s -= 2
            # Product path keywords
            for kw in _GEN_PROD_PATHS:
                if kw in u_low:
                    s += 3
                    break
            # Model code words in URL (strong match signal)
            for w in _model_kws:
                if w.lower() in u_low:
                    s += 6
            # Other query words in URL
            for w in _q_words:
                wl = w.lower()
                if len(wl) > 3 and wl in u_low:
                    s += 2
            # Africa/Nigeria market bonus
            if any(r in u_low for r in [".ng", ".ke", ".gh", "africa", "nigeria"]):
                s += 2
            # Penalise listing/search pages
            if _re_gen.search(r'\?(q|s|search|keyword|query)=', u_low):
                s -= 6
            # Penalise very short URLs (homepage or category root)
            if len(u) < 45:
                s -= 4
            return s

        def _extract_urls_from_html_gen(html: str) -> list:
            """Extract all URLs from search engine HTML using multiple patterns."""
            found, seen = [], set()
            # href attributes
            for m in _re_gen.finditer(r'href=["\']?(https?://[^\s"\'<>&]+)', html):
                u = m.group(1)
                # Decode DuckDuckGo redirect: ...uddg=https%3A...
                ddg = _re_gen.search(r'uddg=(https?%3A[^&"\']+)', u)
                if ddg:
                    try: u = _up_gen.unquote(ddg.group(1))
                    except Exception: pass
                u = u.split("?")[0].rstrip("/")
                if u.startswith("http") and u not in seen:
                    seen.add(u); found.append(u)
            # JSON "url":"..." patterns (Bing JSON, Mojeek)
            for m in _re_gen.finditer(r'"url"\s*:\s*"(https?://[^"]+)"', html):
                u = m.group(1).split("?")[0].rstrip("/")
                if u.startswith("http") and u not in seen:
                    seen.add(u); found.append(u)
            # data-url / data-href
            for m in _re_gen.finditer(
                    r'data-(?:url|href|link)=["\']?(https?://[^\s"\'<>&]+)', html):
                u = m.group(1).split("?")[0].rstrip("/")
                if u.startswith("http") and u not in seen:
                    seen.add(u); found.append(u)
            return found

        def _fetch_search_page(tmpl: str, enc_q: str) -> list:
            """Fetch one search engine result page and return scored candidate URLs."""
            found = []
            try:
                resp = _req_gen.get(
                    tmpl.format(q=enc_q),
                    headers=_headers(), timeout=10, allow_redirects=True
                )
                if resp.status_code in (403, 429, 503):
                    # "Host not in allowlist" = IP-level block; cloudscraper
                    # won't help and would just add latency — bail immediately.
                    if b"not in allowlist" in resp.content:
                        return found
                    try:
                        import cloudscraper as _cs_gen
                        cs = _cs_gen.create_scraper(
                            browser={"browser": "chrome", "platform": "windows"})
                        resp = cs.get(tmpl.format(q=enc_q), timeout=15)
                    except Exception:
                        return found
                for u in _extract_urls_from_html_gen(resp.text):
                    score = _score_gen_url(u)
                    if score > 0:
                        found.append((u, score))
            except Exception:
                pass
            return found

        # ── Fire all (query × engine) combinations in parallel ───────────────
        _gen_tasks = []
        for _gq in _gen_queries[:4]:          # top 4 query variants
            _enc = _up_gen.quote_plus(_gq)
            for _tmpl in _GEN_SEARCH_TEMPLATES:
                _gen_tasks.append((_tmpl, _enc))

        _scored_gen: list[tuple[str, int]] = []
        _seen_gen   = set()

        with _TPE_gen(max_workers=10) as _ex_gen:
            _futs_gen = {
                _ex_gen.submit(_fetch_search_page, tmpl, enc): (tmpl, enc)
                for tmpl, enc in _gen_tasks
            }
            for _fut in _asc_gen(_futs_gen):
                for u, sc in _fut.result():
                    if u not in _seen_gen:
                        _seen_gen.add(u)
                        _scored_gen.append((u, sc))
                # Stop collecting once we have a good pool to rank from
                if len(_scored_gen) >= 30:
                    break

        # ── Rank and deduplicate ─────────────────────────────────────────────
        _scored_gen.sort(key=lambda x: x[1], reverse=True)
        _deduped = []
        _seen_dedup = set()
        for u, _ in _scored_gen:
            if u not in _seen_dedup:
                _seen_dedup.add(u)
                _deduped.append(u)
            if len(_deduped) >= 10:
                break

        _cb(78, f"General search found {len(_deduped)} candidate(s) — scraping…")
        for _gi, _gu in enumerate(_deduped):
            _cb(79, f"General fallback {_gi+1}/{len(_deduped)}: {_gu[:55]}…")
            try:
                if _is_fouani_url(_gu):
                    _gr = _scrape_fouani(_gu)
                else:
                    _gr = _scrape_page(_gu, query=query)
                if _gr.get("Error"): continue
                if _has_content(_gr):
                    _gr["Search Query"] = query
                    if not _gr.get("Brand"): _gr["Brand"] = query.split()[0]
                    _cb(85, "Content found via general search fallback")
                    return _normalise(_gr)
            except Exception:
                continue

    except Exception as _gen_err:
        last_error = f"General search fallback error: {_gen_err}"

    # ── Stage 5: Fouani last resort (appliance/furniture only) ──────────────
    # Official website and general search both failed.
    # Only try fouanistore.com if:
    #   (a) the brand is stocked on Fouani (_FOUANI_FIRST_BRANDS), AND
    #   (b) the query is for an appliance/furniture category — NOT smartphones,
    #       tablets, laptops, solar panels (non-appliance power), etc.
    # Original Fouani categories: ACs, Audio, Furnitures, Power Solution
    # (inverters/batteries only), Refrigerator, Small Appliances/Fans, TVs,
    # Washing Machines.
    _FOUANI_APPLIANCE_KEYWORDS = {
        # Large appliances
        "refrigerator","fridge","washing machine","washer","dryer",
        "air condition","aircon","split unit","cassette ac","standing ac",
        "window ac","window unit","portable ac","air-con","heat pump",
        # TVs & audio
        " tv ", " tv", "television","oled","qled","uled","uhd","smart tv",
        "soundbar","sound bar","speaker","subwoofer","home theater","home theatre",
        # Small appliances
        "microwave","blender","juicer","toaster","iron","kettle","fan ",
        "cooler","air cooler","deep fryer","rice cooker","slow cooker",
        "coffee maker","vacuum cleaner","air purifier","water dispenser",
        "standing fan","ceiling fan","table fan","electric fan",
        # Furniture
        "office chair","desk","table","shelf","cabinet","storage",
        # Power/energy (appliance inverters & batteries — not solar panels)
        "inverter","hybrid inverter","solar inverter","battery storage",
        "power inverter","home battery","energy storage"," battery",
    }
    _FOUANI_EXCLUDE_KEYWORDS = {
        "phone","smartphone","mobile","tablet","ipad","laptop","notebook",
        "solar panel","pv panel","photovoltaic","module","watt panel",
    }

    if False:  # fouanistore.com 403s all Render IPs; skip to error return
        q_low_fouani = query.lower()
        _fouani_cat_match = any(kw in q_low_fouani for kw in _FOUANI_APPLIANCE_KEYWORDS)
        _fouani_excluded  = any(kw in q_low_fouani for kw in _FOUANI_EXCLUDE_KEYWORDS)

        if _fouani_cat_match and not _fouani_excluded:

            # ── Stage 5a: Fouani direct URL (find product ID via search,
            #             then scrape fouanistore.com/product/{id}?{slug} directly)
            # This is always tried first before the full-text search fallback.
            _cb(86, f"Trying Fouani direct URL for '{query}'…")
            _fouani_direct_result = {}
            try:
                import re as _re_f, urllib.parse as _up_f, json as _json_f
                import requests as _req_f

                _fq_enc = _up_f.quote_plus(query)
                _f_headers = {
                    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                                   "Chrome/124.0.0.0 Safari/537.36"),
                    "Accept": "application/json, text/html, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://fouanistore.com/",
                }

                # Try all API endpoints + HTML search page to get the product ID
                _f_products = []
                _f_api_urls = [
                    f"https://fouanistore.com/api/v2/products?search={_fq_enc}&limit=10",
                    f"https://fouanistore.com/api/products?search={_fq_enc}&limit=10",
                    f"https://fouanistore.com/api/products?q={_fq_enc}&limit=10",
                    f"https://fouanistore.com/api/v1/products?search={_fq_enc}&limit=10",
                ]
                for _fapi in _f_api_urls:
                    try:
                        _fr = _req_f.get(_fapi, headers=_f_headers, timeout=8)
                        if _fr.status_code == 200:
                            _fd = _fr.json()
                            if isinstance(_fd, list):
                                _f_products = _fd
                            elif isinstance(_fd, dict):
                                _inner = (_fd.get("data") or _fd.get("products") or
                                          _fd.get("items") or [])
                                if isinstance(_inner, list):
                                    _f_products = _inner
                                elif isinstance(_inner, dict):
                                    _f_products = (_inner.get("data") or
                                                   _inner.get("items") or [])
                            if _f_products:
                                break
                    except Exception:
                        continue

                # HTML search page fallback to get product IDs
                if not _f_products:
                    for _fsurl in [
                        f"https://fouanistore.com/search?q={_fq_enc}",
                        f"https://fouanistore.com/en/search?q={_fq_enc}",
                    ]:
                        try:
                            _fhr = _req_f.get(_fsurl, headers=_f_headers, timeout=12)
                            _fhtml = _fhr.text
                            _fm = _re_f.search(
                                r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                                _fhtml, _re_f.DOTALL)
                            if _fm:
                                _fnd = _json_f.loads(_fm.group(1))
                                _fpdata = (_fnd.get("props", {})
                                              .get("pageProps", {})
                                              .get("data", {}))
                                for _fk in ["data", "products", "items"]:
                                    _fc = _fpdata.get(_fk) if isinstance(_fpdata, dict) else None
                                    if isinstance(_fc, list) and _fc:
                                        _f_products = _fc; break
                                    elif isinstance(_fc, dict):
                                        for _fk2 in ["data", "products", "items"]:
                                            _fc2 = _fc.get(_fk2)
                                            if isinstance(_fc2, list) and _fc2:
                                                _f_products = _fc2; break
                                        if _f_products: break
                            if _f_products:
                                break
                        except Exception:
                            continue

                # Playwright HTML fallback
                if not _f_products:
                    try:
                        _fpw = _fetch_html_playwright(
                            f"https://fouanistore.com/search?q={_fq_enc}", wait_ms=3000)
                        _fm = _re_f.search(
                            r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                            _fpw, _re_f.DOTALL)
                        if _fm:
                            _fnd = _json_f.loads(_fm.group(1))
                            _fpdata = (_fnd.get("props", {})
                                          .get("pageProps", {})
                                          .get("data", {}))
                            for _fk in ["data", "products", "items"]:
                                _fc = _fpdata.get(_fk) if isinstance(_fpdata, dict) else None
                                if isinstance(_fc, list) and _fc:
                                    _f_products = _fc; break
                                elif isinstance(_fc, dict):
                                    for _fk2 in ["data", "products", "items"]:
                                        _fc2 = _fc.get(_fk2)
                                        if isinstance(_fc2, list) and _fc2:
                                            _f_products = _fc2; break
                                    if _f_products: break
                    except Exception:
                        pass

                # Score results and pick best match
                if _f_products:
                    _f_qwords = set(_re_f.sub(r'[^a-z0-9 ]', ' ', query.lower()).split())
                    _f_qwords -= {"and","the","for","with","in","a","an","of","to"}

                    def _f_score(p):
                        n = (p.get("name") or p.get("title") or "").lower()
                        nw = set(_re_f.sub(r'[^a-z0-9 ]', ' ', n).split())
                        s = 0
                        for w in _f_qwords:
                            if w in nw:
                                s += 3 if (len(w) >= 4 and not w.isalpha()) else 1
                        nc = n.replace(' ','').replace('(','').replace(')','')
                        for w in _f_qwords:
                            if len(w) >= 4 and w in nc:
                                s += 2
                        return s

                    _f_scored = [(p, _f_score(p)) for p in _f_products
                                 if isinstance(p, dict)]
                    if _f_scored:
                        _f_best, _f_bscore = max(_f_scored, key=lambda x: x[1])
                        if _f_bscore > 0:
                            _f_id   = _f_best.get("id") or _f_best.get("product_id") or ""
                            _f_slug = _f_best.get("slug") or _f_best.get("name", "").lower()
                            _f_slug = _re_f.sub(r'[^a-z0-9]+', '-', _f_slug).strip('-')
                            if _f_id:
                                # ── Direct URL scrape — this is the key step ──
                                _f_direct_url = (f"https://fouanistore.com/product/"
                                                 f"{_f_id}?{_f_slug}")
                                _cb(88, f"Scraping Fouani direct URL: {_f_direct_url[:55]}…")
                                _fouani_direct_result = _scrape_fouani(_f_direct_url)

            except Exception:
                pass

            if _fouani_direct_result.get("Product Name") and _has_content(_fouani_direct_result):
                _fouani_direct_result["Search Query"] = query
                _cb(92, "Found on fouanistore.com (direct URL)")
                return _normalise(_fouani_direct_result)

            # ── Stage 5b: Fouani full-text search fallback ───────────────────
            # Direct URL attempt above failed or returned no content.
            # Try the full _search_fouani pipeline as a final fallback.
            _cb(93, f"Trying Fouani search fallback for '{query}'…")
            try:
                fouani_r = _search_fouani(query)
                if fouani_r.get("Product Name") and _has_content(fouani_r):
                    fouani_r["Search Query"] = query
                    _cb(95, "Found on fouanistore.com (search)")
                    return _normalise(fouani_r)
            except Exception:
                pass

    # ── All stages exhausted — return informative error ──────────────────────
    result_stub["Error"] = (
        f"No product page found for '{query}' after exhaustive search. "
        f"Last error: {last_error}. "
        "Tip: Use the Single URL Test tab and paste the product page URL directly."
    )
    return _normalise(result_stub)


def search_brand_website(query: str, progress_cb=None) -> dict:
    """
    Public entry point. Runs the full bypass scrape pipeline.
    Only calls scrape_product for a second pass if the first result
    is thin (missing key fields) — avoids fetching the same page twice.
    """
    result = _search_and_scrape(query, progress_cb=progress_cb)

    # Only do a second scrape pass if the result is missing important fields
    # and we have a URL to fetch. Avoids double-fetching on success.
    _RICH_FIELDS = ("Product Name", "Description", "Images", "Key Features")
    _filled = sum(1 for f in _RICH_FIELDS if result.get(f))
    _needs_enrichment = result.get("URL") and not result.get("Error") and _filled < 2

    if _needs_enrichment:
        try:
            ps = _normalise(scrape_product(result["URL"]))
            for key, val in ps.items():
                if val and not result.get(key):
                    result[key] = val
        except Exception:
            pass

    if not result.get("GTIN"):
        result["GTIN"] = _extract_gtin(result)
    if not result.get("GTIN") and (result.get("SKU") or result.get("Product Name")):
        result["GTIN"] = _lookup_gtin_by_model(
            result.get("SKU",""), result.get("Brand",""), result.get("Product Name",""))

    return result
