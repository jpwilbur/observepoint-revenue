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
