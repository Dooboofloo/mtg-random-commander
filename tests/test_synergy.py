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

    @property
    def tag_slugs(self):
        return frozenset(self.tags)

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


def test_m8_token_concepts_find_generators_not_token_cards():
    db = FakeDB()
    db.types = db.types | {"Token"}
    db.type_members["Token"] = {"nonplayable-token"}

    db.tags.update({
        "synergy-token": {"token-payoff"},
        "tokenfall": {"tokenfall-payoff"},
        "repeatable-token-generator": {"token-creator"},
        "repeatable-creature-tokens": {"saproling-creator"},
    })

    assert parse_synergy_tag(db, "synergy-token").pool == {
        "token-payoff",
        "token-creator",
        "saproling-creator",
    }

    assert parse_synergy_tag(db, "tokenfall").pool == {
        "tokenfall-payoff",
        "token-creator",
        "saproling-creator",
    }

    assert "nonplayable-token" not in parse_synergy_tag(
        db, "synergy-token"
    ).pool


def test_m8_plains_and_special_typal_concepts():
    db = FakeDB()
    db.subtypes = db.subtypes | {
        "Plains", "Samurai", "Warrior",
    }
    db.subtype_members.update({
        "Plains": {"plains-land"},
        "Samurai": {"samurai-card"},
        "Warrior": {"warrior-card"},
        "Wolf": {"wolf-card"},
        "Werewolf": {"werewolf-card"},
    })
    db.tags["plainsfall"] = {"plains-payoff"}
    db.tags["synergy-plains"] = {"plains-synergy"}

    assert "plains-land" in parse_synergy_tag(
        db, "plainsfall"
    ).pool
    assert "plains-land" in parse_synergy_tag(
        db, "synergy-plains"
    ).pool

    assert {"wolf-card", "werewolf-card"} <= parse_synergy_tag(
        db, "typal-lupine"
    ).pool
    assert {"samurai-card", "warrior-card"} <= parse_synergy_tag(
        db, "typal-neo-solo-attack"
    ).pool


def test_m8_both_coupling_tags_are_skipped():
    from mtg_random_commander.synergy import (
        SKIPPED_SYNERGY_TAGS,
        recognizes_synergy_tag,
    )

    db = FakeDB()

    for slug in SKIPPED_SYNERGY_TAGS:
        db.tags[slug] = {"unrelated-card"}
        assert not recognizes_synergy_tag(slug)
        assert parse_synergy_tag(db, slug) is None


def test_m8_matters_tags_find_enablers():
    db = FakeDB(["lifegain-matters"])
    db.tags.update({
        "lifegain-matters": {"lifegain-payoff"},
        "repeatable-lifegain": {"healing-engine"},
        "lifegain": {"healing-spell"},
    })

    (package,) = get_synergy_packages(db, "commander")

    assert package.mode == "matters"
    assert package.pool == {
        "lifegain-payoff",
        "healing-engine",
        "healing-spell",
    }


def test_m8_unknown_matters_tags_remain_unsupported():
    from mtg_random_commander.synergy import recognizes_synergy_tag

    # Broad/ambiguous descriptors must not become blanket synergy families.
    db = FakeDB()
    assert not recognizes_synergy_tag("table-order-matters")
    assert parse_synergy_tag(db, "table-order-matters") is None
    assert not recognizes_synergy_tag("repeatable-crime")


def test_m8_missing_optional_enabler_tags_do_not_raise():
    class StrictDB(FakeDB):
        @property
        def tag_slugs(self):
            return frozenset(self.tags)

        def by_tag(self, slug, *, include_descendants=True):
            if slug not in self.tags:
                raise LookupError(slug)
            return super().by_tag(
                slug, include_descendants=include_descendants
            )

    db = StrictDB()
    db.tags["lifegain-matters"] = {"payoff"}
    db.tags["repeatable-lifegain"] = {"healer"}

    assert parse_synergy_tag(db, "lifegain-matters").pool == {
        "payoff", "healer",
    }


