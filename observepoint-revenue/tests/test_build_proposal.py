import json
import pathlib
import subprocess
import sys

import pytest
from docx import Document

import build_proposal as bp

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "scope-calculator" / "scripts" / "build_proposal.py"

DATA = {
    "customer": "Acme Corp",
    "use_case": "privacy",
    "domains": ["acme.com", "shop.acme.com"],
    "regulations": ["CCPA"],
    "monitoring_summary": "Full-site privacy sweep annually, with a critical slice re-checked monthly.",
    "page_universe": {"low": 180_000, "anchor": 197_000, "high": 210_000, "confidence": "MEDIUM"},
    "scope": {"predicted_scans": 1_664_256, "purchased_scans": 1_830_682, "buffer_pct": 0.10,
              "tier": "professional", "price_total": 139_687.28,
              "pricing_source": "live @ https://app.observepoint.com/www-pricing/main.js"},
}


def _text(doc):
    return "\n".join(p.text for p in doc.paragraphs)


def test_proposal_contains_key_fields():
    t = _text(bp.build_proposal(DATA))
    assert "Acme Corp" in t
    assert "acme.com" in t and "shop.acme.com" in t
    assert "CCPA" in t
    assert "1,830,682" in t          # purchased
    assert "1,664,256" in t          # predicted
    assert "10% buffer" in t
    assert "$139,687" in t
    assert "professional" in t


def test_proposal_no_buffer_phrasing_when_zero():
    d = json.loads(json.dumps(DATA))
    d["scope"]["buffer_pct"] = 0.0
    d["scope"]["purchased_scans"] = d["scope"]["predicted_scans"]
    t = _text(bp.build_proposal(d))
    assert "buffer" not in t.lower()
    assert "1,664,256" in t


def test_proposal_omits_internal_pricing_source():
    # The bundle URL / source stamp is internal-only; it must not appear in the customer doc.
    t = _text(bp.build_proposal(DATA))
    assert "app.observepoint.com" not in t
    assert "live @" not in t


def test_clean_guard_rejects_internal_terms():
    d = json.loads(json.dumps(DATA))
    d["monitoring_summary"] = "We discounted query-param spiral URLs."
    doc = bp.build_proposal(d)
    with pytest.raises(ValueError):
        bp._assert_clean(doc)


def test_cli_writes_docx(tmp_path):
    f = tmp_path / "in.json"; f.write_text(json.dumps(DATA))
    out = tmp_path / "p.docx"
    res = subprocess.run([sys.executable, str(SCRIPT), str(f), str(out)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == str(out)
    assert "Acme Corp" in _text(Document(out))
