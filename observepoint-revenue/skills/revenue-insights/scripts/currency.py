"""Currency helpers: sum amounts per currency (never cross-convert without an FX rate)
and format money for display. Pure compute; no I/O. Shared by revenue-insights recipes."""

_SYMBOLS = {"USD": "$", "GBP": "£", "EUR": "€", "CAD": "C$", "AUD": "A$"}


def to_number(v):
    """Best-effort float from a number or a '$1,234.50'-style string. '' / None -> None."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    cleaned = str(v).replace(",", "").replace("$", "").replace("£", "").replace("€", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def sum_by_currency(rows, amount_key="arr", currency_key="currency"):
    """{currency_code: summed_amount}. Currencies stay separate — no FX conversion
    (that needs a rate we don't assume). Rows with no usable amount are ignored;
    a missing currency defaults to USD."""
    totals = {}
    for r in rows:
        amt = to_number((r or {}).get(amount_key))
        if amt is None:
            continue
        cur = (str((r or {}).get(currency_key) or "USD").strip().upper()) or "USD"
        totals[cur] = totals.get(cur, 0.0) + amt
    return totals


def format_money(amount, currency="USD", *, decimals=0):
    """'$79,590' / '£1,000' / '1,234 SEK'. Whole units by default. None -> em dash."""
    if amount is None:
        return "—"
    sym = _SYMBOLS.get((currency or "USD").upper())
    n = f"{amount:,.{decimals}f}"
    return f"{sym}{n}" if sym else f"{n} {(currency or '').upper()}".strip()