def test_m8_sacrifice_enablers_deduplicate_across_tags():
    db = FakeDB(["your-sacrifice-matters"])
    db.tags.update({
        "your-sacrifice-matters": {"payoff"},
        "repeatable-creature-tokens": {"fodder"},
        "sacrifice-outlet-creature": {"outlet"},
        "free-sacrifice-outlet": {"outlet"},
    })

    deck = Deck(commanders=("commander",))
    available = {"payoff", "fodder", "outlet", "unrelated"}

    assert fill_synergy(
        db, deck, "commander",
        available, 3, Random(42),
    ) == 3

    assert len(deck.quantities()) == 3
    assert available == {"unrelated"}

def test_pridemate_uses_lifegain_enablers():
    db = FakeDB(["pridemate"])

    db.tags.update({
        "pridemate": {"pridemate-payoff"},
        "lifegain": {"lifegain-spell"},
        "repeatable-lifegain": {"lifegain-engine"},
        "soul-warden-ability": {"soul-warden"},
    })

    (package,) = get_synergy_packages(
        db, "commander"
    )

    assert package.mode == "matters"
    assert package.pool == {
        "pridemate-payoff",
        "lifegain-spell",
        "lifegain-engine",
        "soul-warden",
    }


def test_synergy_weights_packages_not_pool_sizes():
    db = FakeDB([
        "synergy-wide",
        "synergy-narrow",
    ])

    wide = {
        f"wide-{i:04d}" for i in range(1000)
    }
    narrow = {
        f"narrow-{i:04d}" for i in range(20)
    }

    db.tags["synergy-wide"] = wide
    db.tags["synergy-narrow"] = narrow

    def select(seed):
        deck = Deck(commanders=("commander",))
        available = wide | narrow

        count = fill_synergy(
            db,
            deck,
            "commander",
            available,
            20,
            Random(seed),
        )

        assert count == 20
        assert len(deck.quantities()) == 20

        return deck

    first = select(42)
    second = select(42)

    assert first.entries == second.entries

    selected = set(first.quantities())

    # A small theme should receive meaningful representation,
    # rather than being overwhelmed by 1,000 other candidates.
    assert len(selected & narrow) >= 5


def test_synergy_package_exhaustion_and_overlap():
    db = FakeDB([
        "synergy-first",
        "synergy-second",
    ])

    db.tags["synergy-first"] = {
        "shared", "first",
    }
    db.tags["synergy-second"] = {
        "shared", "second",
    }

    deck = Deck(commanders=("commander",))
    available = {
        "shared", "first", "second", "unrelated",
    }

    count = fill_synergy(
        db,
        deck,
        "commander",
        available,
        4,
        Random(42),
    )

    assert count == 3
    assert set(deck.quantities()) == {
        "shared", "first", "second",
    }
    assert available == {"unrelated"}

def test_m8c_compound_tutor_constraints():
    db = FakeDB()

    db.types = db.types | {
        "Instant", "Sorcery",
    }
    db.supertypes = db.supertypes | {"Basic"}
    db.subtypes = db.subtypes | {
        "Dragon", "Forest", "Equipment", "Lesson",
        "Time Lord",
    }

    db.type_members.update({
        "Creature": {
            "dragon", "flying-creature",
            "artifact-creature", "time-lord",
        },
        "Artifact": {
            "artifact", "artifact-creature", "equipment",
        },
        "Land": {
            "basic-forest", "other-land",
        },
        "Instant": {"instant", "lesson-instant"},
        "Sorcery": {"lesson-sorcery"},
    })

    db.subtype_members.update({
        "Dragon": {"dragon"},
        "Equipment": {"equipment"},
        "Forest": {"basic-forest", "other-land"},
        "Lesson": {"lesson-instant", "lesson-sorcery"},
        "Time Lord": {"time-lord"},
    })

    db.supertype_members["Basic"] = {"basic-forest"}
    db.by_keyword = lambda name: (
        frozenset({"flying-creature"})
        if name == "Flying"
        else frozenset()
    )

    assert parse_synergy_tag(
        db, "tutor-creature-dragon"
    ).pool == {"dragon"}

    assert parse_synergy_tag(
        db, "tutor-artifact-noncreature"
    ).pool == {"artifact", "equipment"}

    assert parse_synergy_tag(
        db, "tutor-land-basic-forest"
    ).pool == {"basic-forest"}

    assert parse_synergy_tag(
        db, "tutor-creature-flying"
    ).pool == {"flying-creature"}

    assert parse_synergy_tag(
        db, "tutor-creature-time-lord"
    ).pool == {"time-lord"}

    assert parse_synergy_tag(
        db, "impulse-instant-sorcery-lesson"
    ).pool == {"lesson-instant", "lesson-sorcery"}

    assert parse_synergy_tag(
        db, "regrowth-instant-sorcery"
    ).pool == {
        "instant", "lesson-instant", "lesson-sorcery",
    }


