from types import SimpleNamespace

import pytest

from mtg_random_commander import cli


class FakeDatabase:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def __getitem__(self, cid):
        return SimpleNamespace(name="Test Commander")

@pytest.fixture(autouse=True)
def mock_commander_candidates(monkeypatch):
    monkeypatch.setattr(
        cli.CardPolicy,
        "commander_candidates",
        lambda self, db, *, eligible_cards=None: frozenset({"cmd"}),
    )
    monkeypatch.setattr(
        cli.CardPolicy,
        "eligible_cards",
        lambda self, db: frozenset({"cmd"}),
    )

def test_cli_generates_deck(
    tmp_path, monkeypatch, capsys
):
    path = tmp_path / "carddb.sqlite"
    fake_db = FakeDatabase()
    opened = []

    class FakeCardDatabase:
        @staticmethod
        def open(target):
            opened.append(target)
            return fake_db

    monkeypatch.setattr(
        cli, "CardDatabase", FakeCardDatabase
    )

    monkeypatch.setattr(
        cli, "ensure_database",
        lambda *, path, update: path,
    )

    builds = []

    def fake_build(
        db,
        settings,
        *,
        rng,
        on_progress=None,
        commander_candidates=None,
        eligible_cards=None,
    ):
        builds.append((db, settings, commander_candidates))
        return (
            SimpleNamespace(commanders=("cmd",), entries=()),
            SimpleNamespace(
                land_slots=37,
                nonland_slots=62,
                allocations=(),
                synergy_slots=0,
            ),
        )

    monkeypatch.setattr(cli, "build_deck", fake_build)

    monkeypatch.setattr(
        cli, "save_decklist",
        lambda db, deck, out_dir: tmp_path / "deck.txt",
    )

    assert cli.main([
        "--database", str(path),
        "--lands", "37",
        "--seed", "3",
    ]) == 0

    assert opened == [path]
    assert builds[0][1].land_range == (37, 37)
    assert builds[0][2] == frozenset({"cmd"})

    output = capsys.readouterr().out

    assert "Preparing eligible commander pool..." in output
    assert "Created Test Commander" in output


def test_cli_update_flag_passes_to_database(
    tmp_path, monkeypatch
):
    path = tmp_path / "carddb.sqlite"
    calls = []

    def fake_ensure(*, path, update):
        calls.append(update)
        return path

    class FakeCardDatabase:
        @staticmethod
        def open(path):
            return FakeDatabase()

    monkeypatch.setattr(
        cli, "CardDatabase", FakeCardDatabase
    )

    monkeypatch.setattr(
        cli, "ensure_database", fake_ensure
    )

    monkeypatch.setattr(
        cli, "build_deck",
        lambda db, settings, *, rng, on_progress=None, commander_candidates=None, eligible_cards=None: (
            SimpleNamespace(commanders=("cmd",), entries=()),
            SimpleNamespace(
                land_slots=37,
                nonland_slots=62,
                allocations=(),
                synergy_slots=0,
            ),
        ),
    )

    monkeypatch.setattr(
        cli, "save_decklist",
        lambda db, deck, out_dir: tmp_path / "deck.txt",
    )

    assert cli.main([
        "--database", str(path),
        "--update-db",
    ]) == 0

    assert calls == [True]


def test_m12_update_does_not_open_or_generate(tmp_path, monkeypatch, capsys):
    path = tmp_path / "snapshot.sqlite"
    called = []

    def refreshed(*, path, update):
        called.append((path, update))
        return path

    monkeypatch.setattr(cli, "ensure_database", refreshed)
    monkeypatch.setattr(
        cli.CardDatabase, "open", lambda *_: (_ for _ in ()).throw(
            AssertionError("Update should not open the database")
        ),
    )
    monkeypatch.setattr(
        cli, "build_deck", lambda *_a, **_kw: (_ for _ in ()).throw(
            AssertionError("Update should not generate a deck")
        ),
    )
    assert cli.main(["--update-db", "--database", str(path)]) == 0
    assert called == [(path, True)]
    assert "refreshed" in capsys.readouterr().out


def test_m12_update_failure_exits_nonzero(tmp_path, monkeypatch, capsys):
    def fails(**kwargs):
        raise OSError("update unavailable")

    monkeypatch.setattr(cli, "ensure_database", fails)
    assert cli.main(["--update-db"]) == 1
    assert "Unable to update database: update unavailable" in capsys.readouterr().err


def test_help_skips_database(monkeypatch):
    monkeypatch.setattr(
        cli,
        "ensure_database",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("Help must not touch database")
        ),
    )

    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])

    assert exc.value.code == 0


