# revenue-insights — Plan 2: Engine + renewals-at-risk anchor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `revenue-insights` engine skill — shared compute helpers, a branded in-chat viz kit, the metrics canon, the request-flow `SKILL.md`, and the first vetted recipe (renewals-at-risk, rebuilding the proven screenshot) — plus the ad-hoc fallback.

**Architecture:** The model calls the SF MCP to gather renewal opps; deterministic Python computes every number (bucketing, currency splits, risk-weighting, caveats) and renders a self-contained branded HTML visual shown in chat. Recipe scripts import `sf_io` from `lib/salesforce` and `brand_kit` from `branding-guide`. Recipe-catalog-first; an ad-hoc generic-aggregate helper covers questions no recipe answers yet.

**Tech Stack:** Python 3 (stdlib only in compute/render), pytest, the Salesforce MCP (`soqlQuery`), `branding-guide/brand_kit` for brand tokens + HTML→PDF on export.

## Global Constraints

- **Interpreter:** always `/opt/homebrew/bin/python3`.
- **Test command:** `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q` (must stay green; never pipe through `| tail` in an `&&` chain).
- **Architecture rule:** no Python script calls SF/Domo/OP; no model arithmetic; no model-held state. **Read-only.**
- **Brand values come from `branding-guide`/`brand_kit` only** — never hardcode a hex/font/logo path in a renderer.
- **Never fabricate** a number/account/source; missing input → labeled default + an "assumptions to verify" note, or an honest "none found".
- **Output location:** `~/Documents/ObservePoint Revenue/revenue-insights/` (rep override honored; `mkdir -p`; never a temp dir).
- **Commit email:** `16406437+jpwilbur@users.noreply.github.com`.
- **Depends on Plan 1:** `lib/salesforce` (sf_io + renewal field map) and `lib/domo` (domo_io + the account-health field), the synthetic fixtures `tests/fixtures/sf/renewals_sample.json` + `tests/fixtures/domo/account_health_sample.json`, fiscal-year start (default 2 = Feb, confirmed in Plan 1). **Health is joined from Domo (`account_health_score`), not SF** — 5 states (green/yellow/red/blue/black).

---

### Task 1: Shared compute helpers (`currency`, `periods`, `risk_weight`) + skill scaffold

Pure functions, the computational core every recipe reuses. Creates the skill scripts dir and registers it for tests.

**Files:**
- Create: `observepoint-revenue/skills/revenue-insights/scripts/currency.py`
- Create: `observepoint-revenue/skills/revenue-insights/scripts/periods.py`
- Create: `observepoint-revenue/skills/revenue-insights/scripts/risk_weight.py`
- Create: `observepoint-revenue/tests/test_revenue_helpers.py`
- Modify: `observepoint-revenue/tests/conftest.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `currency.to_number(v) -> float|None`; `currency.sum_by_currency(rows, amount_key="arr", currency_key="currency") -> dict[str,float]`; `currency.format_money(amount, currency="USD", *, decimals=0) -> str`.
  - `periods.fiscal_quarter(date_iso, fy_start_month=2) -> {"fy_label","quarter","start","end"}`; `periods.in_window(date_iso, start_iso, end_iso) -> bool`.
  - `risk_weight.risk_weighted(amount, health, weights) -> float`.

- [ ] **Step 1: Register the skill scripts dir for tests**

In `observepoint-revenue/tests/conftest.py`, add to the tuple (after the existing skill entries):

```python
    "skills/revenue-insights/scripts",
```

- [ ] **Step 2: Write the failing tests**

Create `observepoint-revenue/tests/test_revenue_helpers.py`:

```python
import pytest
import currency
import periods
import risk_weight


def test_to_number_handles_currency_strings_blanks():
    assert currency.to_number("$1,234.50") == 1234.5
    assert currency.to_number(1000) == 1000.0
    assert currency.to_number("") is None
    assert currency.to_number(None) is None


def test_sum_by_currency_keeps_currencies_separate():
    rows = [
        {"arr": 79590, "currency": "USD"},
        {"arr": "1,000", "currency": "GBP"},
        {"arr": 410, "currency": "USD"},
        {"arr": None, "currency": "USD"},   # ignored
    ]
    assert currency.sum_by_currency(rows) == {"USD": 80000.0, "GBP": 1000.0}


def test_sum_by_currency_defaults_missing_currency_to_usd():
    assert currency.sum_by_currency([{"arr": 5}]) == {"USD": 5.0}


def test_format_money_symbols_and_fallback():
    assert currency.format_money(79590, "USD") == "$79,590"
    assert currency.format_money(1000, "GBP") == "£1,000"
    assert currency.format_money(1234, "SEK") == "1,234 SEK"
    assert currency.format_money(None) == "—"


def test_fiscal_quarter_feb_start_matches_screenshot():
    q = periods.fiscal_quarter("2026-05-01", fy_start_month=2)
    assert q == {"fy_label": "FY26", "quarter": "Q2",
                 "start": "2026-05-01", "end": "2026-07-31"}


def test_fiscal_quarter_january_belongs_to_prior_fy_q4():
    q = periods.fiscal_quarter("2027-01-15", fy_start_month=2)
    assert q["fy_label"] == "FY26" and q["quarter"] == "Q4"
    assert q["start"] == "2026-11-01" and q["end"] == "2027-01-31"


def test_in_window_inclusive_and_safe():
    assert periods.in_window("2026-07-31", "2026-05-01", "2026-07-31") is True
    assert periods.in_window("2026-08-01", "2026-05-01", "2026-07-31") is False
    assert periods.in_window("", "2026-05-01", "2026-07-31") is False


def test_risk_weighted_applies_health_weight():
    w = {"red": 0.25, "yellow": 0.5}
    assert risk_weight.risk_weighted(65500, "Red", w) == 16375.0
    assert risk_weight.risk_weighted(65200, "yellow", w) == 32600.0
    assert risk_weight.risk_weighted(100, "Green", w) == 0.0   # not in undetermined weights
    assert risk_weight.risk_weighted(None, "Red", w) == 0.0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_revenue_helpers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'currency'`.

- [ ] **Step 4: Implement `currency.py`**

Create `observepoint-revenue/skills/revenue-insights/scripts/currency.py`:

```python
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
```

- [ ] **Step 5: Implement `periods.py`**

Create `observepoint-revenue/skills/revenue-insights/scripts/periods.py`:

```python
"""Fiscal-calendar helpers. fy_start_month defaults to 2 (Feb) per the ObservePoint FY
(confirmed in Plan 1). FY is labeled by its start calendar year (a FY starting Feb 2026
is 'FY26'). Pure date math; stdlib only."""
import calendar
import datetime as _dt


