from random import Random
from types import SimpleNamespace

from mtg_random_commander.models import Deck
from mtg_random_commander.synergy import (
    fill_synergy,
    get_synergy_packages,
    parse_synergy_tag,
)


class FakeDB:
    types = frozenset({
        "Creature", "Artifact", "Land",
    })
    supertypes = frozenset({
        "Legendary", "Snow",
    })
    subtypes = frozenset({
        "Elf", "Goblin", "Orc", "Time Lord",
        "Desert", "Saga", "Pirate",
        "Wolf", "Werewolf",
    })
    keywords = frozenset({"Flying"})

    def __init__(self, taggings=()):
        self._taggings = taggings

        self.tags = {
            "typal-goblin-orc": {"goblin-payoff"},
            "typal-time-lord": {"lord-payoff"},
            "creaturefall": {"creaturefall-payoff"},
            "synergy-desert": {"desert-payoff"},
            "synergy-historic": {"historic-payoff"},
            "synergy-outlaw": {"outlaw-payoff"},
            "affinity-for-artifacts": {"artifact-payoff"},
        }

        self.subtype_members = {
            "Goblin": {"goblin-card"},
            "Orc": {"orc-card"},
            "Time Lord": {"lord-card"},
            "Desert": {"desert-land"},
            "Saga": {"saga-card"},
            "Pirate": {"pirate-card"},
        }

        self.type_members = {
            "Artifact": {"artifact-card"},
            "Creature": {"random-creature"},
            "Land": {"desert-land"},
        }

        self.supertype_members = {
            "Legendary": {"legend-card"},
        }

    def taggings_for(self, cid):
        return tuple(
            SimpleNamespace(tag_slug=tag)
            for tag in self._taggings
        )

    def by_tag(self, slug, *, include_descendants=True):
        return frozenset(self.tags.get(slug, ()))

    def by_subtype(self, name):
        return frozenset(self.subtype_members.get(name, ()))

    def by_type(self, name):
        return frozenset(self.type_members.get(name, ()))

    def by_supertype(self, name):
        return frozenset(self.supertype_members.get(name, ()))

    def by_keyword(self, name):
        return frozenset()


def test_typal_union_and_multiword_subtype():
    db = FakeDB()

    orcs = parse_synergy_tag(
        db, "typal-goblin-orc"
    )
    assert orcs.mode == "typal"
    assert orcs.pool == {
        "goblin-card",
        "orc-card",
        "goblin-payoff",
    }

    lords = parse_synergy_tag(
        db, "typal-time-lord"
    )
    assert lords.pool == {
        "lord-card",
        "lord-payoff",
    }


def test_broad_creaturefall_excludes_generic_creatures():
    db = FakeDB()

    package = parse_synergy_tag(
        db, "creaturefall"
    )

    assert package.pool == {
        "creaturefall-payoff",
    }


def test_desert_land_kept_in_source_pool_but_not_nonland_selection():
    db = FakeDB(["synergy-desert"])

    (package,) = get_synergy_packages(
        db, "commander"
    )

    assert {
        "desert-land",
        "desert-payoff",
    } <= package.pool

    deck = Deck(commanders=("commander",))
    available = {
        "desert-payoff",
        "regular-card",
    }

    assert fill_synergy(
        db, deck, "commander",
        available, 2, Random(42),
    ) == 1

    assert deck.quantities() == {
        "desert-payoff": 1,
    }

    assert available == {
        "regular-card",
    }


def test_historic_and_outlaw_expand_named_categories():
    db = FakeDB()

    historic = parse_synergy_tag(
        db, "synergy-historic"
    )

    outlaw = parse_synergy_tag(
        db, "synergy-outlaw"
    )

    assert {
        "historic-payoff",
        "artifact-card",
        "legend-card",
        "saga-card",
    } <= historic.pool

    assert {
        "outlaw-payoff",
        "pirate-card",
    } <= outlaw.pool


def test_overlapping_packages_remain_unique_and_seeded():
    db = FakeDB([
        "typal-goblin-orc",
        "affinity-for-artifacts",
    ])

    available = {
        "goblin-card",
        "orc-card",
        "goblin-payoff",
        "artifact-card",
        "artifact-payoff",
    }

    a = Deck(commanders=("cmd",))
    remaining_a = set(available)

    count = fill_synergy(
        db, a, "cmd",
        remaining_a, 3, Random(42),
    )

    b = Deck(commanders=("cmd",))
    remaining_b = set(available)

    fill_synergy(
        db, b, "cmd",
        remaining_b, 3, Random(42),
    )

    assert count == 3
    assert a.entries == b.entries
    assert remaining_a == remaining_b
    assert len(a.quantities()) == 3


def test_unrecognized_tags_do_not_generate_synergy():
    db = FakeDB([
        "ramp",
        "synergy-non-permanent",
    ])

    assert parse_synergy_tag(
        db, "ramp"
    ) is None

    assert get_synergy_packages(
        db, "cmd"
    ) == ()


def test_negated_typal_does_not_expand_positive_type():
    db = FakeDB()

    db.tags["typal-non-goblin"] = {
        "non-goblin-payoff",
    }

    package = parse_synergy_tag(
        db, "typal-non-goblin"
    )

    assert package.pool == {
        "non-goblin-payoff",
    }

def test_typal_coupling_does_not_expand_unrelated_tribes():
    db = FakeDB([
        "typal-coupling",
        "typal-fungus",
    ])

    db.tags["typal-coupling"] = {
        "unrelated-tribal-card",
    }

    db.tags["typal-fungus"] = {
        "fungus-payoff",
    }

    db.subtypes = db.subtypes | {"Fungus"}
    db.subtype_members["Fungus"] = {
        "fungus-creature",
    }

    assert parse_synergy_tag(
        db, "typal-coupling"
    ) is None

    packages = get_synergy_packages(
        db, "commander"
    )

    assert len(packages) == 1
    assert packages[0].source_tag == "typal-fungus"
    assert packages[0].pool == {
        "fungus-payoff",
        "fungus-creature",
    }