def test_cli_invalid_count():
    with pytest.raises(SystemExit) as exc:
        cli.main(["--count", "0"])

    assert exc.value.code == 2



def test_named_commander_skips_pool_preparation(
    tmp_path, monkeypatch
):
    def unexpected_scan(self, db):
        raise AssertionError(
            "Named commanders should not trigger "
            "full commander enumeration"
        )

    def unexpected_bulk_query(self, db):
        raise AssertionError(
            "CLI must not preload the full eligible-card pool"
        )

    monkeypatch.setattr(
        cli.CardPolicy,
        "commander_candidates",
        unexpected_scan,
    )

    monkeypatch.setattr(
        cli.CardPolicy,
        "eligible_cards",
        unexpected_bulk_query,
    )

    class FakeCardDatabase:
        @staticmethod
        def open(path):
            return FakeDatabase()

    monkeypatch.setattr(
        cli, "CardDatabase", FakeCardDatabase
    )

    monkeypatch.setattr(
        cli, "ensure_database",
        lambda *, path, update: path,
    )

    monkeypatch.setattr(
        cli, "build_deck",
        lambda db, settings, **kwargs: (
            SimpleNamespace(commanders=("cmd",), entries=()),
            SimpleNamespace(
                land_slots=37,
                nonland_slots=62,
                allocations=(),
                synergy_slots=0,
            ),
        ),
    )

    monkeypatch.setattr(
        cli, "save_decklist",
        lambda db, deck, out_dir: tmp_path / "deck.txt",
    )

    assert cli.main([
        "--commander", "Test Commander",
        "--database", str(tmp_path / "carddb.sqlite"),
    ]) == 0


def test_cli_package_overrides():
    parser = cli.build_parser()

    args = parser.parse_args([
        "--package", "ramp=9-11",
        "--package", "draw=0",
    ])

    packages = cli._configure_packages(
        args.package,
        args.no_packages,
        parser,
    )

    assert {
        p.role: p.count_range
        for p in packages
    } == {
        "ramp": (9, 11),
        "draw": (0, 0),
    }


def test_cli_disables_packages_and_rejects_conflicts():
    parser = cli.build_parser()
    assert cli._configure_packages([], True, parser) == ()
    with pytest.raises(SystemExit) as exc:
        cli._configure_packages(["ramp=10"], True, parser)
    assert exc.value.code == 2


def test_cli_rejects_unknown_package_and_duplicate_override():
    parser = cli.build_parser()

    # Arbitrary tags are syntactically valid; their existence
    # is checked against CardDB separately.
    packages = cli._configure_packages(
        ["foobar=2"],
        False,
        parser,
    )

    assert [
        (p.role, p.tags, p.count_range)
        for p in packages
    ] == [
        ("foobar", ("foobar",), (2, 2)),
    ]

    with pytest.raises(SystemExit):
        cli._configure_packages(
            ["ramp=2", "ramp=3"],
            False,
            parser,
        )

def test_synergy_cli_fraction_validation():
    assert cli._synergy_percent("0") == 0
    assert cli._synergy_percent("0.4") == 0.4
    assert cli._synergy_percent("1") == 1

    for bad in (
        "-0.1",
        "1.1",
        "nan",
        "inf",
        "invalid",
    ):
        with pytest.raises(
            cli.argparse.ArgumentTypeError
        ):
            cli._synergy_percent(bad)

def test_cli_land_settings():
    parser = cli.build_parser()

    args = parser.parse_args([
        "--nonbasic-fraction", "0.6",
        "--snow-chance", "0",
    ])

    assert args.nonbasic_fraction == 0.6
    assert args.snow_chance == 0

    defaults = parser.parse_args([])

    assert defaults.nonbasic_fraction is None
    assert defaults.snow_chance == 0.055

    for option in ("--nonbasic-fraction", "--snow-chance"):
        with pytest.raises(SystemExit):
            parser.parse_args([option, "1.5"])


def test_m10_custom_packages_replace_defaults():
    parser = cli.build_parser()

    args = parser.parse_args([
        "--package", "ramp", "8-12",
        "--package", "removal", "8",
        "--package", "lifegain", "5-7",
    ])

    packages = cli._configure_packages(
        args.package,
        args.no_packages,
        parser,
    )

    assert [
        (p.role, p.tags, p.count_range)
        for p in packages
    ] == [
        ("ramp", ("ramp",), (8, 12)),
        ("removal", ("removal",), (8, 8)),
        ("lifegain", ("lifegain",), (5, 7)),
    ]


def test_m10_builtin_overrides_still_work():
    parser = cli.build_parser()

    args = parser.parse_args([
        "--package", "ramp=10",
        "--package", "draw=6-8",
    ])

    packages = cli._configure_packages(
        args.package,
        args.no_packages,
        parser,
    )

    assert {
        p.role: p.count_range
        for p in packages
    } == {
        "ramp": (10, 10),
        "draw": (6, 8),
    }