def _parse(d):
    return _dt.date.fromisoformat(str(d)[:10])


def fiscal_quarter(date_iso, fy_start_month=2):
    """Fiscal quarter containing date_iso -> {fy_label, quarter, start, end} (ISO dates)."""
    d = _parse(date_iso)
    idx = (d.month - fy_start_month) % 12            # 0..11 fiscal month index
    quarter = idx // 3 + 1
    fy_start_year = d.year if d.month >= fy_start_month else d.year - 1
    m0 = fy_start_month + (quarter - 1) * 3           # quarter start, 1-based, may exceed 12
    start_year = fy_start_year + (m0 - 1) // 12
    start_month = (m0 - 1) % 12 + 1
    e0 = m0 + 2                                        # quarter end month
    end_year = fy_start_year + (e0 - 1) // 12
    end_month = (e0 - 1) % 12 + 1
    end_day = calendar.monthrange(end_year, end_month)[1]
    return {
        "fy_label": f"FY{fy_start_year % 100:02d}",
        "quarter": f"Q{quarter}",
        "start": f"{start_year:04d}-{start_month:02d}-01",
        "end": f"{end_year:04d}-{end_month:02d}-{end_day:02d}",
    }


def in_window(date_iso, start_iso, end_iso):
    """Inclusive date-in-range test; bad/empty date -> False."""
    try:
        d = _parse(date_iso)
    except (ValueError, TypeError):
        return False
    return _parse(start_iso) <= d <= _parse(end_iso)
```

- [ ] **Step 6: Implement `risk_weight.py`**

Create `observepoint-revenue/skills/revenue-insights/scripts/risk_weight.py`:

```python
"""Risk-weighting: apply a health-based weight to an amount (the 'undetermined' renewal
bucket). Weights live in the metrics canon / are passed in; nothing is hardcoded here."""


def risk_weighted(amount, health, weights):
    """amount * weights[health] (health matched case-insensitively). Missing health or
    amount -> 0.0. `weights` e.g. {'red': 0.25, 'yellow': 0.5}."""
    if amount is None:
        return 0.0
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        return 0.0
    w = weights.get(str(health or "").strip().lower())
    return amt * w if w is not None else 0.0
```

- [ ] **Step 7: Run the helper tests — verify pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_revenue_helpers.py -v`
Expected: PASS (all 8 tests).

- [ ] **Step 8: Run the full suite + commit**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`
Expected: PASS (no regressions).

```bash
cd "observepoint-revenue"
git add skills/revenue-insights/scripts/currency.py skills/revenue-insights/scripts/periods.py \
        skills/revenue-insights/scripts/risk_weight.py tests/test_revenue_helpers.py tests/conftest.py
git -c user.email="16406437+jpwilbur@users.noreply.github.com" commit -m "feat(revenue-insights): shared compute helpers (currency, fiscal periods, risk-weight)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `viz_kit.py` — branded in-chat visual components

The render kit. Pure string-building components (stat cards, ranked tables, health badges, sections, caveats, page wrapper). All colors/fonts/logo come from `brand_kit` — never hardcoded.

**Files:**
- Create: `observepoint-revenue/skills/revenue-insights/scripts/viz_kit.py`
- Create: `observepoint-revenue/tests/test_viz_kit.py`

**Interfaces:**
- Consumes: `brand_kit` (via the `branding-guide/scripts` shim) — `theme`, `colors`, `brand_yellow`, `css_vars`, `logo_data_uri`.
- Produces: `viz_kit.health_badge(health)`, `stat_card(label, value, sub="")`, `section_header(text)`, `ranked_table(columns, rows)` (columns = list of `(header, key_or_callable)`), `caveats(items)`, `page(title, body, *, kicker="", subtitle="")`, and `HEALTH_COLORS` dict. All return HTML strings.

- [ ] **Step 1: Write the failing tests**

Create `observepoint-revenue/tests/test_viz_kit.py`:

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "skills" / "branding-guide" / "scripts"))
import brand_kit
import viz_kit


def test_health_badge_uses_brand_semantic_colors():
    assert brand_kit.colors()["semantic"]["alert"] in viz_kit.health_badge("Red")
    assert brand_kit.colors()["semantic"]["success"] in viz_kit.health_badge("Green")
    assert brand_kit.brand_yellow() in viz_kit.health_badge("Yellow")
    assert brand_kit.colors()["semantic"]["link"] in viz_kit.health_badge("Blue")


def test_stat_card_shows_label_value_sub():
    out = viz_kit.stat_card("Will Not Renew", "6", "opps · $80K at risk")
    assert "Will Not Renew" in out and ">6<" in out and "at risk" in out


def test_ranked_table_renders_headers_and_callable_cells():
    cols = [("ACCOUNT", "account"), ("ARR", lambda r: "$" + str(r["arr"]))]
    out = viz_kit.ranked_table(cols, [{"account": "Acme", "arr": 10}])
    assert "<th>ACCOUNT</th>" in out and "Acme" in out and "$10" in out


def test_caveats_empty_is_blank():
    assert viz_kit.caveats([]) == ""
    assert "verify" in viz_kit.caveats(["please verify"])


def test_page_is_dark_themed_and_titled():
    out = viz_kit.page("Renewals at Risk", "<p>x</p>", kicker="Q2 FY26", subtitle="src")
    assert "Renewals at Risk" in out and "Q2 FY26" in out
    assert "var(--op-bg)" in out and "<!DOCTYPE html>" in out


def test_html_is_escaped():
    assert "&lt;script&gt;" in viz_kit.stat_card("<script>", "1")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_viz_kit.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'viz_kit'`.

- [ ] **Step 3: Implement `viz_kit.py`**

Create `observepoint-revenue/skills/revenue-insights/scripts/viz_kit.py`:

```python
"""Branded in-chat visual kit for revenue-insights. Components emit self-contained,
brand-correct HTML (dark NERD theme). Brand tokens come from branding-guide/brand_kit —
never hardcoded. Pure string building; no data logic."""
import html
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "branding-guide" / "scripts"))
import brand_kit  # noqa: E402

