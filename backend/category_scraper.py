"""
Category Page Scraper — extracted from scraper_gui.py
Provides: scrape_category_page(url, max_products, progress_cb) -> list[dict]

Special handling:
  fouanistore.com  — extracts from __NEXT_DATA__ JSON, paginates, enriches
  samsung.com      — uses Samsung Product Finder API, enriches each product
  Any other site   — requests + Playwright, multi-page link extraction
"""

import re, json, random
import urllib.parse as urllib_parse
import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# ── Shared helpers from brand_scraper ────────────────────────────────────────
try:
    from brand_scraper import (
        _fetch_html_playwright, _normalise, _ensure_hd_images,
        _extract_gtin, _scrape_page, _scrape_fouani,
    )
except Exception:
    def _fetch_html_playwright(url, wait_ms=3000):
        raise RuntimeError("Playwright not available")
    def _normalise(r): return r
    def _ensure_hd_images(r): return r
    def _extract_gtin(r): return ""
    def _scrape_page(url, query=""): return {"URL": url, "Error": "brand_scraper unavailable"}
    def _scrape_fouani(url): return {}

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

def _random_ua():
    try:
        from fake_useragent import UserAgent
        return UserAgent().chrome
    except Exception:
        return random.choice(_UA_POOL)

def _headers(ua=None):
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


# ════════════════════════════════════════════════════════════════════════════
# Public entry point
# ════════════════════════════════════════════════════════════════════════════

def scrape_category_page(category_url: str, max_products: int = 50,
                         progress_cb=None) -> list:
    """
    Discover all product URLs from a category/listing page, scrape each one,
    and return a list of result dicts ready for BOB/VendorCenter export.
    """
    return _scrape_category_page(category_url, max_products, progress_cb)


