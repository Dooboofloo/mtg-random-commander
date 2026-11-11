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
        "1/5 - Choosing commander...",
        "2/5 - Finding eligible cards...",
        "3/5 - Selecting nonland cards...",
        "4/5 - Allocating basic lands...",
        "5/5 - Validating deck...",
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
