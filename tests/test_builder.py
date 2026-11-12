"""Offline tests for the minimal single-commander generator."""

from dataclasses import dataclass
from random import Random

import pytest

from mtg_random_commander.builder import (
    build_deck,
    validate_deck,
)
from mtg_random_commander.models import DeckSettings
from mtg_random_commander.policy import CardPolicy
from mtg_random_commander.export import (
    export_lines,
    save_decklist,
)


@dataclass(frozen=True)
class Face:
    types: frozenset[str]
    supertypes: frozenset[str] = frozenset()
    subtypes: frozenset[str] = frozenset()
    oracle_text: str = ""
    power: str | None = None
    toughness: str | None = None


@dataclass(frozen=True)
class Card:
    oracle_id: str
    name: str
    color_identity: frozenset[str]
    faces: tuple[Face, ...]


class FakeDB:
    def __init__(self):
        self.cards: dict[str, Card] = {}

        self._add(
            "cmd",
            "Test Commander",
            "BG",
            (
                Face(
                    frozenset({"Creature"}),
                    frozenset({"Legendary"}),
                ),
            ),
        )

        for i in range(100):
            self._add(
                f"spell-{i:03}",
                f"Spell {i:03}",
                "G" if i % 2 else "B",
                (Face(frozenset({"Creature"})),),
            )

        self._add(
            "blue",
            "Blue Spell",
            "U",
            (Face(frozenset({"Instant"})),),
        )

        self._add(
            "mdfc",
            "Land // Spell",
            "G",
            (
                Face(frozenset({"Instant"})),
                Face(frozenset({"Land"})),
            ),
        )

        for name in (
            "Plains", "Island", "Swamp",
            "Mountain", "Forest", "Wastes",
        ):
            self._add(
                name.lower(),
                name,
                "",
                (
                    Face(
                        frozenset({"Land"}),
                        frozenset({"Basic"}),
                    ),
                ),
            )

    def _add(self, cid, name, colors, faces):
        self.cards[cid] = Card(
            cid, name, frozenset(colors), faces
        )

    def __getitem__(self, cid):
        return self.cards[cid]

    def resolve(self, ids):
        return tuple(self[cid] for cid in sorted(ids))

    def by_legality(self, fmt, status):
        return (
            frozenset(self.cards)
            if status == "legal"
            else frozenset()
        )

    def by_type(self, type_name):
        return frozenset(
            cid
            for cid, card in self.cards.items()
            if any(type_name in f.types for f in card.faces)
        )

    def by_supertype(self, type_name):
        return frozenset(
            cid
            for cid, card in self.cards.items()
            if any(type_name in f.supertypes for f in card.faces)
        )

    def by_subtype(self, type_name):
        return frozenset(
            cid
            for cid, card in self.cards.items()
            if any(type_name in f.subtypes for f in card.faces)
        )

    def by_name(self, name):
        return frozenset(
            cid
            for cid, card in self.cards.items()
            if name.casefold() == card.name.casefold()
        )

    def by_tag(self, slug):
        return frozenset()

    def within_identity(self, colors):
        allowed = set(colors)

        return frozenset(
            cid
            for cid, card in self.cards.items()
            if card.color_identity <= allowed
        )

    def legalities_for(self, cid):
        from types import SimpleNamespace

        return (
            SimpleNamespace(
                format="commander",
                status="legal",
            ),
        )

    def taggings_for(self, cid):
        return ()

    def get_tag(self, slug):
        from types import SimpleNamespace

        return SimpleNamespace(
            slug=slug,
            parents=frozenset(),
        )


@pytest.fixture
def db():
    return FakeDB()


def test_fixed_commander_basic_land_deck(db):
    settings = DeckSettings(
        commander_name="Test Commander",
        land_range=(37, 37),
        seed=12,
    )

    deck, plan = build_deck(db, settings)

    assert deck.commanders == ("cmd",)
    assert deck.total_count == 100
    assert deck.land_count == plan.land_slots == 37
    assert deck.nonland_count == 62

    assert all(
        cid not in {"blue", "mdfc", "cmd"}
        for cid in deck.quantities()
    )

    assert (
        deck.quantities()["forest"]
        + deck.quantities()["swamp"]
        == 37
    )

    assert all(
        quantity == 1
        for cid, quantity in deck.quantities().items()
        if cid not in {"forest", "swamp"}
    )

    validate_deck(db, deck, plan, CardPolicy())


