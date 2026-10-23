"""Plain-text rendering of a listing result."""


def render_listing(result):
    meta = result["meta"]
    total = meta["total"]
    size = meta["page_size"]
    if not result["items"]:
        header = f"Showing 0-0 of {total}"
    else:
        start = (meta["page"] - 1) * size + 1
        end = min(meta["page"] * size, total)
        header = f"Showing {start}-{end} of {total}"
    lines = [header] + [f"- {p['name']}" for p in result["items"]]
    return "\n".join(lines)
