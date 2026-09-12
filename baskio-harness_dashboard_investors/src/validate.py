"""Structural and data-sanity checks run on every build before it is promoted.

Returns a list of issue strings; an empty list means the build passed.
This is the harness's "quality gate" — a candidate that fails here never
overwrites the last known-good dashboard.
"""
import re


REQUIRED_IDS = [
    "meta-updated", "meta-coverage", "meta-count", "wl-rows", "wl-filters",
    "main-chart", "c-name", "c-price", "city-grid",
    "rank-gainers", "rank-losers", "rank-volatile", "cat-bars", "narrative-list",
    "forecast-title", "fc-price-7d", "fc-price-30d", "fc-signal", "fc-trend",
    "disclaimer-text", "lang-es", "lang-en",
]

MIN_PRODUCTS = 5
MIN_COVERAGE_DAYS = 300  # a "last year" dashboard should cover close to 365 days


def validate_dataset(dataset: dict) -> list[str]:
    issues = []
    n = dataset.get("meta", {}).get("n_products", 0)
    if n < MIN_PRODUCTS:
        issues.append(f"Only {n} products with full history (< {MIN_PRODUCTS} minimum) — data source looks thin.")

    for p in dataset.get("products", []):
        if "�" in (p.get("nombre") or "") or "�" in (p.get("categoria") or ""):
            issues.append(f"Mojibake detected in product '{p.get('id')}' (nombre/categoria).")
        if p.get("current") is None or p["current"] <= 0:
            issues.append(f"Product '{p.get('id')}' has an invalid current price: {p.get('current')!r}.")
        fc = p.get("forecast")
        if not fc or fc.get("signal") not in ("SUBIR", "BAJAR", "ESTABLE"):
            issues.append(f"Product '{p.get('id')}' is missing a valid forecast signal.")

    insights = dataset.get("insights", {})
    if not insights.get("top_gainers") or not insights.get("top_losers"):
        issues.append("Insights block is missing top_gainers/top_losers.")
    if not insights.get("category_performance"):
        issues.append("Insights block is missing category_performance.")

    meta = dataset.get("meta", {})
    try:
        from datetime import date
        start = date.fromisoformat(meta["start_date"])
        end = date.fromisoformat(meta["max_date"])
        if (end - start).days < MIN_COVERAGE_DAYS:
            issues.append(
                f"Coverage window is only {(end - start).days} days (< {MIN_COVERAGE_DAYS}) — "
                "this is not really a 'last year' view."
            )
    except Exception as e:
        issues.append(f"Could not parse meta date range: {e}")

    return issues


def validate_html(html: str) -> list[str]:
    issues = []
    if html.count("<script") != html.count("</script>"):
        issues.append("Unbalanced <script> tags.")
    if html.count("<section") != html.count("</section>"):
        issues.append("Unbalanced <section> tags.")
    if html.count("<div") < html.count("</div>") - 2 or html.count("<div") > html.count("</div>") + 2:
        issues.append("Div open/close counts differ by more than a small tolerance — check for a stray tag.")

    for el_id in REQUIRED_IDS:
        if f'id="{el_id}"' not in html:
            issues.append(f"Missing required element id in rendered HTML: #{el_id}")

    if "__BASKIO_DATA_JSON__" in html:
        issues.append("Data placeholder was never substituted — dataset injection failed.")

    if len(html) < 20_000:
        issues.append(f"Rendered HTML looks too small ({len(html)} bytes) — likely truncated.")

    m = re.search(r"window\.BASKIO_DATA = (.*?);\s*</script>", html, re.S)
    if not m:
        issues.append("Could not find the embedded window.BASKIO_DATA assignment.")

    return issues