def test_m8c_reanimation_copying_and_cost_reduction():
    db = FakeDB()

    db.types = db.types | {"Instant"}

    db.type_members.update({
        "Creature": {"creature", "artifact-creature"},
        "Artifact": {"artifact", "artifact-creature"},
        "Instant": {"instant"},
    })

    assert parse_synergy_tag(
        db, "reanimate"
    ).pool == {"creature", "artifact-creature"}

    assert parse_synergy_tag(
        db, "reanimate-artifact-creature"
    ).pool == {"artifact-creature"}

    assert parse_synergy_tag(
        db, "copy-instant"
    ).pool == {"instant"}

    assert parse_synergy_tag(
        db, "cost-reducer-artifact"
    ).pool == {"artifact", "artifact-creature"}


def test_m8c_target_tags_using_ability_enablers():
    db = FakeDB()

    db.tags.update({
        "tutor-interaction": {"tutor-payoff"},
        "removal": {"removal-card"},
        "counterspell": {"counterspell-card"},
        "copy-token": {"copy-payoff"},
        "repeatable-token-generator": {"token-maker"},
        "repeatable-creature-tokens": {"creature-token-maker"},
    })

    assert parse_synergy_tag(
        db, "tutor-interaction"
    ).pool == {
        "tutor-payoff",
        "removal-card",
        "counterspell-card",
    }

    assert parse_synergy_tag(
        db, "copy-token"
    ).pool == {
        "copy-payoff",
        "token-maker",
        "creature-token-maker",
    }


def test_m8c_ambiguous_target_tags_remain_unsupported():
    from mtg_random_commander.synergy import recognizes_synergy_tag

    db = FakeDB()

    unsupported = (
        "copy-self",
        "copy-nonland",
        "tutor-card",
        "tutor-to-hand",
        "reanimate-from-opponent",
        "reanimate-face-down",
        "impulse-to-top",
        "impulse-pw-tyvar",
        "tutor-from-opponent",
    )

    for slug in unsupported:
        assert not recognizes_synergy_tag(slug)
        assert parse_synergy_tag(db, slug) is None


def test_m8c_target_families_are_independent_packages():
    db = FakeDB([
        "tutor-creature-dragon",
        "copy-instant",
    ])

    db.types = db.types | {"Instant"}
    db.subtypes = db.subtypes | {"Dragon"}

    db.type_members["Creature"] = {"dragon", "other-creature"}
    db.type_members["Instant"] = {"instant"}
    db.subtype_members["Dragon"] = {"dragon"}

    packages = get_synergy_packages(db, "commander")

    assert len(packages) == 2
    assert {package.mode for package in packages} == {
        "tutor", "copy",
    }

    assert {
        package.source_tag: package.pool
        for package in packages
    } == {
        "tutor-creature-dragon": {"dragon"},
        "copy-instant": {"instant"},
    }

    deck = Deck(commanders=("commander",))
    available = {"dragon", "instant", "unrelated"}

    selected = fill_synergy(
        db, deck, "commander",
        available, 3, Random(42),
    )

    assert selected == 2
    assert set(deck.quantities()) == {"dragon", "instant"}
    assert available == {"unrelated"}


def test_m8d_graveyard_consumers_get_graveyard_setup():
    db = FakeDB(["graveyard-fuel-creature"])

    db.tags.update({
        "graveyard-fuel-creature": {"graveyard-payoff"},
        "mill-self": {"self-miller"},
        "repeatable-surveil": {"surveil-engine"},
        "loot": {"looter"},
    })

    (package,) = get_synergy_packages(db, "commander")

    assert package.mode == "resource"
    assert package.pool == {
        "graveyard-payoff",
        "self-miller",
        "surveil-engine",
        "looter",
    }


def test_m8d_self_mill_finds_graveyard_payoffs():
    db = FakeDB(["mill-self"])

    db.tags.update({
        "mill-self": {"self-miller"},
        "reanimate-creature": {"reanimator"},
        "threshold": {"threshold-payoff"},
        "graveyard-fuel-creature": {"graveyard-consumer"},
    })

    (package,) = get_synergy_packages(db, "commander")

    assert package.pool == {
        "self-miller",
        "reanimator",
        "threshold-payoff",
        "graveyard-consumer",
    }