_T = brand_kit.theme("dark")
_SEM = brand_kit.colors()["semantic"]
HEALTH_COLORS = {
    "green": _SEM["success"],
    "yellow": brand_kit.brand_yellow(),
    "red": _SEM["alert"],
    "blue": _SEM["link"],
    "black": _T["muted"],
}


def _e(x):
    return html.escape("" if x is None else str(x))


def health_badge(health):
    c = HEALTH_COLORS.get(str(health or "").strip().lower(), _T["muted"])
    return (f'<span class="hb"><span class="dot" style="background:{c}"></span>'
            f'{_e(health) or "—"}</span>')


def stat_card(label, value, sub=""):
    return (f'<div class="card"><div class="clabel">{_e(label)}</div>'
            f'<div class="cval">{_e(value)}</div>'
            f'<div class="csub">{_e(sub)}</div></div>')


def section_header(text):
    return f'<div class="sh">{_e(text)}</div>'


def ranked_table(columns, rows):
    """columns: list of (header, key) where key is a dict key or a callable(row)->str."""
    head = "".join(f"<th>{_e(h)}</th>" for h, _ in columns)
    body = ""
    for r in rows:
        cells = ""
        for _, key in columns:
            cells += f"<td>{key(r) if callable(key) else _e(r.get(key))}</td>"
        body += f"<tr>{cells}</tr>"
    return (f'<table class="rt"><thead><tr>{head}</tr></thead>'
            f'<tbody>{body}</tbody></table>')


def caveats(items):
    if not items:
        return ""
    lis = "".join(f"<li>{_e(i)}</li>" for i in items)
    return f'<div class="caveats"><ul>{lis}</ul></div>'


def page(title, body, *, kicker="", subtitle=""):
    css = brand_kit.css_vars("dark")
    logo = brand_kit.logo_data_uri("dark")
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
{css}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--op-bg);color:var(--op-text);
 font-family:var(--op-font),system-ui,sans-serif;padding:28px}}
.logo{{height:20px;opacity:.9;margin-bottom:14px}}
.kicker{{color:var(--op-muted);text-transform:uppercase;letter-spacing:.08em;font-size:12px}}
h1{{margin:.1em 0 .2em;font-size:26px}}
.sub{{color:var(--op-muted);margin-bottom:20px;font-size:13px}}
.cards{{display:flex;gap:14px;margin:18px 0}}
.card{{flex:1;background:{_T['panel']};border:1px solid {_T['border']};
 border-radius:10px;padding:16px}}
.clabel{{color:var(--op-muted);text-transform:uppercase;font-size:11px;letter-spacing:.06em}}
.cval{{font-size:30px;font-weight:700;margin:.1em 0}}
.csub{{color:var(--op-muted);font-size:13px}}
.sh{{color:var(--op-accent);text-transform:uppercase;letter-spacing:.06em;
 font-size:12px;margin:22px 0 8px;font-weight:700}}
table.rt{{width:100%;border-collapse:collapse;font-size:14px}}
.rt th{{text-align:left;color:var(--op-muted);font-weight:600;padding:8px 10px;
 border-bottom:1px solid {_T['border']}}}
.rt td{{padding:9px 10px;border-bottom:1px solid {_T['panel2']}}}
.hb{{display:inline-flex;align-items:center;gap:6px}}
.dot{{width:9px;height:9px;border-radius:50%;display:inline-block}}
.caveats{{margin-top:20px;color:var(--op-muted);font-size:13px;
 border-top:1px solid {_T['border']};padding-top:12px}}