def test_seed_is_reproducible(db):
    settings = DeckSettings(
        commander_name="Test Commander",
        seed=42,
    )

    a, plan_a = build_deck(db, settings)
    b, plan_b = build_deck(db, settings)

    assert plan_a == plan_b
    assert a.entries == b.entries


def test_random_commander_and_multiple_generations(db):
    rng = Random(8)

    a, _ = build_deck(db, DeckSettings(), rng=rng)
    b, _ = build_deck(db, DeckSettings(), rng=rng)

    assert a.commanders == b.commanders == ("cmd",)
    assert a.entries != b.entries


def test_unknown_commander_is_reported(db):
    with pytest.raises(ValueError, match="No eligible commander"):
        build_deck(
            db,
            DeckSettings(commander_name="Nobody"),
        )


def test_export_has_commander_section_and_never_overwrites(
    db, tmp_path
):
    deck, _ = build_deck(
        db,
        DeckSettings(
            commander_name="Test Commander",
            land_range=(36, 36),
            seed=3,
        ),
    )

    lines = export_lines(db, deck)

    assert "// COMMANDER" in lines
    assert lines[-1] == "1 Test Commander"

    a = save_decklist(db, deck, tmp_path)
    b = save_decklist(db, deck, tmp_path)

    assert a.name == "Test Commander.txt"
    assert b.name == "Test Commander_2.txt"

    assert (
        a.read_text(encoding="utf-8")
        == b.read_text(encoding="utf-8")
    )


def test_build_reports_progress(db):
    messages = []

    build_deck(
        db,
        DeckSettings(
            commander_name="Test Commander",
            seed=42,
        ),
        on_progress=messages.append,
    )

    assert messages == [
        "1/6 - Choosing commander...",
        "2/6 - Finding eligible cards...",
        "3/6 - Selecting functional packages...",
        "4/6 - Selecting commander synergies...",
        "5/6 - Allocating basic lands...",
        "6/6 - Validating deck...",
    ]


def test_named_commander_does_not_enumerate_commanders(
    db, monkeypatch
):
    def unexpected_scan(*args, **kwargs):
        raise AssertionError(
            "Named commander generation should not "
            "enumerate all commanders"
        )

    monkeypatch.setattr(
        CardPolicy,
        "commander_candidates",
        unexpected_scan,
    )

    deck, _ = build_deck(
        db,
        DeckSettings(
            commander_name="Test Commander",
            seed=42,
        ),
    )

    assert deck.commanders == ("cmd",)
    assert deck.total_count == 100


def test_precomputed_commander_pool_avoids_rescan(
    db, monkeypatch
):
    def unexpected_scan(*args, **kwargs):
        raise AssertionError(
            "Commander pool should not be recalculated"
        )

    monkeypatch.setattr(
        CardPolicy,
        "commander_candidates",
        unexpected_scan,
    )

    deck, plan = build_deck(
        db,
        DeckSettings(seed=42),
        commander_candidates=frozenset({"cmd"}),
    )

    assert deck.commanders == ("cmd",)
    assert deck.total_count == 100

def test_named_commander_uses_direct_eligibility(
    db, monkeypatch
):
    from mtg_random_commander.builder import _choose_commander

    def unexpected_bulk_query(*args, **kwargs):
        raise AssertionError(
            "Named commander selection must not "
            "construct the full eligibility pool"
        )

    monkeypatch.setattr(
        CardPolicy,
        "eligible_cards",
        unexpected_bulk_query,
    )

    checked = []

    def fake_allows_card(self, database, oracle_id):
        checked.append(oracle_id)
        return True

    monkeypatch.setattr(
        CardPolicy,
        "allows_card",
        fake_allows_card,
    )

    commander_id = _choose_commander(
        db,
        CardPolicy(),
        "Test Commander",
        Random(42),
    )

    assert commander_id == "cmd"
    assert checked == ["cmd"]