def _scrape_category_page(category_url: str, max_products: int = 50,
                           progress_cb=None) -> list:
    """
    Discover all product detail page URLs from a category/listing URL on any
    website, then scrape each one and return a list of result dicts.

    Special handling:
      • fouanistore.com — category/search pages embed all product data in
        __NEXT_DATA__ (hits array). Data is extracted directly without
        visiting individual product pages. Pagination handled via ?page=N.

    Generic strategy for all other sites (tried in order):
      1. requests → BeautifulSoup link extraction
      2. Playwright (headless Chromium) for JS-rendered pages
      3. Both methods attempt pagination via rel="next" / Next buttons.

    Link detection heuristics (generic — works on any site):
      • Paths containing known product indicators (/product/, /p/, /item/,
        /dp/, /smartphone/, /phones/, /tvs/, /refrigerators/, etc.)
      • Schema.org itemprop="url" on product markup
      • Avoids navigation, category, blog, support, account URLs
    """
    # ── Setup ────────────────────────────────────────────────────────────────
    def _cb(pct, msg):
        if progress_cb: progress_cb(pct, msg)

    base_parsed = urllib_parse.urlparse(category_url)
    base_origin = f"{base_parsed.scheme}://{base_parsed.netloc}"
    netloc_low  = base_parsed.netloc.lower().lstrip("www.")

    # ════════════════════════════════════════════════════════════════════════
    # ── Fouani-specific handler ──────────────────────────────────────────────
    # fouanistore.com category/search pages embed ALL product data in
    # __NEXT_DATA__.props.pageProps.hits — no individual page scraping needed.
    # URL formats:
    #   fouanistore.com/search?categories=Refrigerator
    #   fouanistore.com/search?categories=TV&brand=LG
    #   fouanistore.com/category/refrigerator   (also uses __NEXT_DATA__)
    # Pagination: perPage products per page, totalPages pages.
    #   Add &page=2, &page=3 ... to the URL.
    # ════════════════════════════════════════════════════════════════════════
    if "fouanistore.com" in netloc_low:
        _cb(2, f"Detected fouanistore.com — extracting from __NEXT_DATA__…")

        _f_headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0.0.0 Safari/537.36"),
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
            "Accept-Language": "en-US,en;q=0.9",
        }

        def _fetch_fouani_page_html(url: str) -> str:
            """Fetch a Fouani page HTML with requests → Playwright fallback."""
            try:
                r = requests.get(url, headers=_f_headers, timeout=15,
                                 allow_redirects=True)
                if r.status_code == 200 and "__NEXT_DATA__" in r.text:
                    return r.text
            except Exception:
                pass
            try:
                return _fetch_html_playwright(url, wait_ms=3000)
            except Exception:
                return ""

        def _extract_fouani_hits(html: str) -> tuple:
            """
            Parse __NEXT_DATA__ from a Fouani category page HTML.
            Returns (hits_list, total_pages).
            """
            m = re.search(
                r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                html, re.DOTALL)
            if not m:
                return [], 1
            try:
                nd       = json.loads(m.group(1))
                pp       = nd.get("props", {}).get("pageProps", {})
                hits     = pp.get("hits", [])
                total_pg = pp.get("totalPages", 1)
                return hits, int(total_pg)
            except Exception:
                return [], 1

        def _hit_to_result(hit: dict) -> dict:
            """
            Convert a single Fouani hits[] item to our canonical result dict.
            All the data we need is right here:
              id, name, brand, display_price, product_branch.sku,
              product_branch.quantity, image.base_url+origin,
              categories[], subcategories[], rating.avg_rating
            """
            pb    = hit.get("product_branch") or {}
            img   = hit.get("image") or {}
            cats  = hit.get("categories") or []
            subs  = hit.get("subcategories") or []
            rat   = hit.get("rating") or {}

            # Build image URL from base_url + origin (same as _scrape_fouani)
            img_url = ""
            base = img.get("base_url", "").rstrip("/")
            origin = img.get("origin", "")
            if base and origin:
                img_url = f"{base}/{origin}"

            # Build the canonical product page URL so the result has a link
            prod_id   = hit.get("id") or hit.get("uid") or ""
            prod_name = hit.get("name", "")
            prod_slug = re.sub(r'[^a-z0-9]+', '-',
                                    prod_name.lower()).strip('-')
            prod_url  = (f"https://fouanistore.com/product/{prod_id}?{prod_slug}"
                         if prod_id else "https://fouanistore.com/")

            # Category string
            cat_str = " > ".join(filter(None, cats + subs))

            # Availability
            qty = pb.get("quantity", 0) or 0
            avail = "In Stock" if qty > 0 else "Out of Stock"

            # Price
            price = (pb.get("price") or hit.get("display_price") or
                     hit.get("effective_price") or "")

            # Rating
            avg_rat = rat.get("avg_rating", 0)

            return {
                "URL":            prod_url,
                "Website":        "www.fouanistore.com",
                "Product Name":   prod_name.strip(),
                "Brand":          str(hit.get("brand", "")).strip(),
                "Price":          str(price) if price else "",
                "Currency":       "NGN",
                "Category":       cat_str,
                "Key Features":   "",
                "About This Item":"",
                "Tech & Additional Info": "",
                "Description":    "",
                "Rating":         str(avg_rat) if avg_rat else "",
                "Reviews Count":  str(rat.get("nb_stars", 0) or ""),
                "SKU":            (pb.get("sku") or "").strip(),
                "GTIN":           "",
                "Availability":   avail,
                "Images":         img_url,
                "Warranty":       "",
                "Weight":         "",
                "Dimensions":     "",
                "Colour":         "",
                "Source Category URL": category_url,
            }

        # ── Collect all pages ────────────────────────────────────────────────
        all_results   = []
        parsed_url    = urllib_parse.urlparse(category_url)
        base_qs       = urllib_parse.parse_qs(parsed_url.query, keep_blank_values=True)

        page_num  = 1
        total_pgs = 1   # will be updated after first page

        while page_num <= total_pgs and len(all_results) < max_products:
            # Build paged URL — add/replace ?page=N
            paged_qs = {k: v[0] for k, v in base_qs.items()}
            paged_qs["page"] = str(page_num)
            paged_url = urllib_parse.urlunparse(
                parsed_url._replace(
                    query=urllib_parse.urlencode(paged_qs)))

            _cb(min(5 + page_num * 4, 30),
                f"Fouani: fetching page {page_num}/{total_pgs}: "
                f"{paged_url[:55]}…")

            html = _fetch_fouani_page_html(paged_url)
            if not html:
                _cb(0, f"Fouani: could not fetch page {page_num}")
                break

            hits, total_pgs = _extract_fouani_hits(html)
            if not hits:
                _cb(0, "Fouani: no products found in __NEXT_DATA__")
                break

            for hit in hits:
                if len(all_results) >= max_products:
                    break
                if isinstance(hit, dict) and hit.get("name"):
                    all_results.append(_hit_to_result(hit))

            _cb(min(5 + page_num * 4, 30),
                f"Fouani: page {page_num}/{total_pgs} — "
                f"{len(all_results)} products collected")
            page_num += 1

        if all_results:
            # Optionally enrich each result by fetching the individual product
            # page for full description/key features (Fouani listing only has
            # name, price, sku, image — no description bullets or attributes).
            # We do this only if we have few enough results to not be too slow.
            total = len(all_results)
            _cb(35, f"Fouani: enriching {total} products with full details…")
            for idx, result in enumerate(all_results):
                pct = 35 + int((idx / total) * 55)
                _cb(pct, f"Fouani: enriching {idx+1}/{total}: "
                    f"{result.get('Product Name','')[:45]}…")
                try:
                    full = _scrape_fouani(result["URL"])
                    if full.get("Product Name"):
                        # Merge full data — keep listing fields if full is empty
                        for field in ("Key Features", "Tech & Additional Info",
                                      "Description", "GTIN", "Warranty",
                                      "Weight", "Dimensions", "Colour",
                                      "Reviews Count", "Rating"):
                            if full.get(field):
                                result[field] = full[field]
                        # Prefer full images (multiple) over single listing image
                        if full.get("Images") and "," in full.get("Images", ""):
                            result["Images"] = full["Images"]
                except Exception:
                    pass  # keep the listing data if enrichment fails

            _cb(97, f"Fouani: done — {len(all_results)} products scraped.")
            return all_results

        # If __NEXT_DATA__ gave no results, fall through to generic scraper
        _cb(5, "Fouani: __NEXT_DATA__ empty — trying generic link extraction…")

    # ════════════════════════════════════════════════════════════════════════
    # ── Samsung-specific handler ─────────────────────────────────────────────
    # Samsung Africa (and all Samsung regional sites) use AEM + client-side JS.
    # The category page HTML contains an EMPTY product list div — products are
    # fetched AFTER page load via the Samsung Product Finder API:
    #   https://searchapi.samsung.com/v6/front/page/category
    # Required params are embedded as hidden <input> elements in the HTML:
    #   #pfCategoryTypeCode, #pfCategoryGroupCode, #siteCode, #pfPriceCurrency
    # Each API result has a pdURL (product detail page path) and model info.
    # Pagination: start=1, num=20, increment start by 20 each page.
    # ════════════════════════════════════════════════════════════════════════
    if "samsung.com" in netloc_low:
        _cb(2, f"Detected samsung.com — using Product Finder API…")

        _sam_headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0.0.0 Safari/537.36"),
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": category_url,
        }

        def _fetch_samsung_html(url: str) -> str:
            """Fetch Samsung page HTML with requests → Playwright fallback."""
            try:
                r = requests.get(url, headers=_sam_headers, timeout=15,
                                 allow_redirects=True)
                if r.status_code == 200:
                    return r.text
            except Exception:
                pass
            try:
                return _fetch_html_playwright(url, wait_ms=3000)
            except Exception:
                return ""

        def _extract_sam_params(html: str) -> dict:
            """
            Extract Samsung Product Finder API params from hidden inputs.
            Returns dict with keys: site, type_code, group_code, currency, lang
            """
            params = {}
            for input_id, param_key, default in [
                ("siteCode",            "site",       "africa_en"),
                ("pfCategoryTypeCode",  "type_code",  ""),
                ("pfCategoryGroupCode", "group_code", ""),
                ("pfPriceCurrency",     "currency",   "USD"),
                ("language",            "lang",       "en-001"),
            ]:
                m = re.search(
                    rf'id="{input_id}"[^>]*value="([^"]*)"', html)
                params[param_key] = m.group(1) if m else default
            return params

        # Fetch the category page HTML to extract API params
        _sam_html = _fetch_samsung_html(category_url)
        _sam_params = _extract_sam_params(_sam_html) if _sam_html else {}

        if _sam_params.get("type_code"):
            site       = _sam_params["site"]
            type_code  = _sam_params["type_code"]
            group_code = _sam_params["group_code"]
            currency   = _sam_params["currency"]
            # Normalise language code (AEM uses en-001 / en-002 etc.)
            lang = re.sub(r'-0+(\d+)$', r'-\1', _sam_params.get("lang", "en-001"))

            _sam_results  = []
            _sam_api_base = "https://searchapi.samsung.com/v6/front/page/category"
            _sam_start    = 1
            _sam_per_page = 20
            _sam_total    = None    # filled after first API call

            _cb(5, f"Samsung API: site={site}, type={type_code}…")

            while len(_sam_results) < max_products:
                _sam_api_url = (
                    f"{_sam_api_base}?"
                    f"site={site}&lang={lang}&"
                    f"type={type_code}&group={group_code}&"
                    f"filter=&sort=Recommended&"
                    f"start={_sam_start}&num={_sam_per_page}&"
                    f"currency={currency}"
                )
                try:
                    resp = requests.get(_sam_api_url, headers=_sam_headers, timeout=15)
                    if resp.status_code != 200:
                        break
                    data = resp.json()
                except Exception:
                    break

                # Unwrap the API response
                # Shape: {"response": {"resultData": {"productList": [...], "totalCount": N}}}
                result_data = (data.get("response", {})
                                   .get("resultData", {}) or data.get("resultData", {}))
                if not result_data:
                    # Try flat shape: {"productList": [...], "totalCount": N}
                    result_data = data

                product_list = (result_data.get("productList") or
                                result_data.get("products") or
                                result_data.get("items") or [])
                if _sam_total is None:
                    _sam_total = int(result_data.get("totalCount", 0) or
                                     result_data.get("total", 0) or
                                     len(product_list))

                if not product_list:
                    break

                for prod in product_list:
                    if not isinstance(prod, dict):
                        continue
                    if len(_sam_results) >= max_products:
                        break

                    # Build product detail URL from pdURL field
                    pd_url = prod.get("pdURL") or prod.get("url") or ""
                    if pd_url and not pd_url.startswith("http"):
                        pd_url = f"https://www.samsung.com{pd_url}"

                    # Extract available listing data
                    model_code = (prod.get("modelCode") or prod.get("modelId") or
                                  prod.get("model") or "")
                    prod_name  = (prod.get("displayName") or prod.get("modelName") or
                                  prod.get("name") or model_code or "")
                    brand      = "Samsung"
                    price_val  = (prod.get("price") or prod.get("priceDisplay") or
                                  prod.get("minPrice") or "")
                    img_url    = prod.get("thumbUrl") or prod.get("imageUrl") or ""
                    if img_url and img_url.startswith("//"):
                        img_url = "https:" + img_url

                    if not pd_url and not prod_name:
                        continue

                    _sam_results.append({
                        "URL":            pd_url or category_url,
                        "Website":        f"www.samsung.com",
                        "Product Name":   prod_name.strip(),
                        "Brand":          brand,
                        "Price":          str(price_val) if price_val else "",
                        "Currency":       currency,
                        "Category":       "",
                        "Key Features":   "",
                        "About This Item": "",
                        "Tech & Additional Info": "",
                        "Description":    "",
                        "Rating":         "",
                        "Reviews Count":  "",
                        "SKU":            model_code.strip(),
                        "GTIN":           "",
                        "Availability":   "",
                        "Images":         img_url,
                        "Warranty":       "",
                        "Weight":         "",
                        "Dimensions":     "",
                        "Colour":         "",
                        "Source Category URL": category_url,
                    })

                # Advance pagination
                _sam_start += _sam_per_page
                if _sam_total and _sam_start > _sam_total:
                    break

                _cb(min(5 + (_sam_start // _sam_per_page) * 3, 25),
                    f"Samsung API: {len(_sam_results)}/{min(_sam_total or 0, max_products)}"
                    f" products collected…")

            if _sam_results:
                # Enrich each product by scraping its detail page
                total = len(_sam_results)
                _cb(28, f"Samsung: enriching {total} products with full details…")
                for idx, result in enumerate(_sam_results):
                    pct = 28 + int((idx / total) * 62)
                    _cb(pct, f"Samsung: enriching {idx+1}/{total}: "
                        f"{result.get('Product Name','')[:40]}…")
                    if result.get("URL") and result["URL"] != category_url:
                        try:
                            full = _normalise(_scrape_page(result["URL"]))
                            for field in ("Product Name", "Key Features",
                                          "Tech & Additional Info", "Description",
                                          "GTIN", "Warranty", "Weight", "Dimensions",
                                          "Colour", "Rating", "Reviews Count",
                                          "Category", "Availability", "Price"):
                                if full.get(field) and not result.get(field):
                                    result[field] = full[field]
                            # Prefer multiple product images over single thumbnail
                            if full.get("Images") and "," in full.get("Images", ""):
                                result["Images"] = full["Images"]
                            elif full.get("Images") and not result.get("Images"):
                                result["Images"] = full["Images"]
                        except Exception:
                            pass

                _cb(97, f"Samsung: done — {len(_sam_results)} products scraped.")
                return _sam_results

        # API failed or returned no products — try Playwright to load the
        # JS-rendered product grid, then extract product links generically
        _cb(5, "Samsung: API returned no products — trying Playwright…")
        if not _sam_html:
            _sam_html = ""
        try:
            _sam_html_pw = _fetch_html_playwright(category_url, wait_ms=5000)
            if _sam_html_pw:
                _sam_html = _sam_html_pw
        except Exception:
            pass


    # ── URL path patterns that indicate a product detail page ────────────────
    _PRODUCT_PATH_PATTERNS = [
        r'/product[s]?/[^/]+/?$',
        r'/p/[^/]+/?$',
        r'/item/[^/]+/?$',
        r'/dp/[A-Z0-9]{10}',
        r'/smartphones?/[^/]+/?$',
        r'/phones?/[^/]+/?$',
        r'/laptop[s]?/[^/]+/?$',
        r'/tablet[s]?/[^/]+/?$',
        r'/tv[s]?/[^/]+/?$',
        r'/television[s]?/[^/]+/?$',
        r'/refrigerator[s]?/[^/]+/?$',
        r'/washing[- ]machine[s]?/[^/]+/?$',
        r'/air[- ]conditioner[s]?/[^/]+/?$',
        r'/speaker[s]?/[^/]+/?$',
        r'/inverter[s]?/[^/]+/?$',
        r'/solar[- ]panel[s]?/[^/]+/?$',
        r'/galaxy/[^/]+/?$',
        r'/iphone[- ][^/]+/?$',
        r'/buy/[^/]+/?$',
        r'/detail[s]?/[^/]+/?$',
        r'[?&]sku=',
        r'[?&]product[_-]?id=',
        r'/[a-z0-9\-]+-\d{5,}/?$',     # slug ending with long numeric ID
        r'/N\d{7,}[A-Z]/p/',            # Noon SKU pattern
    ]
    _PROD_RE = [re.compile(p, re.IGNORECASE) for p in _PRODUCT_PATH_PATTERNS]

    # Path fragments that indicate NON-product pages
    _SKIP_FRAGMENTS = {
        '/search', '/category', '/categories', '/brand', '/brands',
        '/blog', '/news', '/article', '/press', '/about', '/contact',
        '/support', '/help', '/faq', '/policy', '/terms', '/privacy',
        '/login', '/register', '/account', '/cart', '/wishlist', '/checkout',
        '/compare', '/sitemap', '/tag', '/filter', '/sort',
        '#', 'javascript:', 'mailto:', 'tel:',
    }

    def _is_product_url(href: str) -> bool:
        """Return True if href looks like a product detail page URL."""
        if not href or not href.startswith("http"):
            return False
        h_low = href.lower()
        if any(frag in h_low for frag in _SKIP_FRAGMENTS):
            return False
        # Must stay on the same domain
        if netloc_low not in h_low:
            return False
        # Must match at least one product path pattern
        path = urllib_parse.urlparse(href).path
        return any(p.search(path) or p.search(href) for p in _PROD_RE)

    def _make_absolute(href: str, page_url: str) -> str:
        """Convert relative href to absolute URL."""
        if not href:
            return ""
        href = href.strip()
        if href.startswith("http"):
            return href
        if href.startswith("//"):
            return base_parsed.scheme + ":" + href
        if href.startswith("/"):
            return base_origin + href
        # Relative to current page
        return urllib_parse.urljoin(page_url, href)

    def _extract_product_links(html: str, page_url: str) -> list:
        """
        Extract all product detail page links from a category page HTML.
        Uses multiple extraction strategies in order of precision.
        """
        soup = BeautifulSoup(html, "lxml")
        found = []
        seen  = set()

        def _add(href):
            abs_url = _make_absolute(href, page_url)
            if abs_url and abs_url not in seen and _is_product_url(abs_url):
                seen.add(abs_url)
                found.append(abs_url)

        # Strategy 1: itemprop="url" on Product schema markup
        for tag in soup.find_all(attrs={"itemprop": "url"}):
            _add(tag.get("href") or tag.get("content") or "")

        # Strategy 2: links inside known product card/tile containers
        _CARD_SELS = [
            # Generic product card containers
            "[class*='product-card'] a", "[class*='product-item'] a",
            "[class*='product-tile'] a", "[class*='product-cell'] a",
            "[class*='product-thumb'] a", "[class*='prod-card'] a",
            "[class*='item-card'] a",   "[class*='item-tile'] a",
            # Amazon
            "[data-component-type='s-search-result'] a",
            "h2.a-size-mini a", ".s-result-item h2 a",
            # Noon
            "[class*='productContainer'] a", "[class*='sc-product'] a",
            # Jumia
            "[class*='sku-'] a", "article.c-prd-grid-item a",
            # Samsung
            "[class*='product-card'] a", "[class*='CardProduct'] a",
            # LG
            "[class*='product-list__item'] a",
            # Generic e-commerce
            ".products li a", ".product-list a",
            "[class*='grid-item'] a", "[class*='listing-item'] a",
            "[class*='catalog-item'] a",
        ]
        for sel in _CARD_SELS:
            for a in soup.select(sel):
                _add(a.get("href", ""))

        # Strategy 3: ALL <a href> links whose path matches product patterns
        # (broad fallback — catches any site not covered by card selectors)
        if len(found) < 3:
            for a in soup.find_all("a", href=True):
                _add(a["href"])

        return found

    def _find_next_page(html: str, page_url: str) -> str:
        """Return the URL of the next pagination page, or '' if none."""
        soup = BeautifulSoup(html, "lxml")
        # Look for rel="next" link (canonical pagination)
        tag = soup.find("link", rel="next") or soup.find("a", rel="next")
        if tag:
            href = tag.get("href", "")
            if href:
                return _make_absolute(href, page_url)
        # Common "Next" button selectors
        for sel in [
            "a[class*='next']", "a[class*='Next']",
            "[class*='pagination'] a[class*='next']",
            "[class*='pager'] a[aria-label*='Next']",
            "a[aria-label='Next page']", "a[title='Next']",
            ".next-page a", "#next a",
        ]:
            el = soup.select_one(sel)
            if el and el.get("href"):
                return _make_absolute(el["href"], page_url)
        # Last resort: look for an <a> whose text is "Next" / "›" / "»"
        for a in soup.find_all("a", href=True):
            txt = a.get_text(strip=True).lower()
            if txt in ("next", "next page", "›", "»", ">", "→"):
                return _make_absolute(a["href"], page_url)
        return ""

    # ── Fetch category page(s) and collect product links ─────────────────────
    _cb(2, f"Fetching category page: {category_url[:55]}…")

    all_product_urls = []
    seen_urls        = set()
    current_url      = category_url
    page_num         = 1
    _MAX_PAGES       = 10  # safety limit on pagination

    while current_url and len(all_product_urls) < max_products and page_num <= _MAX_PAGES:
        _cb(min(5 + page_num * 3, 25),
            f"Scanning page {page_num}: {current_url[:55]}…")

        html = None

        # Try requests first (fast)
        try:
            resp = requests.get(current_url, headers=_headers(), timeout=15,
                                allow_redirects=True)
            if resp.status_code == 200:
                html = resp.text
            elif resp.status_code in (403, 429, 503):
                try:
                    import cloudscraper as _cs_cat
                    cs  = _cs_cat.create_scraper(
                        browser={"browser": "chrome", "platform": "windows"})
                    html = cs.get(current_url, timeout=20).text
                except Exception:
                    pass
        except Exception:
            pass

        # Playwright fallback (JS-rendered pages, Cloudflare, etc.)
        if not html:
            try:
                html = _fetch_html_playwright(current_url, wait_ms=3500)
            except Exception as _pw_err:
                _cb(0, f"Could not fetch page {page_num}: {_pw_err}")
                break

        if not html:
            break

        # Extract product links from this page
        links = _extract_product_links(html, current_url)
        for lnk in links:
            if lnk not in seen_urls:
                seen_urls.add(lnk)
                all_product_urls.append(lnk)

        _cb(min(5 + page_num * 3, 25),
            f"Page {page_num}: found {len(links)} product links "
            f"({len(all_product_urls)} total so far)…")

        # Pagination
        next_url = _find_next_page(html, current_url)
        if next_url and next_url != current_url and next_url not in seen_urls:
            current_url = next_url
            page_num   += 1
        else:
            break

    all_product_urls = all_product_urls[:max_products]
    total = len(all_product_urls)

    if total == 0:
        return []

    # ── Scrape each discovered product URL ────────────────────────────────────
    results = []
    for idx, prod_url in enumerate(all_product_urls):
        pct = 25 + int((idx / total) * 70)
        _cb(pct, f"Scraping product {idx+1}/{total}: {prod_url[:55]}…")
        try:
            r = _normalise(_scrape_page(prod_url))
            r = _ensure_hd_images(r)
            if not r.get("GTIN"):
                r["GTIN"] = _extract_gtin(r)
            r["Source Category URL"] = category_url
            results.append(r)
        except Exception as _e:
            results.append({
                "URL": prod_url, "Website": netloc_low,
                "Product Name": prod_url, "Error": str(_e),
                "Source Category URL": category_url,
            })

    _cb(97, f"Done — scraped {len(results)} products from category.")
    return results


