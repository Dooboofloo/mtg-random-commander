"""Tests for our application-level CardDB lifecycle and progress display."""

from time import sleep

from mtg_carddb import WorkflowProgress
from mtg_random_commander import database


def test_missing_database_is_initialized(tmp_path, monkeypatch, capsys):
    target = tmp_path / "nested" / "carddb.sqlite"
    called = []

    def fake_init(path, *, on_progress):
        called.append(path)
        on_progress(WorkflowProgress("bulk", "start"))
        on_progress(WorkflowProgress("bulk", "complete"))
        on_progress(WorkflowProgress("build", "start"))
        on_progress(WorkflowProgress("build", "complete", "123 Oracle cards"))
        path.write_bytes(b"fake")

    monkeypatch.setattr(database, "initialize_database", fake_init)
    monkeypatch.setattr(
        database, "update_database",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("update not expected")),
    )

    result = database.ensure_database(path=target)
    assert result == target
    assert target.exists()
    assert called == [target]
    output = capsys.readouterr().err
    assert "First-time setup" in output
    assert "Downloading card data from Scryfall" in output
    assert "Finished: Building and checking" in output
    assert "123 Oracle cards" in output


def test_existing_database_is_not_updated_automatically(tmp_path, monkeypatch, capsys):
    target = tmp_path / "carddb.sqlite"
    target.write_bytes(b"existing")

    def fail(*args, **kwargs):
        raise AssertionError("No initialization or update should run")

    monkeypatch.setattr(database, "initialize_database", fail)
    monkeypatch.setattr(database, "update_database", fail)

    assert database.ensure_database(path=target) == target
    assert target.read_bytes() == b"existing"
    assert capsys.readouterr().err == ""


def test_explicit_update(tmp_path, monkeypatch, capsys):
    target = tmp_path / "carddb.sqlite"
    target.write_bytes(b"existing")
    updated = []

    def fake_update(path, *, on_progress):
        updated.append(path)
        on_progress(WorkflowProgress("references", "start"))
        on_progress(WorkflowProgress("references", "complete"))

    monkeypatch.setattr(database, "update_database", fake_update)
    monkeypatch.setattr(
        database, "initialize_database",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("init not expected")),
    )

    assert database.ensure_database(path=target, update=True) == target
    assert updated == [target]
    output = capsys.readouterr().err
    assert "Refreshing card data" in output
    assert "Downloading supplementary card catalogs" in output


def test_update_request_with_missing_database_initializes(tmp_path, monkeypatch):
    target = tmp_path / "carddb.sqlite"
    initialized = []
    monkeypatch.setattr(
        database,
        "initialize_database",
        lambda path, *, on_progress: initialized.append(path),
    )
    monkeypatch.setattr(
        database,
        "update_database",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("update not expected")),
    )

    assert database.ensure_database(path=target, update=True) == target
    assert initialized == [target]


def test_default_path_from_carddb_is_used(tmp_path, monkeypatch):
    target = tmp_path / "default" / "carddb.sqlite"
    monkeypatch.setattr(database, "default_database_path", lambda: target)
    monkeypatch.setattr(
        database,
        "initialize_database",
        lambda path, *, on_progress: path.write_bytes(b"created"),
    )

    assert database.ensure_database() == target
    assert target.read_bytes() == b"created"


def test_progress_heartbeat_is_emitted_while_waiting(capsys):
    with database.DatabaseProgress(interval_seconds=0.01) as progress:
        progress(WorkflowProgress("build", "start"))
        sleep(0.06)
        progress(WorkflowProgress("build", "complete", "42 Oracle cards"))

    output = capsys.readouterr().err
    assert "Still working: Building and checking the local card database" in output
    assert "42 Oracle cards" in output


def test_progress_thread_stops_on_error():
    from pytest import raises

    progress = database.DatabaseProgress(interval_seconds=0.01)
    with raises(RuntimeError, match="failed"):
        with progress:
            raise RuntimeError("failed")
    assert progress._thread is not None
    assert not progress._thread.is_alive()