def test_functional_packages_are_filled_without_duplicates(db, monkeypatch):
    from collections import Counter
    from mtg_random_commander.models import DeckPackage

    tagged = {
        "ramp": {"spell-000", "spell-001", "spell-002", "mdfc", "blue"},
        "removal": {"spell-001", "spell-003", "spell-004"},
        "counterspell": {"spell-005"},
        "draw": {"spell-005", "spell-006", "spell-007", "spell-008"},
    }
    monkeypatch.setattr(db, "by_tag", lambda tag: frozenset(tagged.get(tag, ())))

    settings = DeckSettings(
        commander_name="Test Commander",
        land_range=(37, 37),
        seed=7,
        synergy_percent=0.0,
        packages=(
            DeckPackage("ramp", ("ramp",), (2, 2)),
            DeckPackage("interaction", ("removal", "counterspell"), (2, 2)),
            DeckPackage("draw", ("draw",), (2, 2)),
        ),
    )
    deck, plan = build_deck(db, settings)
    roles = Counter(entry.role for entry in deck.entries if entry.slot == "nonland")

    assert (roles["ramp"], roles["interaction"], roles["draw"]) == (2, 2, 2)
    assert roles["misc"] == 56
    assert plan.package_slots == 6
    assert plan.misc_slots == 56
    assert deck.total_count == 100
    assert not ({"blue", "mdfc"} & deck.quantities().keys())
    assert all(
        count == 1 for cid, count in deck.quantities().items()
        if cid not in {"swamp", "forest"}
    )
    validate_deck(db, deck, plan, CardPolicy())


def test_package_shortfalls_go_to_misc(db, monkeypatch):
    from collections import Counter
    from mtg_random_commander.models import DeckPackage

    monkeypatch.setattr(
        db, "by_tag",
        lambda tag: frozenset({"spell-000"}) if tag == "ramp" else frozenset(),
    )
    settings = DeckSettings(
        commander_name="Test Commander",
        land_range=(37, 37),
        seed=5,
        packages=(
            DeckPackage("ramp", ("ramp",), (4, 4)),
            DeckPackage("draw", ("draw",), (3, 3)),
        ),
    )
    deck, plan = build_deck(db, settings)
    roles = Counter(entry.role for entry in deck.entries if entry.slot == "nonland")

    assert plan.package_slots == 7
    assert roles["ramp"] == 1
    assert roles["draw"] == 0
    assert roles["misc"] == 61
    assert deck.total_count == 100


def test_package_overcommit_is_rejected(db):
    from mtg_random_commander.models import DeckPackage

    with pytest.raises(ValueError, match="Package targets require"):
        build_deck(
            db,
            DeckSettings(
                commander_name="Test Commander",
                land_range=(80, 80),
                packages=(DeckPackage("ramp", ("ramp",), (20, 20)),),
            ),
        )


def test_packages_can_be_disabled(db):
    deck, plan = build_deck(
        db,
        DeckSettings(
            commander_name="Test Commander",
            land_range=(37, 37),
            packages=(),
            seed=3,
        ),
    )
    assert plan.allocations == ()
    assert {entry.role for entry in deck.entries if entry.slot == "nonland"} == {"misc"}

def test_synergy_budget_and_misc_fallback(db, monkeypatch):
    from dataclasses import replace
    from types import SimpleNamespace
    from mtg_random_commander.models import DeckPackage

    original = db.cards["spell-001"]

    db.cards["spell-001"] = replace(
        original,
        faces=(
            replace(
                original.faces[0],
                subtypes=frozenset({"Elf"}),
            ),
        ),
    )

    db.types = frozenset({"Creature", "Land"})
    db.supertypes = frozenset({"Legendary", "Basic"})
    db.subtypes = frozenset({"Elf"})
    db.keywords = frozenset()

    monkeypatch.setattr(
        db,
        "taggings_for",
        lambda cid: (
            SimpleNamespace(tag_slug="typal-elf"),
        ),
    )

    monkeypatch.setattr(
        db,
        "by_tag",
        lambda slug, **kwargs: frozenset(),
    )

    deck, plan = build_deck(
        db,
        DeckSettings(
            commander_name="Test Commander",
            land_range=(37, 37),
            seed=42,
            packages=(
                DeckPackage(
                    "ramp", ("ramp",), (3, 3),
                ),
            ),
            synergy_percent=0.5,
        ),
    )

    assert plan.package_slots == 3
    assert plan.synergy_slots == int((62 - 3) * 0.5)
    assert plan.misc_slots == 62 - 3 - plan.synergy_slots

    assert sum(
        entry.quantity
        for entry in deck.entries
        if entry.role == "synergy"
    ) == 1

    assert sum(
        entry.quantity
        for entry in deck.entries
        if entry.role == "misc"
    ) == 61

    assert deck.total_count == 100
    assert deck.quantities()["spell-001"] == 1

    validate_deck(
        db, deck, plan, CardPolicy()
    )