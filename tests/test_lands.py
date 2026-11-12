"""Offline tests for mana bases and MDFC slot eligibility."""

from dataclasses import dataclass, replace
from random import Random

import pytest

from mtg_random_commander.lands import (
    _fetch_types,
    build_mana_base,
    candidate_pools,
    mana_demand,
    slot_eligible,
)
from mtg_random_commander.models import Deck


@dataclass(frozen=True)
class Face:
    types: frozenset[str]
    mana_cost: str = ""
    oracle_text: str = ""


@dataclass(frozen=True)
class Card:
    oracle_id: str
    name: str
    color_identity: frozenset[str]
    faces: tuple[Face, ...]
    layout: str = "normal"
    produced_mana: frozenset[str] = frozenset()
    subtypes: frozenset[str] = frozenset()
    supertypes: frozenset[str] = frozenset()


class FakeDB:
    def __init__(self):
        self.cards = {}
        self.synergy_pools = ()

        self.add(
            "cmd", "Commander", "BG",
            [Face(frozenset({"Creature"}), "{B}{G}")],
        )

        for name in (
            "Plains", "Island", "Swamp",
            "Mountain", "Forest", "Wastes",
        ):
            self.add(
                name.lower(), name, "",
                [Face(frozenset({"Land"}))],
                supertypes={"Basic"},
                subtypes={name},
            )

            if name != "Wastes":
                self.add(
                    "snow-" + name.lower(),
                    "Snow-Covered " + name,
                    "",
                    [Face(frozenset({"Land"}))],
                    supertypes={"Basic", "Snow"},
                    subtypes={name},
                )

        for i in range(80):
            self.add(
                f"spell-{i}", f"Spell {i}", "BG",
                [Face(frozenset({"Sorcery"}), "{G}{G}{B}")],
            )

        self.add(
            "bala",
            "Bala Ged Recovery // Bala Ged Sanctuary",
            "G",
            [
                Face(frozenset({"Sorcery"}), "{2}{G}"),
                Face(frozenset({"Land"})),
            ],
            layout="modal_dfc",
            produced={"G"},
        )

        self.add(
            "azcanta",
            "Search for Azcanta // Azcanta, the Sunken Ruin",
            "U",
            [
                Face(frozenset({"Enchantment"}), "{1}{U}"),
                Face(frozenset({"Land"})),
            ],
            layout="transform",
        )

        self.add(
            "transform-land",
            "Test Transforming Land",
            "",
            [
                Face(frozenset({"Land"})),
                Face(frozenset({"Creature"}), "{2}"),
            ],
            layout="transform",
        )

        self.add(
            "forest-dual",
            "Woodland Cemetery",
            "BG",
            [Face(frozenset({"Land"}))],
            produced={"B", "G"},
        )

        self.add(
            "utility",
            "Ghost Quarter",
            "",
            [Face(frozenset({"Land"}))],
            produced={"C"},
        )

        self.add(
            "bad-fetch",
            "Flooded Strand",
            "",
            [
                Face(
                    frozenset({"Land"}),
                    oracle_text=(
                        "Search your library for a Plains or Island card"
                    ),
                )
            ],
        )

        self.add(
            "good-fetch",
            "Verdant Catacombs",
            "",
            [
                Face(
                    frozenset({"Land"}),
                    oracle_text=(
                        "Search your library for a Swamp or Forest card"
                    ),
                )
            ],
        )

    def add(
        self, cid, name, colors, faces, *,
        layout="normal", produced=(),
        subtypes=(), supertypes=(),
    ):
        self.cards[cid] = Card(
            cid,
            name,
            frozenset(colors),
            tuple(faces),
            layout,
            frozenset(produced),
            frozenset(subtypes),
            frozenset(supertypes),
        )

    def __getitem__(self, cid):
        return self.cards[cid]

    def by_type(self, kind):
        return frozenset(
            cid for cid, card in self.cards.items()
            if any(kind in face.types for face in card.faces)
        )

    def by_supertype(self, kind):
        return frozenset(
            cid for cid, card in self.cards.items()
            if kind in card.supertypes
        )

    def by_name(self, name):
        return frozenset(
            cid for cid, card in self.cards.items()
            if card.name.casefold() == name.casefold()
        )

    def produces_mana(self, color):
        return frozenset(
            cid for cid, card in self.cards.items()
            if color in card.produced_mana
        )

    def taggings_for(self, cid):
        return ()


