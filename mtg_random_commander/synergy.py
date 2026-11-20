"""Commander-tag synergy pools and nonland selection.

Payoff-to-enabler mappings deliberately use Oracle Tag slugs, not card names.
Tags that describe a card without indicating useful deckbuilding support remain
unsupported rather than being interpreted speculatively.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
from random import Random
from typing import TYPE_CHECKING

from .models import Deck
from .synergy_expansion import (
    EXPANDED_ENABLER_TAGS,
    TARGET_ABILITY_EXPRESSIONS,
    TARGET_ABILITY_SUPPORT,
    DESCEND_ENABLERS,
)
from .synergy_m13 import (
    M13_ENABLER_TAGS,
    M13_MANA_VALUE_RANGES,
    M13_CRIME_PAYOFF_PATTERN,
    M13_CRIME_ENABLERS,
)
from .synergy_resources import (
    RESOURCE_ENABLER_TAGS,
    RESOURCE_TYPE_FILTERS,
)

if TYPE_CHECKING:
    from mtg_carddb import CardDatabase


SKIPPED_SYNERGY_TAGS = frozenset({
    "typal-coupling",
    "typal-coupling-distinct",
})

# These cannot safely expand to every card with this type or property.
BROAD_CONCEPTS = frozenset({"creature", "permanent", "spell", "token"})

CONCEPT_SUBTYPES = {
    "outlaw": ("Assassin", "Mercenary", "Pirate", "Rogue", "Warlock"),
    "party": ("Cleric", "Rogue", "Warrior", "Wizard"),
    "lupine": ("Wolf", "Werewolf"),
    "multi-sea-monster": ("Kraken", "Leviathan", "Octopus", "Serpent"),
    "neo-solo-attack": ("Samurai", "Warrior"),
}

# Unlike raw type/subtype queries, these select cards with abilities that
# create the resource. Avoid the mostly non-playable Token cards themselves.
CONCEPT_ENABLER_TAGS = {
    "token": (
        "repeatable-token-generator", "repeatable-creature-tokens",
        "repeatable-artifact-tokens", "repeatable-noncreature-tokens",
    ),
    "token-creature": ("repeatable-creature-tokens",),
    "treasure": ("repeatable-treasures",),
    "clue": ("repeatable-clues",),
    "food": ("repeatable-food",),
    "blood": ("repeatable-blood",),
}

# Directional links: a commander with the payoff wants the enabler.
# Deliberately curated. Unknown *-matters tags are NOT automatically parsed.
PAYOFF_ENABLER_TAGS = {
    "attacking-matters": (
        "extra-combat-phase", "gives-haste", "gives-myriad",
        "multiple-bodies",
    ),
    "attacking-opponents-matters": (
        "extra-combat-phase", "gives-myriad", "multiple-bodies",
    ),
    "lifegain-matters": (
        "lifegain", "repeatable-lifegain", "soul-warden-ability",
    ),
    "pridemate": (
        "lifegain", "repeatable-lifegain", "soul-warden-ability",
    ),
    "draw-matters": (
        "pure-draw", "repeatable-pure-draw", "draw-engine", "cantrip",
    ),
    "second-draw-matters": (
        "pure-draw", "repeatable-pure-draw", "cantrip", "loot",
    ),
    "third-draw-matters": (
        "pure-draw", "repeatable-pure-draw", "cantrip", "loot",
    ),
    "self-discard-matters": (
        "discard-outlet", "free-discard-outlet", "repeatable-loot",
        "loot", "rummage",
    ),
    "your-sacrifice-matters": (
        "free-sacrifice-outlet", "repeatable-sacrifice-outlet",
        "sacrifice-outlet-creature", "sacrifice-outlet-artifact",
        "sacrifice-outlet-token", "repeatable-creature-tokens",
    ),
    "opponent-sacrifice-matters": (
        "opponent-sacrifices", "mutual-sacrifice",
    ),
    "creature-count-matters": (
        "repeatable-creature-tokens", "multiple-bodies",
        "repeatable-token-generator",
    ),
    "artifact-count-matters": (
        "repeatable-artifact-tokens", "repeatable-treasures",
        "repeatable-clues", "repeatable-food",
    ),
    "life-loss-matters": (
        "opponent-loses-life", "blood-artist-ability", "drain-life",
    ),
    "self-life-loss-matters": (
        "life-payment", "burn-self",
    ),
    "opponent-discard-matters": (
        "discard", "discard-symmetrical", "hand-disruption",
    ),
    "second-spell-matters": (
        "cantrip", "cost-reducer", "refund", "mini-refund",
    ),
    "third-spell-matters": (
        "cantrip", "cost-reducer", "refund", "mini-refund",
    ),
    "fourth-spell-matters": (
        "cantrip", "cost-reducer", "refund", "mini-refund",
    ),
    "storm-count-matters": (
        "cantrip", "cost-reducer", "ritual-untap", "refund",
    ),
    "hand-size-matters": (
        "draw-engine", "repeatable-pure-draw", "hand-size-increase",
    ),
    "land-count-matters": (
        "land-ramp", "multi-land-ramp", "extra-land", "play-additional-land",
    ),
    "lands-matter": (
        "land-ramp", "multi-land-ramp", "extra-land", "play-additional-land",
    ),
    "cards-in-graveyard-matter": (
        "mill-self", "repeatable-surveil", "mulch", "repeatable-mulch",
    ),
    "card-types-in-graveyard-matter": (
        "mill-self", "repeatable-surveil", "mulch", "repeatable-mulch",
    ),
    "lands-in-graveyard-matter": (
        "mill-self", "graveyard-fuel-land", "mulch",
    ),
    "pp-counters-matter": (
        "gives-pp-counters", "gives-pp-counters-to-all",
        "repeatable-pp-counters", "repeatable-proliferate",
    ),
    "counters-matter": (
        "counter-doubler", "counter-increaser", "repeatable-proliferate",
        "gives-pp-counters", "repeatable-pp-counters",
    ),
    "mm-counters-matter": (
        "gives-mm-counters", "counter-fuel-other",
    ),
    "coin-flips-matter": (
        "coin-flip", "krarks-other-thumb-effect",
    ),
    "reanimate-matters": (
        "reanimate", "reanimate-creature", "mass-reanimation",
    ),
}


TARGET_FAMILY_PREFIXES = (
    "tutor-",
    "copy-",
    "reanimate-",
    "regrowth-",
    "impulse-",
    "cost-reducer-",
)

# These tags describe an action, destination, or unrestricted class,
# rather than a specific kind of card worth adding to the deck.
TARGET_UNSUPPORTED_TAGS = frozenset({
    "tutor-card",
    "tutor-copy",
    "tutor-mv",
    "tutor-land-to-battlefield",
    "copy-ability",
    "copy-self",
    "copy-spell",
    "copy-from-graveyard",
    "copy-permanent",
    "copy-permanent-spell",
    "copy-noncreature",
    "copy-nonland",
    "reanimate-self",
    "reanimate-copy",
    "reanimate-cast",
    "reanimate-face-down",
    "reanimate-from-any",
    "reanimate-from-opponent",
    "regrowth-self",
    "regrowth-any",
    "impulse-cast",
    "impulse-onto-battlefield",
    "impulse-to-top",
    "impulse-pw-tyvar",
    "impulse-multicolor",
    "impulse-nonland",
    "cost-reducer",
    "cost-reducer-activated-ability",
    "cost-reducer-colored-mana",
    "cost-reducer-equip-ability",
    "cost-reducer-noncreature",
})

TARGET_UNSUPPORTED_PREFIXES = (
    "tutor-to-",
    "tutor-from-",
    "reanimate-from-",
)

TARGET_BROAD_CONCEPTS = frozenset({
    "card",
    "permanent",
    "nonland",
    "noncreature",
    "nonartifact",
    "nonbasic",
})

# Some target relationships need ability tags rather than card types.
TARGET_TAG_ENABLERS = {
    "tutor-interaction": ("removal", "counterspell"),
    "copy-token": CONCEPT_ENABLER_TAGS["token"],
}


def _target_expression(slug: str) -> tuple[str, str] | None:
    """Identify a supported target family and its target expression."""
    if slug == "reanimate":
        return "reanimate", "creature"

    if (
        slug in TARGET_UNSUPPORTED_TAGS
        or slug.startswith(TARGET_UNSUPPORTED_PREFIXES)
    ):
        return None

    for prefix in TARGET_FAMILY_PREFIXES:
        if slug.startswith(prefix):
            expression = slug[len(prefix):]

            if expression and expression not in TARGET_BROAD_CONCEPTS:
                return prefix[:-1], expression

            return None

    return None


@dataclass(frozen=True)
class SynergyPackage:
    source_tag: str
    mode: str
    pool: frozenset[str]


def recognizes_synergy_tag(slug: str) -> bool:
    """True when a tag belongs to a supported parser family."""
    if slug in SKIPPED_SYNERGY_TAGS:
        return False

    return (
        slug in PAYOFF_ENABLER_TAGS
        or slug in EXPANDED_ENABLER_TAGS
        or slug in M13_ENABLER_TAGS
        or slug in TARGET_ABILITY_EXPRESSIONS
        or slug in M13_MANA_VALUE_RANGES
        or slug in RESOURCE_ENABLER_TAGS
        or slug in TARGET_TAG_ENABLERS
        or _target_expression(slug) is not None
        or slug.startswith(("typal-", "affinity-for-", "synergy-"))
        or (slug.endswith("fall") and len(slug) > 4)
    )


def _singular(value: str) -> str:
    if value.endswith("wolves"):
        return value[:-6] + "wolf"
    if value.endswith("ies"):
        return value[:-3] + "y"
    if value.endswith("s") and not value.endswith("ss"):
        return value[:-1]
    return value


@lru_cache(maxsize=16)
def _canonical_names(catalog: frozenset[str]) -> dict[str, str]:
    """Small, bounded, database-independent cache of catalog spellings."""
    names: dict[str, str] = {}
    for item in sorted(catalog, key=lambda item: (item.casefold(), item)):
        names.setdefault(item.casefold(), item)
    return names


def _matching_name(catalog: frozenset[str], name: str) -> str | None:
    return _canonical_names(catalog).get(name.casefold())


def _tag_pool(db: CardDatabase, slugs: tuple[str, ...]) -> set[str]:
    result: set[str] = set()
    # Optional enabler tags need not occur in every database snapshot.
    known = db.tag_slugs
    for slug in slugs:
        if slug in known:
            result.update(db.by_tag(slug, include_descendants=False))
    return result


def _simple_concept_pool(db: CardDatabase, concept: str) -> set[str]:
    normalized = concept.casefold().strip("-")
    if normalized.startswith("non-"):
        return set()
    if normalized in BROAD_CONCEPTS:
        return set()

    # Preserve exact names such as Plains before attempting plural removal.
    for word in (normalized, _singular(normalized)):
        name = word.replace("-", " ")
        subtype = _matching_name(db.subtypes, name)
        if subtype is not None:
            return set(db.by_subtype(subtype))
        type_name = _matching_name(db.types, name)
        if type_name is not None and type_name != "Token":
            return set(db.by_type(type_name))
        supertype = _matching_name(db.supertypes, name)
        if supertype is not None:
            return set(db.by_supertype(supertype))
        keyword = _matching_name(db.keywords, name)
        if keyword is not None:
            return set(db.by_keyword(keyword))
    return set()


def _concept_pool(db: CardDatabase, concept: str) -> set[str]:
    if concept == "historic":
        return (
            set(db.by_type("Artifact"))
            | set(db.by_supertype("Legendary"))
            | set(db.by_subtype("Saga"))
        )
    if concept == "legend":
        return set(db.by_supertype("Legendary"))
    if concept in CONCEPT_SUBTYPES:
        result: set[str] = set()
        for subtype in CONCEPT_SUBTYPES[concept]:
            result.update(db.by_subtype(subtype))
        return result
    return _simple_concept_pool(db, concept)


def _typal_pool(db: CardDatabase, concept: str) -> set[str]:
    if concept.startswith("non-"):
        return set()
    if concept in CONCEPT_SUBTYPES:
        return _concept_pool(db, concept)

    full_name = _matching_name(db.subtypes, concept.replace("-", " "))
    if full_name is not None:
        return set(db.by_subtype(full_name))

    result: set[str] = set()
    for part in concept.split("-"):
        name = _matching_name(db.subtypes, _singular(part))
        if name is not None:
            result.update(db.by_subtype(name))
    return result


def _target_pool(
    db: CardDatabase,
    expression: str,
) -> set[str] | None:
    """Resolve card-type, subtype, keyword, and supertype constraints.

    Positive constraints intersect, except instant-sorcery, which is
    a union. Negative qualifiers subtract matching cards.

    Return None for unsupported expressions, and an empty set for
    valid expressions that currently match no cards.
    """
    if expression in TARGET_BROAD_CONCEPTS:
        return None

    atoms = expression.split("-")
    positive: list[set[str]] = []
    excluded: list[set[str]] = []
    i = 0

    while i < len(atoms):
        atom = atoms[i]

        # Instant-or-sorcery is a union, not an intersection.
        if atoms[i:i + 2] == ["instant", "sorcery"]:
            positive.append(
                set(db.by_type("Instant"))
                | set(db.by_type("Sorcery"))
            )
            i += 2
            continue

        # Negative qualifiers require at least one positive
        # constraint elsewhere in the expression.
        if atom in {
            "noncreature", "nonland", "nonartifact", "nonbasic",
        }:
            if atom == "nonbasic":
                excluded.append(set(db.by_supertype("Basic")))
            else:
                excluded.append(
                    set(db.by_type(atom[3:].capitalize()))
                )

            i += 1
            continue

        # "land-any" is equivalent to "land".
        if atom == "any" and "land" in atoms[:i]:
            i += 1
            continue

        if atom == "historic":
            positive.append(_concept_pool(db, "historic"))
            i += 1
            continue

        # Prefer the longest match. This handles multiword
        # subtypes such as Time Lord without splitting them.
        matched = False

        for length in range(
            min(4, len(atoms) - i), 0, -1
        ):
            name = " ".join(atoms[i:i + length])

            catalogs = (
                (db.types, db.by_type),
                (db.supertypes, db.by_supertype),
                (db.subtypes, db.by_subtype),
                (db.keywords, db.by_keyword),
            )

            for catalog, query in catalogs:
                canonical = _matching_name(catalog, name)

                if canonical is None:
                    continue

                # Don't select physical token representations
                # instead of cards capable of creating tokens.
                if canonical == "Token":
                    return None

                positive.append(set(query(canonical)))
                i += length
                matched = True
                break

            if matched:
                break

        if not matched:
            return None

    if not positive:
        return None

    pool = set.intersection(*positive)

    for excluded_pool in excluded:
        pool.difference_update(excluded_pool)

    return pool


def parse_synergy_tag(db: CardDatabase, slug: str) -> SynergyPackage | None:
    """Translate a recognized commander payoff/theme into a card pool."""
    if not recognizes_synergy_tag(slug):
        return None

    if slug in PAYOFF_ENABLER_TAGS:
        mode = "matters"
        inferred = _tag_pool(db, PAYOFF_ENABLER_TAGS[slug])

    elif slug in TARGET_TAG_ENABLERS:
        mode = "target"
        inferred = _tag_pool(db, TARGET_TAG_ENABLERS[slug])

    elif slug in RESOURCE_ENABLER_TAGS:
        mode = "resource"
        inferred = _tag_pool(db, RESOURCE_ENABLER_TAGS[slug])

        # Some untappers specifically affect one kind
        # of permanent. Avoid unrelated mana producers.
        required_type = RESOURCE_TYPE_FILTERS.get(slug)

        if required_type is not None:
            inferred.intersection_update(
                db.by_type(required_type)
            )

    elif slug in EXPANDED_ENABLER_TAGS:
        mode = "expanded"
        inferred = _tag_pool(db, EXPANDED_ENABLER_TAGS[slug])
        # Extend the preexisting generic concept interpretation rather than
        # silently replacing it for previously recognized synergy tags.
        if slug.startswith("synergy-"):
            concept = slug.removeprefix("synergy-")
            inferred.update(_concept_pool(db, concept))
            inferred.update(_tag_pool(db, CONCEPT_ENABLER_TAGS.get(concept, ())))

    elif slug in M13_MANA_VALUE_RANGES:
        # CardDB's indexed interval query selects genuine low/high-MV spells
        # rather than merely collecting other mana-value payoffs.  This runs
        # only for the explicit three slugs, not arbitrary *-matters labels.
        mode = "mana-value"
        low, high = M13_MANA_VALUE_RANGES[slug]
        inferred = set(db.mana_value_between(low, high)) - set(db.by_type("Land"))
        inferred.update(_tag_pool(db, M13_ENABLER_TAGS.get(slug, ())))

    elif slug in M13_ENABLER_TAGS:
        mode = "expanded"
        inferred = _tag_pool(db, M13_ENABLER_TAGS[slug])

    elif slug in TARGET_ABILITY_EXPRESSIONS:
        mode = slug.partition("-")[0]
        expression = TARGET_ABILITY_EXPRESSIONS[slug]
        if expression in {"nonland", "permanent"}:
            # Those are intentionally too broad for a general type query.
            # Use only known ETB or attack payoffs, with land filtering.
            inferred = _tag_pool(db, TARGET_ABILITY_SUPPORT[mode])
            if expression == "nonland":
                inferred.difference_update(db.by_type("Land"))
        else:
            targets = _target_pool(db, expression)
            if targets is None:
                return None
            if mode == "flicker":
                # Prefer relevant ETB/leave triggers over arbitrary creatures
                # or artifacts; the direct tag remains available regardless.
                inferred = targets & _tag_pool(db, TARGET_ABILITY_SUPPORT[mode])
            else:
                # A sneak/animate enabler can use ordinary cards of the
                # specified type even if they lack Oracle Tag relationships.
                inferred = targets

    elif (target := _target_expression(slug)) is not None:
        mode, expression = target
        inferred = _target_pool(db, expression)

        if inferred is None:
            return None

    else:
        if slug.startswith("typal-"):
            mode, concept = "typal", slug.removeprefix("typal-")
        elif slug.startswith("affinity-for-"):
            mode, concept = "affinity", slug.removeprefix("affinity-for-")
        elif slug.startswith("synergy-"):
            mode, concept = "synergy", slug.removeprefix("synergy-")
        else:
            mode, concept = "fall", slug[:-4].rstrip("-")

        if not concept:
            return None

        if mode == "typal":
            inferred = _typal_pool(db, concept)
        else:
            inferred = _concept_pool(db, concept)

        inferred.update(_tag_pool(db, CONCEPT_ENABLER_TAGS.get(concept, ())))

    # Keep direct payoffs in the pool as before, but never confuse them with
    # the newly inferred enabler cards in coverage reporting.
    pool = set(db.by_tag(slug, include_descendants=False)) | inferred
    if not pool:
        return None
    return SynergyPackage(slug, mode, frozenset(pool))


def get_synergy_packages(
    db: CardDatabase, commander_id: str
) -> tuple[SynergyPackage, ...]:
    """Parse the commander's direct Oracle Tags."""
    packages = []
    taggings = db.taggings_for(commander_id)
    for tagging in taggings:
        parsed = parse_synergy_tag(db, tagging.tag_slug)
        if parsed is not None:
            packages.append(parsed)

    # Scryfall's commander Tagger inventory does not currently expose a
    # `descend` archetype tag. This explicit mechanic check covers real
    # descend commanders without guessing at other rules text or card roles.
    if not any(tag.tag_slug == "descend" for tag in taggings) and hasattr(db, "__getitem__"):
        faces = getattr(db[commander_id], "faces", ())
        if any(
            re.search(r"\bdescend(?:s|ed|ing)?\b", getattr(face, "oracle_text", None) or "", re.I)
            for face in faces
        ):
            pool = _tag_pool(db, DESCEND_ENABLERS)
            if pool:
                packages.append(SynergyPackage(
                    "mechanic:descend", "mechanic", frozenset(pool)
                ))

    # "Commit a crime" payoff wording is absent from the current Tagger
    # commander tag inventory.  Only a real payoff clause creates the
    # synthetic package, not a generic repeatable-crime enabler.
    if hasattr(db, "__getitem__"):
        faces = getattr(db[commander_id], "faces", ())
        if any(
            re.search(M13_CRIME_PAYOFF_PATTERN, getattr(face, "oracle_text", None) or "", re.I)
            for face in faces
        ):
            pool = _tag_pool(db, M13_CRIME_ENABLERS)
            if pool:
                packages.append(SynergyPackage(
                    "mechanic:crime", "mechanic", frozenset(pool)
                ))

    return tuple(packages)



def fill_synergy(
    db: CardDatabase,
    deck: Deck,
    commander_id: str,
    available: set[str],
    target: int,
    rng: Random,
    *,
    packages: tuple[SynergyPackage, ...] | None = None,
) -> int:
    """Fill synergy slots with equal weight per commander theme."""
    if target <= 0:
        return 0

    if packages is None:
        packages = get_synergy_packages(db, commander_id)

    # Keep each theme independent rather than combining their
    # candidate pools. Functional-package cards have already
    # been removed from available.
    pools = [
        set(available & package.pool)
        for package in packages
    ]

    selected = 0

    while selected < target:
        active = [pool for pool in pools if pool]

        if not active:
            break

        # First choose a theme, then a card within that theme.
        pool = rng.choice(active)
        cid = rng.choice(sorted(pool))

        deck.add(
            cid,
            slot="nonland",
            role="synergy",
        )

        available.remove(cid)

        # A card can belong to multiple themes, but must
        # never be selected more than once.
        for candidate_pool in pools:
            candidate_pool.discard(cid)

        selected += 1

    return selected
