"""Offline coverage-audit tests; no CardDB download or installed snapshot."""

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import csv
import json

from scripts.audit_synergy import (
    build_report,
    compare_inventory,
    family_for,
    write_reports,
)


@dataclass(frozen=True)
class Card:
    oracle_id: str
    name: str
    color_identity: frozenset[str]


class FakeDB:
    subtypes = frozenset({"Elf"})
    types = frozenset({"Creature", "Land"})
    supertypes = frozenset({"Legendary"})
    keywords = frozenset()

    def __init__(self):
        self.cards = {
            "green-cmd": Card("green-cmd", "Green Leader", frozenset("G")),
            "black-cmd": Card("black-cmd", "Black Leader", frozenset("B")),
            "elf": Card("elf", "Elf Card", frozenset("G")),
            "payoff": Card("payoff", "Elf Payoff", frozenset("G")),
            "foreign": Card("foreign", "Off-color Card", frozenset("U")),
        }
        self.tags = {
            "typal-elf": {"payoff", "foreign"},
            "typal-coupling": {"foreign"},
            "lifegain-matters": {"black-cmd"},
            "synergy-unknown-concept": set(),
        }
        self.commander_tags = {
            "green-cmd": ("typal-elf", "typal-coupling"),
            "black-cmd": ("typal-elf", "lifegain-matters", "synergy-unknown-concept"),
        }

    def resolve(self, ids):
        return tuple(self.cards[cid] for cid in sorted(ids))

    def taggings_for(self, cid):
        return tuple(SimpleNamespace(tag_slug=tag) for tag in self.commander_tags[cid])

    def by_tag(self, slug, *, include_descendants=True):
        return frozenset(self.tags[slug])

    def by_subtype(self, subtype):
        return frozenset({"elf"} if subtype == "Elf" else ())

    def by_type(self, kind):
        return frozenset()

    def by_supertype(self, kind):
        return frozenset()

    def by_keyword(self, name):
        return frozenset()

    def within_identity(self, colors):
        allowed = set(colors)
        return frozenset(
            cid for cid, card in self.cards.items()
            if card.color_identity <= allowed
        )

    def info(self):
        return SimpleNamespace(
            created_at="2026-11-12",
            schema_version=1,
            sources=(SimpleNamespace(
                source_type="oracle_tags",
                source_updated_at="2026-11-11",
            ),),
        )


class FakePolicy:
    include_banned = False

    def commander_candidates(self, db):
        return frozenset({"green-cmd", "black-cmd"})

    def eligible_cards(self, db):
        return frozenset(db.cards)


def test_family_priorities():
    assert family_for("typal-fungus") == "typal-*"
    assert family_for("landfall") == "*fall"
    assert family_for("lifegain-matters") == "*-matters"
    assert family_for("graveyard-fuel-something") == "graveyard-fuel-*"
    assert family_for("cycle-whatever") == "other/cycle"


def test_coverage_distinguishes_parser_status_and_color_legal_pools():
    report = build_report(FakeDB(), FakePolicy())
    rows = {row["tag"]: row for row in report["tags"]}
    assert report["summary"]["eligible_commanders"] == 2
    assert report["summary"]["distinct_direct_tags"] == 4
    assert rows["typal-elf"]["status"] == "expanded"
    assert rows["typal-elf"]["commanders"] == 2
    assert rows["typal-elf"]["actionable_commanders"] == 1
    assert rows["typal-elf"]["pool_size"] == 3
    assert rows["typal-elf"]["direct_size"] == 2
    assert rows["typal-elf"]["inferred_size"] == 1
    assert rows["typal-coupling"]["status"] == "skipped"
    assert rows["lifegain-matters"]["status"] == "unsupported"
    assert rows["synergy-unknown-concept"]["status"] == "recognized-empty"
    assert report["summary"]["commanders_with_actionable_synergy"] == 1


def test_json_csv_and_legacy_compare(tmp_path: Path):
    report = build_report(FakeDB(), FakePolicy())
    previous = tmp_path / "old-tags.txt"
    previous.write_text("# historical\ntypal-elf\nold-tag\n", encoding="utf-8")
    report["baseline"] = compare_inventory(report, previous)
    assert report["baseline"]["added"] == [
        "lifegain-matters", "synergy-unknown-concept", "typal-coupling"
    ]
    assert report["baseline"]["removed"] == ["old-tag"]

    json_file = tmp_path / "out" / "coverage.json"
    csv_file = tmp_path / "out" / "coverage.csv"
    write_reports(report, json_file, csv_file)
    saved = json.loads(json_file.read_text(encoding="utf-8"))
    assert saved["summary"] == report["summary"]
    with csv_file.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 4
    assert rows[0]["tag"] == "typal-elf"


def test_direct_only_and_hierarchy_delta_are_reported():
    class HierarchyDB(FakeDB):
        def by_tag(self, slug, *, include_descendants=True):
            result = super().by_tag(slug, include_descendants=include_descendants)
            if slug == "typal-elf" and include_descendants:
                return result | {"elf"}
            return result

    db = HierarchyDB()
    db.commander_tags["green-cmd"] += ("synergy-mystery",)
    db.tags["synergy-mystery"] = {"payoff"}
    rows = {
        row["tag"]: row
        for row in build_report(db, FakePolicy())["tags"]
    }
    assert rows["typal-elf"]["descendant_extra"] == 1
    assert rows["synergy-mystery"]["status"] == "direct-only"
    assert rows["synergy-mystery"]["inferred_size"] == 0
    assert rows["synergy-mystery"]["actionable_commanders"] == 1


def test_inventory_and_report_are_deterministic():
    db = FakeDB()
    policy = FakePolicy()
    assert build_report(db, policy) == build_report(db, policy)