def test_modal_dfc_dual_slot_and_transform_front_face():
    db = FakeDB()
    land, nonland = candidate_pools(
        db, frozenset(db.cards)
    )

    assert "bala" in land
    assert "bala" in nonland

    assert "azcanta" not in land
    assert "azcanta" in nonland

    assert "transform-land" in land
    assert "transform-land" not in nonland

    assert "forest-dual" in land
    assert "forest-dual" not in nonland

    assert not slot_eligible(
        db["forest-dual"], "nonland"
    )


def test_mana_symbol_weighting():
    db = FakeDB()

    db.add(
        "hybrid", "Hybrid", "BG",
        [
            Face(
                frozenset({"Instant"}),
                "{B/G}{G/P}{2}{X}",
            )
        ],
    )

    deck = Deck(commanders=("cmd",))
    deck.add(
        "hybrid",
        slot="nonland",
        role="misc",
    )

    demand = mana_demand(db, deck)

    assert demand["B"] == pytest.approx(1.5)
    assert demand["G"] == pytest.approx(2.5)


def test_mdfc_selected_as_spell_cannot_be_selected_as_land():
    db = FakeDB()
    deck = Deck(commanders=("cmd",))
    deck.add("bala", slot="nonland", role="synergy")

    land, _ = candidate_pools(db, frozenset(db.cards))

    build_mana_base(
        db,
        deck,
        frozenset(db.cards),
        land,
        20,
        Random(4),
        nonbasic_fraction=1,
        snow_chance=0,
    )

    assert deck.land_count == 20
    assert deck.quantities()["bala"] == 1
    assert deck.mainboard_count == 21


def test_fixed_seed_and_snow_basics():
    db = FakeDB()
    land, _ = candidate_pools(db, frozenset(db.cards))

    def make():
        deck = Deck(commanders=("cmd",))
        build_mana_base(
            db, deck, frozenset(db.cards),
            land, 30, Random(8),
            nonbasic_fraction=0,
            snow_chance=1,
        )
        return deck

    a, b = make(), make()

    assert a.entries == b.entries
    assert a.land_count == 30

    assert all(
        db[entry.oracle_id].name.startswith("Snow-Covered ")
        for entry in a.entries
    )


def test_fetchland_requires_existing_target():
    db = FakeDB()

    assert _fetch_types(db["bad-fetch"]) == {
        "Island", "Plains",
    }
    assert _fetch_types(db["good-fetch"]) == {
        "Swamp", "Forest",
    }
    assert _fetch_types(db["utility"]) == set()

    land, _ = candidate_pools(db, frozenset(db.cards))

    for seed in range(8):
        deck = Deck(commanders=("cmd",))

        build_mana_base(
            db, deck, frozenset(db.cards),
            land, 12, Random(seed),
            nonbasic_fraction=0.85,
            snow_chance=0,
        )

        assert "bad-fetch" not in deck.quantities()
        assert deck.land_count == 12


def test_colorless_commander_gets_wastes():
    db = FakeDB()

    db.cards["cmd"] = replace(
        db.cards["cmd"],
        color_identity=frozenset(),
    )

    land, _ = candidate_pools(db, frozenset(db.cards))
    deck = Deck(commanders=("cmd",))

    build_mana_base(
        db, deck, frozenset(db.cards),
        land, 34, Random(1),
        nonbasic_fraction=0,
        snow_chance=1,
    )

    assert deck.quantities() == {"wastes": 34}


def test_snow_commander_forces_snow_basics():
    db = FakeDB()

    db.cards["cmd"] = replace(
        db.cards["cmd"],
        supertypes=frozenset({"Snow"}),
    )

    land, _ = candidate_pools(db, frozenset(db.cards))
    deck = Deck(commanders=("cmd",))

    build_mana_base(
        db, deck, frozenset(db.cards),
        land, 30, Random(1),
        nonbasic_fraction=0,
        snow_chance=0,
    )

    assert all(
        db[cid].name.startswith("Snow-Covered ")
        for cid in deck.quantities()
    )
