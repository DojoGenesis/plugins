#!/bin/sh
# Writes the project files into the current directory.
set -e

cat > 'README.md' <<'__SCAFFOLD_FILE_END__'
# shop

Small product catalogue.

- `shop/config.py`     settings
- `shop/catalog.py`    the products
- `shop/paging.py`     page arithmetic
- `shop/api.py`        `list_products(query)` returns items plus paging info
- `shop/render.py`     text rendering of a listing
- `shop/web.py`        `page(query_string)` ties api and render together
- `shop/export_pdf.py` printed sheets
__SCAFFOLD_FILE_END__

mkdir -p 'shop'
cat > 'shop/__init__.py' <<'__SCAFFOLD_FILE_END__'
"""shop: a tiny product catalogue with paged listings."""
__SCAFFOLD_FILE_END__

mkdir -p 'shop'
cat > 'shop/api.py' <<'__SCAFFOLD_FILE_END__'
"""The listing endpoint, as a plain function."""

from shop import catalog, paging


def list_products(query=None):
    """`query` holds the raw (string) URL parameters: category, page, page_size."""
    query = query or {}
    items = catalog.all_products()
    category = query.get("category")
    if category:
        items = [p for p in items if p["category"] == category]
    result = paging.paginate(items, query.get("page"), query.get("page_size"))
    return {
        "items": result["items"],
        "meta": {key: result[key] for key in ("page", "page_size", "total", "pages")},
    }
__SCAFFOLD_FILE_END__

mkdir -p 'shop'
cat > 'shop/catalog.py' <<'__SCAFFOLD_FILE_END__'
"""The product data (generated, 130 products)."""

_PRODUCTS = [
    {"id": i, "name": f"Product {i:03d}", "category": "tools" if i % 2 else "garden"}
    for i in range(1, 131)
]


def all_products():
    return [dict(p) for p in _PRODUCTS]
__SCAFFOLD_FILE_END__

mkdir -p 'shop'
cat > 'shop/config.py' <<'__SCAFFOLD_FILE_END__'
"""Settings for the shop code."""

# Product listings (API and web pages)
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50

# Rows that fit on one printed catalogue sheet
PDF_PAGE_SIZE = 20
__SCAFFOLD_FILE_END__

mkdir -p 'shop'
cat > 'shop/export_pdf.py' <<'__SCAFFOLD_FILE_END__'
"""Split the catalogue into printed sheets."""

from shop import config


def paginate_for_pdf(items):
    size = config.PDF_PAGE_SIZE
    return [items[i:i + size] for i in range(0, len(items), size)]
__SCAFFOLD_FILE_END__

mkdir -p 'shop'
cat > 'shop/paging.py' <<'__SCAFFOLD_FILE_END__'
"""Page arithmetic shared by the listing code."""

from shop import config


def clamp_page_size(value):
    """Turn a requested page size (any type) into a usable one."""
    try:
        size = int(value)
    except (TypeError, ValueError):
        return config.DEFAULT_PAGE_SIZE
    if size < 1:
        return config.DEFAULT_PAGE_SIZE
    return min(size, config.MAX_PAGE_SIZE)


def clamp_page(value):
    try:
        page = int(value)
    except (TypeError, ValueError):
        return 1
    return max(page, 1)


def paginate(items, page=None, page_size=None):
    size = clamp_page_size(page_size)
    page = clamp_page(page)
    total = len(items)
    start = (page - 1) * size
    return {
        "items": items[start:start + size],
        "page": page,
        "page_size": size,
        "total": total,
        "pages": -(-total // size),
    }
__SCAFFOLD_FILE_END__

mkdir -p 'shop'
cat > 'shop/render.py' <<'__SCAFFOLD_FILE_END__'
"""Plain-text rendering of a listing result."""


def render_listing(result):
    meta = result["meta"]
    total = meta["total"]
    if not result["items"]:
        header = f"Showing 0-0 of {total}"
    else:
        start = (meta["page"] - 1) * 20 + 1
        end = min(meta["page"] * 20, total)
        header = f"Showing {start}-{end} of {total}"
    lines = [header] + [f"- {p['name']}" for p in result["items"]]
    return "\n".join(lines)
__SCAFFOLD_FILE_END__

mkdir -p 'shop'
cat > 'shop/web.py' <<'__SCAFFOLD_FILE_END__'
"""The web page: query string in, text out."""

from urllib.parse import parse_qsl

from shop import api, render


def page(query_string=""):
    query = dict(parse_qsl(query_string))
    return render.render_listing(api.list_products(query))
__SCAFFOLD_FILE_END__