def test_m8d_sacrifice_outlets_get_matching_fodder():
    db = FakeDB()

    db.tags.update({
        "sacrifice-outlet-creature": {"creature-outlet"},
        "sacrifice-outlet-artifact": {"artifact-outlet"},
        "repeatable-creature-tokens": {"creature-maker"},
        "repeatable-artifact-tokens": {"artifact-maker"},
    })

    creature = parse_synergy_tag(
        db, "sacrifice-outlet-creature"
    )
    artifact = parse_synergy_tag(
        db, "sacrifice-outlet-artifact"
    )

    assert "creature-maker" in creature.pool
    assert "artifact-maker" not in creature.pool

    assert "artifact-maker" in artifact.pool
    assert "creature-maker" not in artifact.pool


def test_m8d_untappers_select_appropriate_permanent_types():
    db = FakeDB()

    db.tags.update({
        "untapper-creature": {"creature-untapper"},
        "untapper-artifact": {"artifact-untapper"},
        "untapper-land": {"land-untapper"},
        "mana-dork": {"dork", "mana-rock"},
        "mana-producer": {"dork", "mana-rock", "mana-land"},
    })

    db.type_members.update({
        "Creature": {"dork"},
        "Artifact": {"mana-rock"},
        "Land": {"mana-land"},
    })

    creature = parse_synergy_tag(
        db, "untapper-creature"
    )
    artifact = parse_synergy_tag(
        db, "untapper-artifact"
    )
    land = parse_synergy_tag(
        db, "untapper-land"
    )

    assert "dork" in creature.pool
    assert "mana-rock" not in creature.pool

    assert "mana-rock" in artifact.pool
    assert "dork" not in artifact.pool

    assert "mana-land" in land.pool
    assert "mana-rock" not in land.pool


def test_m8d_counter_resources_and_proliferate():
    db = FakeDB()

    db.tags.update({
        "counter-fuel-energy": {"energy-commander"},
        "gains-pp-counters": {"growing-commander"},
        "energy-generator": {"energy-producer"},
        "repeatable-proliferate": {"proliferator"},
    })

    energy = parse_synergy_tag(
        db, "counter-fuel-energy"
    )
    counters = parse_synergy_tag(
        db, "gains-pp-counters"
    )

    assert "energy-producer" in energy.pool
    assert "proliferator" in energy.pool
    assert "proliferator" in counters.pool


def test_m8d_keyword_relationships_are_directional():
    db = FakeDB()

    db.tags.update({
        "gives-lifelink": {"lifelink-granter"},
        "pridemate": {"lifegain-payoff"},
        "lifegain-matters": {"lifegain-engine-payoff"},
        "gives-deathtouch": {"deathtouch-granter"},
        "pinger": {"pinger"},
    })

    lifelink = parse_synergy_tag(
        db, "gives-lifelink"
    )
    deathtouch = parse_synergy_tag(
        db, "gives-deathtouch"
    )

    assert {
        "lifelink-granter",
        "lifegain-payoff",
        "lifegain-engine-payoff",
    } <= lifelink.pool

    assert "pinger" in deathtouch.pool


def test_m8d_ambiguous_resource_tags_remain_unsupported():
    from mtg_random_commander.synergy import (
        recognizes_synergy_tag,
    )

    db = FakeDB()

    for slug in (
        "tap-fuel-unknown",
        "graveyard-fuel-self",
        "gains-soulshift",
        "sneak-self",
    ):
        assert not recognizes_synergy_tag(slug)
        assert parse_synergy_tag(db, slug) is None


def test_m8d_resource_packages_remain_independent():
    db = FakeDB([
        "graveyard-fuel-creature",
        "sacrifice-outlet-creature",
    ])

    db.tags.update({
        "graveyard-fuel-creature": set(),
        "sacrifice-outlet-creature": set(),
        "mill-self": {"miller"},
        "repeatable-surveil": {"surveiller"},
        "repeatable-creature-tokens": {"fodder-maker"},
    })

    packages = get_synergy_packages(db, "commander")

    assert len(packages) == 2
    assert {package.mode for package in packages} == {
        "resource",
    }

    deck = Deck(commanders=("commander",))
    available = {
        "miller",
        "surveiller",
        "fodder-maker",
        "unrelated",
    }

    chosen = fill_synergy(
        db,
        deck,
        "commander",
        available,
        4,
        Random(42),
    )

    assert chosen == 3
    assert set(deck.quantities()) == {
        "miller",
        "surveiller",
        "fodder-maker",
    }
    assert available == {"unrelated"}