def test_m10_accepts_mixed_package_syntax():
    parser = cli.build_parser()

    args = parser.parse_args([
        "--package", "ramp=10",
        "--package", "removal", "8",
        "--package", "interaction=7",
    ])

    packages = cli._configure_packages(
        args.package,
        args.no_packages,
        parser,
    )

    assert [
        (p.role, p.tags, p.count_range)
        for p in packages
    ] == [
        ("ramp", ("ramp",), (10, 10)),
        ("removal", ("removal",), (8, 8)),
        ("interaction", ("removal", "counterspell"), (7, 7)),
    ]


def test_m10_rejects_duplicate_custom_packages():
    parser = cli.build_parser()

    args = parser.parse_args([
        "--package", "lifegain", "8",
        "--package", "lifegain", "6",
    ])

    with pytest.raises(SystemExit) as exc:
        cli._configure_packages(
            args.package,
            args.no_packages,
            parser,
        )

    assert exc.value.code == 2


@pytest.mark.parametrize(
    "options",
    [
        ["--package", "misc", "5"],
        ["--package", "synergy-land", "5"],
        ["--package", "Unknown_Tag", "5"],
        ["--package", "removal", "10-5"],
        ["--package", "removal", "100"],
    ],
)
def test_m10_rejects_invalid_custom_packages(options):
    parser = cli.build_parser()
    args = parser.parse_args(options)

    with pytest.raises(SystemExit) as exc:
        cli._configure_packages(
            args.package,
            args.no_packages,
            parser,
        )

    assert exc.value.code == 2


def test_m10_custom_package_tag_validation():
    parser = cli.build_parser()
    db = SimpleNamespace(
        tag_slugs=frozenset({
            "ramp",
            "removal",
            "lifegain",
        })
    )

    cli._validate_custom_package_tags(
        db,
        [["lifegain", "8"]],
        parser,
    )

    with pytest.raises(SystemExit) as exc:
        cli._validate_custom_package_tags(
            db,
            [["not-an-oracle-tag", "8"]],
            parser,
        )

    assert exc.value.code == 2


def test_m10_no_packages_conflicts_with_custom():
    parser = cli.build_parser()

    args = parser.parse_args([
        "--no-packages",
        "--package", "lifegain", "8",
    ])

    with pytest.raises(SystemExit) as exc:
        cli._configure_packages(
            args.package,
            args.no_packages,
            parser,
        )

    assert exc.value.code == 2


def test_m10_package_syntax_is_equivalent():
    parser = cli.build_parser()

    equals = parser.parse_args([
        "--package", "lifegain=8",
        "--package", "interaction=7-9",
    ])

    spaced = parser.parse_args([
        "--package", "lifegain", "8",
        "--package", "interaction", "7-9",
    ])

    assert cli._configure_packages(
        equals.package,
        False,
        parser,
    ) == cli._configure_packages(
        spaced.package,
        False,
        parser,
    )

    # Duplicate detection also works across syntax forms.
    mixed = parser.parse_args([
        "--package", "ramp=8",
        "--package", "ramp", "10",
    ])

    with pytest.raises(SystemExit):
        cli._configure_packages(
            mixed.package,
            False,
            parser,
        )


def test_batch_generation_reuses_eligible_pool(tmp_path, monkeypatch):
    db = FakeDatabase()

    class Connection:
        @staticmethod
        def open(path):
            return db

    monkeypatch.setattr(cli, "CardDatabase", Connection)
    monkeypatch.setattr(cli, "ensure_database", lambda *, path, update: path)

    calls = []
    shared = frozenset({"cmd", "spell"})

    def eligible(self, database):
        calls.append(database)
        return shared

    monkeypatch.setattr(cli.CardPolicy, "eligible_cards", eligible)

    pools = []

    def fake_build(database, settings, **kwargs):
        pools.append(kwargs["eligible_cards"])
        return (
            SimpleNamespace(commanders=("cmd",), entries=()),
            SimpleNamespace(
                land_slots=37,
                nonland_slots=62,
                allocations=(),
                synergy_slots=0,
            ),
        )

    monkeypatch.setattr(cli, "build_deck", fake_build)
    monkeypatch.setattr(
        cli, "save_decklist", lambda database, deck, directory: tmp_path / "deck.txt"
    )

    assert cli.main([
        "--count", "3",
        "--database", str(tmp_path / "carddb.sqlite"),
    ]) == 0
    assert len(calls) == 1
    assert pools == [shared, shared, shared]
