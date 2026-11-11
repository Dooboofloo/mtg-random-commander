import pytest

from mtg_random_commander import cli


class FakeDatabase:
    def __init__(self):
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __len__(self):
        return 500

    def by_legality(self, format_name, status):
        self.queries.append((format_name, status))
        return frozenset({"id-1", "id-2"})


def test_cli_opens_database_and_reports_counts(tmp_path, monkeypatch, capsys):
    path = tmp_path / "carddb.sqlite"
    fake_db = FakeDatabase()
    opened = []

    class FakeCardDatabase:
        @staticmethod
        def open(target):
            opened.append(target)
            return fake_db

    monkeypatch.setattr(cli, "CardDatabase", FakeCardDatabase)
    monkeypatch.setattr(cli, "ensure_database", lambda *, path, update: path)

    assert cli.main(["--database", str(path)]) == 0
    out = capsys.readouterr().out
    assert "Oracle cards: 500" in out
    assert "Commander-legal cards: 2" in out
    assert opened == [path]
    assert fake_db.queries == [("commander", "legal")]


def test_cli_passes_explicit_update_flag(tmp_path, monkeypatch):
    path = tmp_path / "carddb.sqlite"
    passed = []

    def fake_ensure(*, path, update):
        passed.append(update)
        return path

    class FakeCardDatabase:
        @staticmethod
        def open(target):
            return FakeDatabase()

    monkeypatch.setattr(cli, "ensure_database", fake_ensure)
    monkeypatch.setattr(cli, "CardDatabase", FakeCardDatabase)
    assert cli.main(["--database", str(path), "--update-db"]) == 0
    assert passed == [True]


def test_help_does_not_initialize_database(monkeypatch):
    monkeypatch.setattr(
        cli, "ensure_database", lambda **k: (_ for _ in ()).throw(
            AssertionError("Help must not touch database")
        )
    )
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
