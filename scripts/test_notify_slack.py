import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("notify_slack", HERE / "notify_slack.py")
ns = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ns)


def test_build_message_has_name_version_and_link():
    msg = ns.build_message("ObservePoint Consultant", "0.8.2", "https://drive.google.com/drive/folders/ABC")
    assert "*ObservePoint Consultant*" in msg
    assert "`v0.8.2`" in msg
    assert "<https://drive.google.com/drive/folders/ABC|ObservePoint Consultant>" in msg
    assert "available to install" in msg


def test_resolve_webhook_env_precedence(tmp_path):
    # env wins even if the file also exists
    f = tmp_path / ".config" / "op-release" / "slack-webhook"
    f.parent.mkdir(parents=True)
    f.write_text("https://hooks.slack.com/FROM_FILE\n")
    got = ns.resolve_webhook(env={"OP_RELEASE_SLACK_WEBHOOK": "  https://hooks.slack.com/FROM_ENV  "},
                             home=str(tmp_path))
    assert got == "https://hooks.slack.com/FROM_ENV"


def test_resolve_webhook_file_fallback(tmp_path):
    f = tmp_path / ".config" / "op-release" / "slack-webhook"
    f.parent.mkdir(parents=True)
    f.write_text("https://hooks.slack.com/FROM_FILE\n")
    assert ns.resolve_webhook(env={}, home=str(tmp_path)) == "https://hooks.slack.com/FROM_FILE"


def test_resolve_webhook_none_when_unset(tmp_path):
    assert ns.resolve_webhook(env={}, home=str(tmp_path)) is None


def test_post_success_sends_json_body():
    captured = {}

    class _Resp:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def fake_opener(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = req.data
        captured["ctype"] = req.headers.get("Content-type")
        return _Resp()

    ok = ns.post("https://hooks.slack.com/X", "hello", _opener=fake_opener)
    assert ok is True
    assert captured["url"] == "https://hooks.slack.com/X"
    assert json.loads(captured["body"].decode()) == {"text": "hello"}
    assert captured["ctype"] == "application/json"


def test_post_returns_false_on_error():
    def boom(req, timeout=None):
        raise OSError("network down")

    assert ns.post("https://hooks.slack.com/X", "hi", _opener=boom) is False


def test_post_returns_false_on_non_2xx():
    class _Resp:
        status = 500
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    assert ns.post("https://hooks.slack.com/X", "hi", _opener=lambda req, timeout=None: _Resp()) is False
