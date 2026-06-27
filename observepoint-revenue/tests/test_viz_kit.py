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
