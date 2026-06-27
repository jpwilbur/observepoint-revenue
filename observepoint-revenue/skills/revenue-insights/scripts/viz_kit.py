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
    """Render rows as an HTML table.

    columns: list of (header, key). `key` is either:
      - a string dict-key → the row's value is HTML-escaped (use for untrusted field values), or
      - a callable(row) -> str → its return is inserted as TRUSTED HTML, NOT escaped (use for
        composed viz_kit output like health_badge(); if a callable embeds untrusted field data,
        the caller must escape it itself).
    """
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
