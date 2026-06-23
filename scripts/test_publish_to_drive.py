import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("publish_to_drive", HERE / "publish_to_drive.py")
ptd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ptd)


def _make_artifact(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(b"PK\x03\x04 fake zip")
    return p


def _drive(tmp_path):
    d = tmp_path / "drive"
    d.mkdir()
    return d


def test_publish_places_new_and_archives_old(tmp_path):
    drive = _drive(tmp_path)
    (drive / "observepoint-revenue-0.15.0.plugin").write_bytes(b"old")
    art = _make_artifact(tmp_path, "observepoint-revenue-0.16.0.plugin")
    result = ptd.publish(art, drive)
    assert result["published"] is True
    assert result["archived"] == ["observepoint-revenue-0.15.0.plugin"]
    assert [p.name for p in drive.glob("*.plugin")] == ["observepoint-revenue-0.16.0.plugin"]
    assert (drive / "Old Versions" / "observepoint-revenue-0.15.0.plugin").is_file()


def test_publish_creates_old_versions_when_missing(tmp_path):
    drive = _drive(tmp_path)
    (drive / "observepoint-revenue-0.15.0.plugin").write_bytes(b"old")
    art = _make_artifact(tmp_path, "observepoint-revenue-0.16.0.plugin")
    assert not (drive / "Old Versions").exists()
    ptd.publish(art, drive)
    assert (drive / "Old Versions").is_dir()


def test_publish_first_release_no_archive(tmp_path):
    drive = _drive(tmp_path)
    art = _make_artifact(tmp_path, "observepoint-revenue-0.16.0.plugin")
    result = ptd.publish(art, drive)
    assert result["archived"] == []
    assert (drive / "observepoint-revenue-0.16.0.plugin").is_file()


def test_publish_idempotent_noop(tmp_path):
    drive = _drive(tmp_path)
    art = _make_artifact(tmp_path, "observepoint-revenue-0.16.0.plugin")
    ptd.publish(art, drive)
    result = ptd.publish(art, drive)
    assert result["skipped"] is True
    assert result["published"] is False


def test_publish_force_republishes(tmp_path):
    drive = _drive(tmp_path)
    art = _make_artifact(tmp_path, "observepoint-revenue-0.16.0.plugin")
    ptd.publish(art, drive)
    result = ptd.publish(art, drive, force=True)
    assert result["published"] is True


def test_publish_self_heals_to_one_current(tmp_path):
    drive = _drive(tmp_path)
    (drive / "observepoint-revenue-0.15.0.plugin").write_bytes(b"old")
    (drive / "observepoint-revenue-0.16.0.plugin").write_bytes(b"stale-current")
    art = _make_artifact(tmp_path, "observepoint-revenue-0.16.0.plugin")
    ptd.publish(art, drive)
    assert [p.name for p in drive.glob("*.plugin")] == ["observepoint-revenue-0.16.0.plugin"]
    assert (drive / "Old Versions" / "observepoint-revenue-0.15.0.plugin").is_file()
    assert (drive / "observepoint-revenue-0.16.0.plugin").read_bytes() == b"PK\x03\x04 fake zip"


def test_dry_run_touches_nothing(tmp_path):
    drive = _drive(tmp_path)
    (drive / "observepoint-revenue-0.15.0.plugin").write_bytes(b"old")
    art = _make_artifact(tmp_path, "observepoint-revenue-0.16.0.plugin")
    result = ptd.publish(art, drive, dry_run=True)
    assert result["published"] is True
    assert (drive / "observepoint-revenue-0.15.0.plugin").is_file()
    assert not (drive / "observepoint-revenue-0.16.0.plugin").exists()
    assert not (drive / "Old Versions").exists()


def test_current_published_version(tmp_path):
    drive = _drive(tmp_path)
    assert ptd.current_published_version(drive) is None
    (drive / "observepoint-revenue-0.16.1.plugin").write_bytes(b"x")
    assert ptd.current_published_version(drive) == "0.16.1"


def test_resolve_drive_dir_override(tmp_path):
    got = ptd.resolve_drive_dir("ObservePoint Revenue", override=str(tmp_path / "x"))
    assert got == tmp_path / "x"


def test_resolve_drive_dir_single_mount(tmp_path):
    mount = tmp_path / "Library" / "CloudStorage" / "GoogleDrive-me@x.com"
    mount.mkdir(parents=True)
    got = ptd.resolve_drive_dir("ObservePoint Revenue", home=str(tmp_path))
    assert got == (mount / "Shared drives" / "Solutions Consulting" / "Claude"
                   / "Plugins" / "ObservePoint Revenue")


def test_resolve_drive_dir_zero_mounts(tmp_path):
    with pytest.raises(ValueError):
        ptd.resolve_drive_dir("ObservePoint Revenue", home=str(tmp_path))


def test_resolve_drive_dir_multiple_mounts(tmp_path):
    for n in ("GoogleDrive-a@x.com", "GoogleDrive-b@x.com"):
        (tmp_path / "Library" / "CloudStorage" / n).mkdir(parents=True)
    with pytest.raises(ValueError):
        ptd.resolve_drive_dir("ObservePoint Revenue", home=str(tmp_path))


def test_main_print_current(tmp_path, capsys):
    drive = tmp_path / "ObservePoint Revenue"
    drive.mkdir()
    (drive / "observepoint-revenue-0.16.1.plugin").write_bytes(b"x")
    rc = ptd.main(["--folder", "ObservePoint Revenue", "--drive-dir", str(drive), "--print-current"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "0.16.1"


def test_main_print_current_empty_when_none(tmp_path, capsys):
    drive = tmp_path / "ObservePoint Revenue"
    drive.mkdir()
    rc = ptd.main(["--folder", "ObservePoint Revenue", "--drive-dir", str(drive), "--print-current"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == ""


def test_main_publishes(tmp_path):
    drive = tmp_path / "ObservePoint Revenue"
    drive.mkdir()
    art = tmp_path / "observepoint-revenue-0.16.0.plugin"
    art.write_bytes(b"PK\x03\x04 fake zip")
    rc = ptd.main([str(art), "--folder", "ObservePoint Revenue", "--drive-dir", str(drive)])
    assert rc == 0
    assert (drive / "observepoint-revenue-0.16.0.plugin").is_file()


def test_main_missing_artifact_returns_2(tmp_path):
    drive = tmp_path / "ObservePoint Revenue"
    drive.mkdir()
    rc = ptd.main(["--folder", "ObservePoint Revenue", "--drive-dir", str(drive)])
    assert rc == 2