</style></head><body>
<img class="logo" src="{logo}" alt="ObservePoint"/>
<div class="kicker">{_e(kicker)}</div>
<h1>{_e(title)}</h1>
<div class="sub">{_e(subtitle)}</div>
{body}
</body></html>"""
```

- [ ] **Step 4: Run the viz tests — verify pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_viz_kit.py -v`
Expected: PASS (all 6 tests).

- [ ] **Step 5: Commit**

```bash
cd "observepoint-revenue"
git add skills/revenue-insights/scripts/viz_kit.py tests/test_viz_kit.py
git -c user.email="16406437+jpwilbur@users.noreply.github.com" commit -m "feat(revenue-insights): branded in-chat viz kit (cards, tables, health badges)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `renewals_at_risk.py` — compute (bucketing, currency, risk-weight, caveats)

The recipe's deterministic compute. Operates on normalized renewal rows; a thin mapper turns raw SF records (per Plan 1 Task 5's field map) into them.

**Files:**
- Create: `observepoint-revenue/skills/revenue-insights/scripts/renewals_at_risk.py`
- Create: `observepoint-revenue/tests/test_renewals_at_risk.py`

**Interfaces:**
- Consumes: `sf_io` (lib/salesforce), `domo_io` (lib/domo), `currency`, `periods`, `risk_weight` (Task 1); Plan 1 Task 5's SF field map + `tests/fixtures/sf/renewals_sample.json`; Plan 1's Domo health field + `tests/fixtures/domo/account_health_sample.json`.
- **Health is NOT in SF — it's joined from Domo.** SF gives account/status/arr/currency/close_date; Domo gives `account_health_score` (color string) + `days_in_current_health` keyed by `account_name`. The recipe joins on normalized account name.
- Produces: `renewals_at_risk.DEFAULT_FIELD_MAP` (SF, no health), `RENEWAL_WEIGHTS`, `health_token(s) -> str|None` (extract green/yellow/red/black/blue from a string), `normalize_sf_records(records, field_map=DEFAULT_FIELD_MAP) -> list[dict]` (no health), `health_by_account(domo_health_records) -> dict[str,str]` (normalized account name → color token), `join_health(sf_rows, health_map) -> list[dict]` (adds `health`), `compute_from_normalized(rows, *, today_iso, fy_start_month=2, weights=None) -> dict`, `compute(sf_records, health_records, *, today_iso, fy_start_month=2, weights=None, field_map=DEFAULT_FIELD_MAP) -> dict`. Result dict shape: `{period, summary:{will_renew, undetermined, will_not_renew}, will_not_renew_rows, undetermined_rows, caveats}`.

- [ ] **Step 1: Write the failing tests**

Create `observepoint-revenue/tests/test_renewals_at_risk.py`:

```python
import renewals_at_risk as rar


NORM = [
    {"account": "Acme", "status": "Will Renew", "health": "Green",
     "arr": 1000, "currency": "USD", "close_date": "2026-07-01"},
    {"account": "Globex", "status": "Will Not Renew", "health": "Yellow",
     "arr": 500, "currency": "USD", "close_date": "2026-07-10"},
    {"account": "Initech", "status": "Will Not Renew", "health": "Green",
     "arr": 200, "currency": "GBP", "close_date": "2026-07-12"},
    {"account": "Umbrella", "status": "Undetermined", "health": "Red",
     "arr": 400, "currency": "USD", "close_date": "2026-07-20"},
    {"account": "Soylent", "status": "Undetermined", "health": "Yellow",
     "arr": 1000, "currency": "GBP", "close_date": "2026-07-22"},
]


def test_buckets_count_and_currency_split():
    r = rar.compute_from_normalized(NORM, today_iso="2026-06-26")
    s = r["summary"]
    assert s["will_renew"]["count"] == 1
    assert s["will_not_renew"]["count"] == 2
    assert s["will_not_renew"]["arr"] == {"USD": 500.0, "GBP": 200.0}
    assert s["undetermined"]["count"] == 2


def test_undetermined_is_risk_weighted_by_currency():
    r = rar.compute_from_normalized(NORM, today_iso="2026-06-26")
    # Red 400*0.25 = 100 USD; Yellow 1000*0.5 = 500 GBP
    assert r["summary"]["undetermined"]["risk_weighted"] == {"USD": 100.0, "GBP": 500.0}


def test_period_is_q2_fy26():
    r = rar.compute_from_normalized(NORM, today_iso="2026-06-26")
    assert r["period"]["quarter"] == "Q2" and r["period"]["fy_label"] == "FY26"


def test_green_but_will_not_renew_raises_a_caveat():
    r = rar.compute_from_normalized(NORM, today_iso="2026-06-26")
    assert any("Initech" in c and "Green" in c for c in r["caveats"])


def test_rows_sorted_by_arr_desc():
    r = rar.compute_from_normalized(NORM, today_iso="2026-06-26")
    arrs = [row["arr"] for row in r["will_not_renew_rows"]]
    assert arrs == sorted(arrs, reverse=True)


def test_normalize_sf_maps_nested_account_name_no_health():
    # SF does NOT carry health (confirmed in Plan 1 Task 5) — normalize_sf_records omits it.
    raw = [{"Account": {"Name": "Acme"}, "Renewal_Forecast__c": "Will Not Renew",
            "Renewable_ARR__c": 200, "CurrencyIsoCode": "GBP", "CloseDate": "2026-07-12"}]
    norm = rar.normalize_sf_records(raw)
    assert norm[0]["account"] == "Acme" and norm[0]["arr"] == 200
    assert norm[0]["currency"] == "GBP" and norm[0]["status"] == "Will Not Renew"
    assert "health" not in norm[0] or norm[0]["health"] is None


def test_health_token_extracts_color_from_string():
    assert rar.health_token("Green") == "green"
    assert rar.health_token("Red - At Risk") == "red"
    assert rar.health_token("BLUE") == "blue"
    assert rar.health_token("") is None
    assert rar.health_token(None) is None


def test_health_by_account_and_join():
    domo_health = [
        {"account_name": "Acme", "account_health_score": "Green", "days_in_current_health": 10},
        {"account_name": "Globex", "account_health_score": "Red - At Risk", "days_in_current_health": 5},
    ]
    hmap = rar.health_by_account(domo_health)
    assert hmap == {"acme": "green", "globex": "red"}
    sf_rows = [
        {"account": "Acme", "status": "Will Renew", "arr": 1, "currency": "USD", "close_date": "2026-07-01"},
        {"account": "Nomatch", "status": "Undetermined", "arr": 2, "currency": "USD", "close_date": "2026-07-01"},
    ]
    joined = rar.join_health(sf_rows, hmap)
    assert joined[0]["health"] == "green"
    assert joined[1]["health"] is None   # no Domo health for this account
```

> **Field-name note:** `DEFAULT_FIELD_MAP` and the Domo health columns (`account_name`, `account_health_score`) are the names **confirmed in Plan 1** (`lib/salesforce/salesforce-org.md` Renewals + `lib/domo/domo-datasets.md` Account health). The fixtures already use them.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_renewals_at_risk.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'renewals_at_risk'`.

- [ ] **Step 3: Implement `renewals_at_risk.py` (compute only — render/main added in Task 4)**

Create `observepoint-revenue/skills/revenue-insights/scripts/renewals_at_risk.py`:

```python
"""renewals-at-risk recipe (RevOps/CSM): SF renewal opps + Domo account health -> bucketed
at-risk view. The MODEL runs the renewal SOQL (lib/salesforce/salesforce-org.md) and the Domo
health query (lib/domo/domo-datasets.md "Account health"); this script joins them and computes
every number. No SF/Domo calls, no model math."""
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[3] / "lib" / "salesforce"))
sys.path.insert(0, str(_HERE.parents[3] / "lib" / "domo"))
import sf_io  # noqa: E402
import domo_io  # noqa: E402
import currency  # noqa: E402  (same scripts dir, on sys.path at runtime + via conftest)
import periods  # noqa: E402
import risk_weight  # noqa: E402

# Undetermined-bucket risk weights — see metrics-canon.md (matches the proven report).
RENEWAL_WEIGHTS = {"red": 0.25, "yellow": 0.5}

# SF renewal fields -> normalized keys (confirmed Plan 1; health is NOT here — joined from Domo).
DEFAULT_FIELD_MAP = {
    "account": "Account.Name",
    "status": "Renewal_Forecast__c",
    "arr": "Renewable_ARR__c",
    "currency": "CurrencyIsoCode",
    "close_date": "CloseDate",
}

_HEALTH_COLORS = ("green", "yellow", "red", "blue", "black")


def _get(rec, path):
    cur = rec
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _norm_acct(name):
    return str(name or "").strip().lower()


def health_token(s):
    """Extract the color token from a Domo account_health_score string (e.g. 'Red - At Risk'
    -> 'red'). Returns None if no known color is present."""
    low = str(s or "").lower()
    for c in _HEALTH_COLORS:
        if c in low:
            return c
    return None


def normalize_sf_records(records, field_map=DEFAULT_FIELD_MAP):
    """SF renewal records -> normalized rows (account/status/arr/currency/close_date). No health."""
    out = []
    for r in records:
        out.append({
            "account": _get(r, field_map["account"]),
            "status": _get(r, field_map["status"]),
            "arr": _get(r, field_map["arr"]),
            "currency": _get(r, field_map["currency"]) or "USD",
            "close_date": _get(r, field_map["close_date"]),
        })
    return out


def health_by_account(domo_health_records):
    """Domo health rows -> {normalized account_name: color token}."""
    out = {}
    for r in domo_health_records:
        acct = _norm_acct(r.get("account_name"))
        tok = health_token(r.get("account_health_score"))
        if acct and tok:
            out[acct] = tok
    return out


def join_health(sf_rows, health_map):
    """Add a `health` color token to each SF row from the Domo health map (None if no match)."""
    return [{**r, "health": health_map.get(_norm_acct(r["account"]))} for r in sf_rows]


def _bucket(status):
    s = str(status or "").strip().lower()
    if "not" in s:                      # 'Will Not Renew', 'WNR'
        return "will_not_renew"
    if "undeterm" in s or "unknown" in s:
        return "undetermined"
    if "renew" in s:
        return "will_renew"
    return "undetermined"               # unmapped -> conservative


def _sort(rows):
    return sorted(rows, key=lambda r: currency.to_number(r["arr"]) or 0.0, reverse=True)


def compute_from_normalized(rows, *, today_iso, fy_start_month=2, weights=None):
    weights = weights or RENEWAL_WEIGHTS
    buckets = {"will_renew": [], "undetermined": [], "will_not_renew": []}
    for r in rows:
        buckets[_bucket(r["status"])].append(r)

    def _summ(brows):
        return {"count": len(brows), "arr": currency.sum_by_currency(brows)}

    und = []
    for r in buckets["undetermined"]:
        rw = risk_weight.risk_weighted(currency.to_number(r["arr"]), r.get("health"), weights)
        und.append({**r, "risk_weighted": rw,
                    "weight": weights.get(str(r.get("health") or "").strip().lower())})

    caveats = [
        f"{r['account']} is flagged Will Not Renew despite a Green health score — worth verifying."
        for r in buckets["will_not_renew"]
        if str(r.get("health") or "").strip().lower() == "green"
    ]

    return {
        "period": periods.fiscal_quarter(today_iso, fy_start_month),
        "summary": {
            "will_renew": _summ(buckets["will_renew"]),
            "undetermined": {**_summ(buckets["undetermined"]),
                             "risk_weighted": currency.sum_by_currency(und, amount_key="risk_weighted")},
            "will_not_renew": _summ(buckets["will_not_renew"]),
        },
        "will_not_renew_rows": _sort(buckets["will_not_renew"]),
        "undetermined_rows": _sort(und),
        "caveats": caveats,
    }


def compute(sf_records, health_records, *, today_iso, fy_start_month=2, weights=None,
            field_map=DEFAULT_FIELD_MAP):
    """SF renewal JSON + Domo health JSON -> the renewals-at-risk result. Joins health on account."""
    sf_rows = normalize_sf_records(sf_io.parse_records(sf_records), field_map)
    hmap = health_by_account(domo_io.parse_query_result(health_records))
    rows = join_health(sf_rows, hmap)
    return compute_from_normalized(rows, today_iso=today_iso,
                                   fy_start_month=fy_start_month, weights=weights)
```

- [ ] **Step 4: Run the recipe tests — verify pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_renewals_at_risk.py -v`
Expected: PASS (all 6 tests). If `test_normalize_*` fails, reconcile `DEFAULT_FIELD_MAP` with Plan 1 Task 5's confirmed field names.

- [ ] **Step 5: Run full suite + commit**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`
Expected: PASS.

```bash
cd "observepoint-revenue"
git add skills/revenue-insights/scripts/renewals_at_risk.py tests/test_renewals_at_risk.py
git -c user.email="16406437+jpwilbur@users.noreply.github.com" commit -m "feat(revenue-insights): renewals-at-risk compute (buckets, currency split, risk-weight, caveats)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Render entrypoint + metrics canon + recipe catalog + SKILL.md (end-to-end)

Wires compute → viz_kit into a renderable HTML report, documents the methodology, and makes `revenue-insights` an invokable skill with the full request flow.

**Files:**
- Modify: `observepoint-revenue/skills/revenue-insights/scripts/renewals_at_risk.py` (add `render` + `main`)
- Create: `observepoint-revenue/skills/revenue-insights/references/metrics-canon.md`
- Create: `observepoint-revenue/skills/revenue-insights/references/recipe-catalog.md`
- Create: `observepoint-revenue/skills/revenue-insights/SKILL.md`
- Modify: `observepoint-revenue/tests/test_renewals_at_risk.py` (add the end-to-end render test)

**Interfaces:**
- Consumes: `compute` (Task 3), `viz_kit` (Task 2), `currency` (Task 1); Plan 1's `tests/fixtures/sf/renewals_sample.json` + `tests/fixtures/domo/account_health_sample.json`.
- Produces: `renewals_at_risk.render(result) -> str` (HTML), `renewals_at_risk.main(argv) -> None` (CLI). The `revenue-insights` skill, discoverable.

- [ ] **Step 1: Write the failing end-to-end test**

Append to `observepoint-revenue/tests/test_renewals_at_risk.py`:

```python
import json
import pathlib

FIX = pathlib.Path(__file__).parent / "fixtures"


def test_end_to_end_render_from_sf_and_domo_fixtures():
    sf = json.loads((FIX / "sf" / "renewals_sample.json").read_text())
    health = json.loads((FIX / "domo" / "account_health_sample.json").read_text())
    result = rar.compute(sf, health, today_iso="2026-06-26")
    out = rar.render(result)
    assert "Renewals at Risk" in out
    assert "Will Not Renew" in out and "Undetermined" in out
    assert "var(--op-bg)" in out                      # branded page
    assert "despite a Green health score" in out      # caveat fired from the joined-health edge row
    # Domo health joined onto an SF row drives risk-weighting (Umbrella Undetermined+Red = 0.25)
    assert result["summary"]["undetermined"]["risk_weighted"].get("USD") == 65500.0 * 0.25
```

> Depends on Plan 1's two fixtures: `sf/renewals_sample.json` (Initech = Will Not Renew) joined with `domo/account_health_sample.json` (Initech = Green) → the Green-but-WNR caveat; Umbrella = Undetermined+Red → the risk-weight assertion.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_renewals_at_risk.py::test_end_to_end_render_from_sf_fixture -v`
Expected: FAIL — `AttributeError: module 'renewals_at_risk' has no attribute 'render'`.

- [ ] **Step 3: Add `render` + `main` to `renewals_at_risk.py`**

Add these imports and functions to `observepoint-revenue/skills/revenue-insights/scripts/renewals_at_risk.py` (add `argparse`, `json` to the imports; `viz_kit` to the same-dir imports):

```python
import argparse  # add to the top import block
import json       # add to the top import block
import viz_kit    # add to the same-dir import block (noqa: E402)


def _arr_str(arrmap):
    return " + ".join(currency.format_money(v, c) for c, v in sorted(arrmap.items())) or "—"


def render(result):
    s, p = result["summary"], result["period"]
    cards = '<div class="cards">' + "".join([
        viz_kit.stat_card("Will Renew", s["will_renew"]["count"],
                          f'opps · {_arr_str(s["will_renew"]["arr"])} ARR'),
        viz_kit.stat_card("Undetermined", s["undetermined"]["count"],
                          f'opps · {_arr_str(s["undetermined"]["arr"])} ARR'),
        viz_kit.stat_card("Will Not Renew", s["will_not_renew"]["count"],
                          f'opps · {_arr_str(s["will_not_renew"]["arr"])} at risk'),
    ]) + "</div>"

    money = lambda r: currency.format_money(currency.to_number(r["arr"]), r["currency"])
    wnr = viz_kit.section_header(
        f'Will Not Renew · {_arr_str(s["will_not_renew"]["arr"])} confirmed lost'
    ) + viz_kit.ranked_table(
        [("ACCOUNT", "account"),
         ("HEALTH", lambda r: viz_kit.health_badge(r["health"])),
         ("RENEWABLE ARR", money),
         ("CLOSE DATE", "close_date")],
        result["will_not_renew_rows"])

    und = viz_kit.section_header("Undetermined · risk-weighted") + viz_kit.ranked_table(
        [("ACCOUNT", "account"),
         ("HEALTH", lambda r: viz_kit.health_badge(r["health"])),
         ("RENEWABLE ARR", money),
         ("RISK-WEIGHTED", lambda r: currency.format_money(r["risk_weighted"], r["currency"])),
         ("CLOSE DATE", "close_date")],
        result["undetermined_rows"])

    body = cards + wnr + und + viz_kit.caveats(result["caveats"])
    return viz_kit.page(
        "Renewals at Risk", body,
        kicker=f'{p["quarter"]} {p["fy_label"]} · {p["start"]} – {p["end"]}',
        subtitle="Source: Salesforce renewal forecast · undetermined risk-weighted by health score")


def main(argv=None):
    ap = argparse.ArgumentParser(description="renewals-at-risk recipe -> branded HTML")
    ap.add_argument("renewals_json", help="SF renewal SOQL result JSON")
    ap.add_argument("--health", required=True, help="Domo account-health result JSON")
    ap.add_argument("--today", required=True, help="ISO date anchoring the fiscal quarter")
    ap.add_argument("--fy-start-month", type=int, default=2)
    ap.add_argument("--out", default="renewals-at-risk.html", help="HTML output path")
    a = ap.parse_args(argv)
    sf_data = json.loads(pathlib.Path(a.renewals_json).read_text())
    health_data = json.loads(pathlib.Path(a.health).read_text())
    try:
        result = compute(sf_data, health_data, today_iso=a.today, fy_start_month=a.fy_start_month)
    except (sf_io.SalesforceResultError, domo_io.DomoResultError) as e:
        sys.exit(f"renewal/health result unusable: {e}")
    pathlib.Path(a.out).write_text(render(result))
    print(a.out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the end-to-end test — verify pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_renewals_at_risk.py -v`
Expected: PASS (all tests incl. the e2e render).

- [ ] **Step 5: Write `references/metrics-canon.md`**

Create `observepoint-revenue/skills/revenue-insights/references/metrics-canon.md` — the encoded methodology (seed it with what renewals-at-risk needs; it grows per recipe):

```markdown
# Revenue metrics canon (revenue-insights)

The encoded methodology so every report computes a metric the same way. The MODEL gathers
(SF/Domo/OP MCP) and judges; deterministic scripts compute. Read-only.

## Cross-cutting rules
- **Currency:** never fabricate FX. Sum each currency separately (`currency.sum_by_currency`);
  show native (`currency.format_money`). Cross-currency totals only when Domo supplies an FX
  rate (not assumed in Phase 1).
- **Fiscal periods:** `periods.fiscal_quarter`, FY starts month 2 (Feb) — FY labeled by its
  start calendar year (Feb 2026 → FY26). Confirmed in Plan 1.
- **Source of truth per metric:** SF = live deal-level; Domo = curated/aggregate; OP = usage.
  When SF and Domo disagree, show both labeled — never silently pick.

## Renewals (renewals-at-risk)
- **Renewable ARR** = `Renewable_ARR__c` on the SF renewal Opportunity (Plan 1 schema).
- **Forecast buckets** from `Renewal_Forecast__c`: Will Renew / Undetermined / Will Not Renew.
- **Will Not Renew** = confirmed churn (at-risk ARR booked as lost).
- **Account health** is NOT in SF — it is a **Domo** field `account_health_score` (string → color
  token: green/yellow/red/blue/black), joined onto SF renewals by account name. See
  `lib/domo/domo-datasets.md` → "Account health" and `lib/salesforce/salesforce-org.md` → "Renewals".
- **Undetermined risk-weighting** = Renewable ARR × health weight: **Red 0.25, Yellow 0.50**
  (the gross-renewal methodology; matches the proven report). Other states are not in the
  undetermined bucket, so they carry no undetermined weight.
- **Auto-caveat:** any Will-Not-Renew row whose joined health is Green is flagged "verify"
  (status/health contradiction).
```

- [ ] **Step 6: Write `references/recipe-catalog.md`**

Create `observepoint-revenue/skills/revenue-insights/references/recipe-catalog.md`:

```markdown
# Recipe catalog (revenue-insights)

Vetted, tested recipes. Each: altitude · sources · compute script · queries · viz.
A request with no matching recipe uses the **ad-hoc fallback** (see SKILL.md).

| Recipe | Altitude | Sources | Compute script | Status |
|---|---|---|---|---|
| renewals-at-risk | RevOps / CSM | SF renewal forecast + Domo health | `scripts/renewals_at_risk.py` | shipped |
| pipeline-coverage | VP Sales | SF + Domo | `scripts/pipeline_coverage.py` | Plan 3 |
| arr-nrr-bridge | Board / CRO | Domo | `scripts/arr_nrr_bridge.py` | Plan 3 |
| consumption-pacing | CSM | OP usage + SF | `scripts/consumption_pacing.py` | Plan 3 |

## renewals-at-risk
- **Queries:** the renewal SOQL in `lib/salesforce/salesforce-org.md` ("Renewals") + the account-
  health query in `lib/domo/domo-datasets.md` ("Account health"). Save each result to JSON.
- **Run:** `renewals_at_risk.py <renewals.json> --health <health.json> --today <ISO> [--out <path>]`
  → branded HTML.
- **Viz:** 3 KPI cards (Will Renew / Undetermined / Will Not Renew) + Will-Not-Renew table
  + Undetermined risk-weighted table + caveats footnote.
```

- [ ] **Step 7: Write `SKILL.md`**

Create `observepoint-revenue/skills/revenue-insights/SKILL.md`:

```markdown
---
name: revenue-insights
description: Use when a revenue-team member wants an analysis, report, dashboard, or metric from Salesforce / Domo / ObservePoint usage data — "renewals at risk", "pipeline coverage", "how are we pacing", "ARR/NRR", "build me a revenue report", "show me the numbers for QBR/board/forecast". Produces a branded in-chat visual (exports on request). For account research use research-account; for scoping/pricing use scope-calculator.
---

# revenue-insights

World-class revenue insight at every altitude (board → AE → CSM) from a question in chat.
**The model gathers (SF/Domo/OP MCP) and judges; deterministic scripts compute every number
and render the branded visual. No LLM math, no LLM-held state. Read-only.**

## Request flow (every report)
1. **Classify** the ask → altitude + recipe (see `references/recipe-catalog.md`) or ad-hoc
   + sources + parameters (period, segment, territory). For territory/segment, resolve via
   `lib/salesforce` (the same `resolve_territory` flow find-accounts uses).
2. **Gather** — run the recipe's queries via MCP (SF `soqlQuery`, Domo `DomoSqlQueryTool`,
   OP usage tools). Pass `--today <today's date>` to compute scripts (they don't read the clock).
3. **Compute** — pipe the returned JSON to the recipe's script; it computes every number.
4. **Render** — the script emits a branded HTML visual to
   `~/Documents/ObservePoint Revenue/revenue-insights/` (`mkdir -p`); show it in chat and
   narrate the "so what" + the script-computed caveats.
5. **Export on request** — PDF/deck/`.xlsx` via `branding-guide`.

## Recipe: renewals-at-risk
1. Read `${CLAUDE_PLUGIN_ROOT}/lib/salesforce/salesforce-org.md` ("Renewals") → run the renewal
   SOQL via `soqlQuery`; save to `<renewals.json>`. **Health is not in SF.**
2. Read `${CLAUDE_PLUGIN_ROOT}/lib/domo/domo-datasets.md` ("Account health") → run the health query
   via `DomoSqlQueryTool` (name the columns so it routes correctly); save to `<health.json>`.
3. `python3 ${CLAUDE_PLUGIN_ROOT}/skills/revenue-insights/scripts/renewals_at_risk.py <renewals.json>
   --health <health.json> --today <YYYY-MM-DD>
   --out "~/Documents/ObservePoint Revenue/revenue-insights/renewals-at-risk-<date>.html"`
   (the script joins SF renewals + Domo health on account name and computes every number).
4. Show the HTML; narrate the caveats it computed. Methodology: `references/metrics-canon.md`.

## Ad-hoc fallback (no matching recipe)
Use `references/metrics-canon.md` for definitions, write the SF/Domo SQL yourself, pipe the rows
to `scripts/adhoc_aggregate.py` for the arithmetic (never compute in your head), render via
`viz_kit`. **Label the output "ad-hoc — computed live, methodology per canon, not yet a vetted
recipe."** If it's useful and repeatable, propose promoting it to a recipe.

## Conventions
- Never fabricate a number/account/source. Missing input → labeled default + "assumptions to
  verify", or an honest "none found".
- Brand values come from `branding-guide` only. Pricing (if ever needed) = the live calculator.
- Allowed MCP tools: SF read (`soqlQuery`, `find`, `getUserInfo`, `getObjectSchema`),
  Domo read (`DomoSqlQueryTool`, `SearchTool`, `FileSetQueryTool`), OP usage read. No writes.
```

- [ ] **Step 8: Run full suite + commit**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`
Expected: PASS.

```bash
cd "observepoint-revenue"
git add skills/revenue-insights/scripts/renewals_at_risk.py \
        skills/revenue-insights/references/metrics-canon.md \
        skills/revenue-insights/references/recipe-catalog.md \
        skills/revenue-insights/SKILL.md tests/test_renewals_at_risk.py
git -c user.email="16406437+jpwilbur@users.noreply.github.com" commit -m "feat(revenue-insights): renewals render + canon + catalog + SKILL.md (end-to-end anchor)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 9: Smoke-test the live anchor (manual, optional but recommended)**

With the SF MCP connected, run the renewal SOQL for a real book, save the JSON, run the recipe with `--today 2026-06-26`, open the HTML. Confirm it visually matches the proven report's shape (KPI cards + two tables + caveats) and that totals reconcile to a spot SF check.

---

### Task 5: Ad-hoc generic aggregate helper

The deterministic arithmetic behind the ad-hoc fallback, so novel questions never require LLM math.

**Files:**
- Create: `observepoint-revenue/skills/revenue-insights/scripts/adhoc_aggregate.py`
- Create: `observepoint-revenue/tests/test_adhoc_aggregate.py`

**Interfaces:**
- Consumes: `currency.to_number` (Task 1).
- Produces: `adhoc_aggregate.aggregate(rows, group_keys=(), sums=(), counts=False, avgs=()) -> list[dict]` — group rows by `group_keys`, emitting per-group `sum_<k>`, `count`, `avg_<k>`.

- [ ] **Step 1: Write the failing tests**

Create `observepoint-revenue/tests/test_adhoc_aggregate.py`:

```python
import adhoc_aggregate as agg


ROWS = [
    {"stage": "Commit", "arr": 100}, {"stage": "Commit", "arr": 200},
    {"stage": "Best Case", "arr": 50}, {"stage": "Best Case", "arr": "150"},
]


def test_group_sum_and_count():
    out = {r["stage"]: r for r in agg.aggregate(ROWS, group_keys=("stage",),
                                                sums=("arr",), counts=True)}
    assert out["Commit"]["sum_arr"] == 300.0 and out["Commit"]["count"] == 2
    assert out["Best Case"]["sum_arr"] == 200.0


def test_avg():
    out = {r["stage"]: r for r in agg.aggregate(ROWS, group_keys=("stage",), avgs=("arr",))}
    assert out["Commit"]["avg_arr"] == 150.0


def test_no_group_aggregates_whole_set():
    out = agg.aggregate(ROWS, sums=("arr",), counts=True)
    assert len(out) == 1 and out[0]["sum_arr"] == 500.0 and out[0]["count"] == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_adhoc_aggregate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adhoc_aggregate'`.

- [ ] **Step 3: Implement `adhoc_aggregate.py`**

Create `observepoint-revenue/skills/revenue-insights/scripts/adhoc_aggregate.py`:

```python
"""Generic group-by aggregation for the ad-hoc fallback — the arithmetic for questions no
vetted recipe covers. The MODEL writes the SQL and passes rows here; this computes. No I/O."""
import currency


def aggregate(rows, group_keys=(), sums=(), counts=False, avgs=()):
    """Group `rows` (list of dicts) by `group_keys`; emit per group: the group key values,
    `sum_<k>` for k in sums, `avg_<k>` for k in avgs, and `count` if counts. With no
    group_keys, aggregates the whole set into one row. Numbers parsed via currency.to_number."""
    groups = {}
    order = []
    for r in rows:
        key = tuple(r.get(k) for k in group_keys)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)

    out = []
    for key in order:
        g = groups[key]
        rec = {k: v for k, v in zip(group_keys, key)}
        if counts:
            rec["count"] = len(g)
        for k in sums:
            rec[f"sum_{k}"] = sum((currency.to_number(r.get(k)) or 0.0) for r in g)
        for k in avgs:
            vals = [currency.to_number(r.get(k)) for r in g if currency.to_number(r.get(k)) is not None]
            rec[f"avg_{k}"] = (sum(vals) / len(vals)) if vals else None
        out.append(rec)
    return out
```

- [ ] **Step 4: Run the tests — verify pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_adhoc_aggregate.py -v`
Expected: PASS (all 3 tests).

- [ ] **Step 5: Run full suite + commit**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`
Expected: PASS.

```bash
cd "observepoint-revenue"
git add skills/revenue-insights/scripts/adhoc_aggregate.py tests/test_adhoc_aggregate.py
git -c user.email="16406437+jpwilbur@users.noreply.github.com" commit -m "feat(revenue-insights): generic aggregate helper for the ad-hoc fallback

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage (Plan 2 scope):**
- *`revenue-insights` skill (canon, recipe catalog, compute scripts, viz kit, ad-hoc fallback)* → Tasks 1–5. ✓
- *Branded in-chat visual first, dark NERD theme, brand from branding-guide* → Task 2 (`viz_kit` pulls every color from `brand_kit`; `page()` is dark). ✓
- *renewals-at-risk rebuilds the screenshot* → Task 3 (compute, **joining SF renewals + Domo health on account name** — health is not in SF) + Task 4 (render: 3 KPI cards + Will-Not-Renew + Undetermined risk-weighted tables + caveats). Health = 5 states (green/yellow/red/blue/black) via `health_token`. ✓
- *Multi-currency native, no fabricated FX* → `currency.sum_by_currency` keeps currencies separate; canon states the rule. ✓
- *Risk-weighting (screenshot: Red 25% / Yellow 50%)* → `risk_weight` + `RENEWAL_WEIGHTS`, tested against the screenshot numbers (65500→16375, 65200→32600). ✓
- *Reconciliation / source-of-truth per metric* → canon cross-cutting rules. ✓
- *Ad-hoc fallback labeled + promote path* → Task 5 helper + SKILL.md ad-hoc section. ✓
- *Tests against fixture JSON, no live source* → all tests use inline data or Plan 1's synthetic fixtures. ✓
- *Read-only* → no create/update MCP calls; scripts never call SF/Domo. ✓

**Placeholder scan:** every code/test step shows complete code; no "TBD"/"add validation"/"similar to". The one parameterized unknown (the health-field API name) is explicitly flagged to reconcile with Plan 1 Task 5, with a concrete evidenced default — not a blank. ✓

**Type consistency:** `currency.to_number`/`sum_by_currency`/`format_money`, `periods.fiscal_quarter` (returns `fy_label`/`quarter`/`start`/`end`), `risk_weight.risk_weighted`, `viz_kit.*` signatures, and `renewals_at_risk` result keys (`summary.{will_renew,undetermined.{count,arr,risk_weighted},will_not_renew}`, `will_not_renew_rows`, `undetermined_rows`, `caveats`) are used identically across compute, render, and tests. `aggregate` emits `sum_<k>`/`avg_<k>`/`count` consistently. ✓

## Execution Handoff

This is Plan 2 of 3. Plan 3 (pipeline-coverage, arr-nrr-bridge, consumption-pacing) is authored after Plan 1's probes fill `lib/domo/domo-datasets.md`, so its Domo/OP queries and column names are real.
