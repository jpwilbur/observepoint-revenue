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