def test_catalog_name_cache_is_bounded_and_canonical():
    from mtg_random_commander.synergy import _canonical_names, _matching_name

    catalog = frozenset({"Time Lord", "Artifact", "Forest"})
    _canonical_names.cache_clear()

    assert _matching_name(catalog, "time lord") == "Time Lord"
    assert _matching_name(catalog, "TIME LORD") == "Time Lord"
    assert _matching_name(catalog, "unknown") is None
    assert _canonical_names.cache_info().misses == 1


# M12: directional expansion adds breadth, not new deck sampling weights.
def test_m12_important_matter_and_trigger_tags_find_support():
    from mtg_random_commander.synergy import recognizes_synergy_tag

    db = FakeDB()
    db.tags.update({
        "attacking-matters-self": {"attacker"},
        "gives-haste": {"haste-enabler"},
        "extra-combat-phase": {"extra-combat"},
        "trigger-doubler": {"doubler"},
        "titan-trigger": {"titan"},
        "leaves-battlefield-trigger": {"death-value"},
        "mana-value-matters": {"mana-value-payoff"},
        "synergy-cascade": {"cascade-card"},
        "x-cost-matters": {"x-payoff"},
        "mana-increaser": {"extra-mana"},
    })
    for tag, expected in (
        ("attacking-matters-self", {"attacker", "haste-enabler", "extra-combat"}),
        ("trigger-doubler", {"doubler", "titan", "death-value"}),
        ("mana-value-matters", {"mana-value-payoff", "cascade-card"}),
        ("x-cost-matters", {"x-payoff", "extra-mana"}),
    ):
        assert recognizes_synergy_tag(tag)
        assert expected <= parse_synergy_tag(db, tag).pool


def test_m12_repeatable_enablers_link_to_actual_payoffs():
    db = FakeDB()
    db.tags.update({
        "repeatable-lifegain": {"lifegain-source"},
        "lifegain-matters": {"lifegain-payoff"},
        "repeatable-creature-tokens": {"token-source"},
        "creature-count-matters": {"swarm-payoff"},
        "your-sacrifice-matters": {"sac-payoff"},
        "repeatable-pp-counters": {"counters-source"},
        "counters-matter": {"counters-payoff"},
    })
    assert {"lifegain-source", "lifegain-payoff"} <= parse_synergy_tag(
        db, "repeatable-lifegain"
    ).pool
    assert {"token-source", "swarm-payoff", "sac-payoff"} <= parse_synergy_tag(
        db, "repeatable-creature-tokens"
    ).pool
    assert {"counters-source", "counters-payoff"} <= parse_synergy_tag(
        db, "repeatable-pp-counters"
    ).pool


def test_m12_keyword_support_only_recognizes_curated_keywords():
    from mtg_random_commander.synergy import recognizes_synergy_tag

    db = FakeDB()
    db.tags.update({
        "gains-flying": {"flier"},
        "gives-flying": {"flying-granter"},
        "synergy-flying": {"flying-payoff"},
        "gives-escape": {"escape-granter"},
        "mill-self": {"miller"},
    })
    assert {"flier", "flying-payoff"} <= parse_synergy_tag(
        db, "gains-flying"
    ).pool
    assert {"flying-granter", "flying-payoff"} <= parse_synergy_tag(
        db, "gives-flying"
    ).pool
    assert {"escape-granter", "miller"} <= parse_synergy_tag(
        db, "gives-escape"
    ).pool
    for unsupported in ("gains-nothing", "gives-nothing", "gains-soulshift"):
        assert not recognizes_synergy_tag(unsupported)
        assert parse_synergy_tag(db, unsupported) is None


