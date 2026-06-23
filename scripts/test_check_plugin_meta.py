import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("check_plugin_meta", HERE / "check_plugin_meta.py")
cpm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cpm)


def _plugin(tmp_path, description="A short description.", skills=None):
    """Build a minimal plugin dir. skills: {skill_name: description_text}."""
    root = tmp_path / "plugin"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "p", "version": "1.0.0", "description": description})
    )
    for name, desc in (skills or {}).items():
        d = root / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("---\nname: %s\ndescription: %s\n---\n\n# %s\n" % (name, desc, name))
    return root


def test_clean_plugin_passes(tmp_path):
    root = _plugin(tmp_path, "Fine.", {"foo": "Use when foo. No tags here."})
    assert cpm.check(root) == []


def test_description_over_500_fails(tmp_path):
    root = _plugin(tmp_path, "x" * 501)
    errors = cpm.check(root)
    assert len(errors) == 1
    assert "plugin.json description" in errors[0] and "501" in errors[0]


def test_description_exactly_500_passes(tmp_path):
    root = _plugin(tmp_path, "x" * 500)
    assert cpm.check(root) == []


def test_skill_description_with_xml_tag_fails(tmp_path):
    root = _plugin(tmp_path, "Fine.", {"owned": 'what domains does <org> own'})
    errors = cpm.check(root)
    assert len(errors) == 1
    assert "owned/SKILL.md" in errors[0].replace("\\", "/")
    assert "<org>" in errors[0]


def test_multiple_violations_all_reported(tmp_path):
    root = _plugin(tmp_path, "x" * 600, {"a": "has <tag>", "b": "clean one"})
    errors = cpm.check(root)
    assert len(errors) == 2


def test_missing_manifest_reported(tmp_path):
    (tmp_path / "empty").mkdir()
    errors = cpm.check(tmp_path / "empty")
    assert len(errors) == 1
    assert "plugin.json" in errors[0]


def test_main_returns_1_on_violation(tmp_path, capsys):
    root = _plugin(tmp_path, "x" * 501)
    assert cpm.main([str(root)]) == 1
    assert "FAILED" in capsys.readouterr().err


def test_main_returns_0_when_clean(tmp_path):
    root = _plugin(tmp_path, "Fine.", {"foo": "clean"})
    assert cpm.main([str(root)]) == 0


def test_main_no_args_returns_2(capsys):
    assert cpm.main([]) == 2
    assert "usage" in capsys.readouterr().err
