"""Deterministic scope / usage / price engine for the ObservePoint scope-calculator.

No network and no LLM arithmetic. Pure functions plus a CLI that reads an inputs
JSON (file arg or stdin) and writes a full breakdown JSON to stdout.
"""
import json
import sys

# Spec §4.4 — last-known-good graduated audit page-scan tiers (band width, rate/page).
# Single source of truth for the baked fallback; fetch_pricing imports this.
BAKED_TIERS = [
    {"limit": 1_000,      "pricePerPage": 0.0},
    {"limit": 50_000,     "pricePerPage": 0.17},
    {"limit": 500_000,    "pricePerPage": 0.12},
    {"limit": 1_000_000,  "pricePerPage": 0.06},
    {"limit": 5_000_000,  "pricePerPage": 0.04},
    {"limit": 50_000_000, "pricePerPage": 0.03},
]
BAKED_AS_OF = "2026-06-06"


def graduated_price(scans, tiers):
    """Graduated/marginal price: each band's width priced at its rate, summed.
    Mirrors the website's calculateTierBreakdown exactly. Returns
    {total, breakdown:[{band_limit, rate, pages, cost}], avg_per_page}."""
    remaining = int(scans)
    breakdown = []
    total = 0.0
    for band in tiers:
        pages = min(band["limit"], remaining)
        if pages <= 0:
            continue
        cost = pages * band["pricePerPage"]
        total += cost
        remaining -= pages
        breakdown.append({
            "band_limit": band["limit"],
            "rate": band["pricePerPage"],
            "pages": pages,
            "cost": round(cost, 2),
        })
        if remaining <= 0:
            break
    if remaining > 0:  # beyond defined bands: price the tail at the last band's rate
        rate = tiers[-1]["pricePerPage"]
        cost = remaining * rate
        total += cost
        breakdown.append({"band_limit": None, "rate": rate, "pages": remaining, "cost": round(cost, 2)})
    avg = round(total / scans, 4) if scans else 0.0
    return {"total": round(total, 2), "breakdown": breakdown, "avg_per_page": avg}


def classify_tier(scans):
    """Website $F classifier: starter < 600k <= professional <= 6M < enterprise."""
    if scans < 600_000:
        return "starter"
    if scans <= 6_000_000:
        return "professional"
    return "enterprise"


def use_case_pages(base_pages, geographies=1, scenarios=1, environments=1.0):
    """base × geos × scenarios × environments (geos×scenarios = the website's
    geoPersonaMultiplier; environments is 1 or 1.5)."""
    return base_pages * geographies * scenarios * environments


def annual_scans(ucp, cadence_layers):
    """Additive layered cadence model. cadence_layers: list of
    {name, pct, runs_per_year}. A page may appear in multiple layers (layers are
    additive). Returns {total, by_layer:[{name, pct, runs_per_year, pages, runs}]}."""
    by_layer = []
    total = 0.0
    for layer in cadence_layers:
        pages = ucp * layer["pct"]
        runs = pages * layer["runs_per_year"]
        total += runs
        by_layer.append({
            "name": layer["name"],
            "pct": layer["pct"],
            "runs_per_year": layer["runs_per_year"],
            "pages": round(pages, 2),
            "runs": round(runs, 2),
        })
    return {"total": round(total), "by_layer": by_layer}


def apply_buffer(scans, buffer_pct=0.0):
    """purchased = round(predicted × (1 + buffer))."""
    return round(scans * (1 + buffer_pct))


def _compute_one(base, m, layers, buffer_pct, tiers):
    ucp = use_case_pages(base, m.get("geographies", 1), m.get("scenarios", 1),
                         m.get("environments", 1))
    sc = annual_scans(ucp, layers)
    predicted = sc["total"]
    purchased = apply_buffer(predicted, buffer_pct)
    return {
        "base_pages": base,
        "use_case_pages": round(ucp),
        "predicted_scans": predicted,
        "purchased_scans": purchased,
        "buffer_pct": buffer_pct,
        "cadence_by_layer": sc["by_layer"],
        "implied_blended_frequency": round(predicted / ucp, 3) if ucp else 0,
        "tier": classify_tier(purchased),
        "price": graduated_price(purchased, tiers),
    }


def compute(inputs):
    """Full scope breakdown over the page-count range (low/anchor/high)."""
    pc = inputs["page_count"]
    m = inputs.get("multipliers", {})
    layers = inputs["cadence_layers"]
    buffer_pct = inputs.get("buffer_pct", 0.0)
    tiers = inputs.get("tiers") or BAKED_TIERS

    anchor = _compute_one(pc["anchor"], m, layers, buffer_pct, tiers)
    low = _compute_one(pc["low"], m, layers, buffer_pct, tiers)
    high = _compute_one(pc["high"], m, layers, buffer_pct, tiers)

    return {
        "customer": inputs.get("customer"),
        "use_case": inputs.get("use_case"),
        "pricing_source": inputs.get("pricing_source", f"baked ({BAKED_AS_OF})"),
        "confidence": pc.get("confidence"),
        "multipliers": {
            "geographies": m.get("geographies", 1),
            "scenarios": m.get("scenarios", 1),
            "environments": m.get("environments", 1),
            "combined_geo_persona": m.get("geographies", 1) * m.get("scenarios", 1),
        },
        "anchor": anchor,
        "range": {
            "low": {"predicted_scans": low["predicted_scans"],
                    "purchased_scans": low["purchased_scans"],
                    "price_total": low["price"]["total"]},
            "high": {"predicted_scans": high["predicted_scans"],
                     "purchased_scans": high["purchased_scans"],
                     "price_total": high["price"]["total"]},
        },
        "recommended_quote": {
            "purchased_scans": anchor["purchased_scans"],
            "price_total": anchor["price"]["total"],
            "tier": anchor["tier"],
        },
    }


def main(argv):
    raw = open(argv[1]).read() if len(argv) > 1 else sys.stdin.read()
    print(json.dumps(compute(json.loads(raw)), indent=2))


if __name__ == "__main__":
    main(sys.argv)