def test_m12_flicker_targets_filter_to_relevant_type_and_trigger():
    db = FakeDB()
    db.tags.update({
        "flicker-creature": {"commander"},
        "titan-trigger": {"etb-creature", "etb-artifact"},
        "flicker-artifact": {"commander2"},
    })
    db.type_members["Creature"].add("etb-creature")
    db.type_members["Artifact"].add("etb-artifact")
    assert {"commander", "etb-creature"} <= parse_synergy_tag(
        db, "flicker-creature"
    ).pool
    assert "etb-artifact" not in parse_synergy_tag(db, "flicker-creature").pool
    assert {"commander2", "etb-artifact"} <= parse_synergy_tag(
        db, "flicker-artifact"
    ).pool
    assert "etb-creature" not in parse_synergy_tag(db, "flicker-artifact").pool


def test_m12_animate_and_sneak_explicit_target_types():
    db = FakeDB()
    db.tags.update({
        "animate-artifact": {"animator"},
        "sneak-creature": {"sneaker"},
    })
    assert {"animator", "artifact-card"} <= parse_synergy_tag(
        db, "animate-artifact"
    ).pool
    assert "desert-land" not in parse_synergy_tag(db, "animate-artifact").pool
    assert {"sneaker", "random-creature"} <= parse_synergy_tag(
        db, "sneak-creature"
    ).pool


def test_m12_missing_optional_tags_are_safe_and_mode_stays_independent():
    class StrictDB(FakeDB):
        def by_tag(self, slug, *, include_descendants=True):
            if slug not in self.tags:
                raise LookupError(slug)
            return super().by_tag(slug, include_descendants=include_descendants)

    db = StrictDB(["repeatable-creature-tokens", "lifegain-matters"])
    db.tags.update({
        "repeatable-creature-tokens": {"tokens"},
        "lifegain-matters": {"lifegain"},
    })
    packages = get_synergy_packages(db, "cmd")
    assert len(packages) == 2
    assert {package.source_tag for package in packages} == {
        "repeatable-creature-tokens", "lifegain-matters"
    }
    deck = Deck(commanders=("cmd",))
    assert fill_synergy(
        db, deck, "cmd", {"tokens", "lifegain"}, 2, Random(10),
        packages=packages,
    ) == 2


def test_m12_no_blanket_descriptive_tag_fallback():
    from mtg_random_commander.synergy import recognizes_synergy_tag
    for slug in (
        "activated-ability", "triggered-ability", "alliteration",
        "repeatable-crime", "gives-random-new-mechanic", "animate-self",
        "sneak-from-library", "flicker-self", "tutor-to-hand",
    ):
        assert not recognizes_synergy_tag(slug)


def test_m12_descend_detected_from_commander_oracle_text_without_tag():
    from types import SimpleNamespace

    class DescendDB(FakeDB):
        def __getitem__(self, cid):
            return SimpleNamespace(faces=(SimpleNamespace(
                oracle_text=(
                    "At the beginning of your end step, if you descended "
                    "this turn, create a 1/1 black Fungus creature token."
                ),
            ),))

    db = DescendDB()
    db.tags.update({
        "mill-self": {"self-miller"},
        "free-sacrifice-outlet": {"sacrifice-outlet"},
    })
    packages = get_synergy_packages(db, "cmd")
    assert len(packages) == 1
    assert packages[0].source_tag == "mechanic:descend"
    assert packages[0].pool == {"self-miller", "sacrifice-outlet"}


def test_m12_descend_not_inferred_from_unrelated_text():
    from types import SimpleNamespace

    class TextDB(FakeDB):
        def __getitem__(self, cid):
            return SimpleNamespace(faces=(SimpleNamespace(
                oracle_text="Whenever a creature enters the battlefield, draw a card."
            ),))

    db = TextDB()
    db.tags["mill-self"] = {"miller"}
    assert get_synergy_packages(db, "cmd") == ()


def test_m12_direct_descend_tag_does_not_duplicate_text_package():
    from types import SimpleNamespace

    class TaggedDescendDB(FakeDB):
        def __getitem__(self, cid):
            return SimpleNamespace(faces=(SimpleNamespace(
                oracle_text="Whenever you descend, create a Fungus.",
            ),))

    db = TaggedDescendDB(["descend"])
    db.tags.update({"descend": {"commander"}, "mill-self": {"miller"}})
    packages = get_synergy_packages(db, "cmd")
    assert len(packages) == 1
    assert packages[0].source_tag == "descend"
    assert {"commander", "miller"} <= packages[0].pool
