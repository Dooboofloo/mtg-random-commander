"""Commander-tag synergy pools and their nonland selection."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import TYPE_CHECKING

from .models import Deck

if TYPE_CHECKING:
    from mtg_carddb import CardDatabase


# These concepts are useful as direct tags, but should not
# automatically select every card sharing the broad property.
BROAD_CONCEPTS = frozenset({
    "creature",
    "permanent",
    "spell",
})

CONCEPT_SUBTYPES = {
    "outlaw": (
        "Assassin", "Mercenary", "Pirate", "Rogue", "Warlock",
    ),
    "party": (
        "Cleric", "Rogue", "Warrior", "Wizard",
    ),
    "lupine": ("Wolf", "Werewolf"),
    "multi-sea-monster": (
        "Kraken", "Leviathan", "Octopus", "Serpent",
    ),
}


@dataclass(frozen=True)
class SynergyPackage:
    source_tag: str
    mode: str
    pool: frozenset[str]


def _singular(value: str) -> str:
    if value.endswith("wolves"):
        return value[:-6] + "wolf"
    if value.endswith("ies"):
        return value[:-3] + "y"
    if value.endswith("s") and not value.endswith("ss"):
        return value[:-1]
    return value


def _matching_name(
    catalog: frozenset[str],
    name: str,
) -> str | None:
    normalized = name.casefold()
    return next(
        (
            item for item in catalog
            if item.casefold() == normalized
        ),
        None,
    )


def _simple_concept_pool(
    db: CardDatabase,
    concept: str,
) -> set[str]:
    normalized = concept.casefold().strip("-")

    if normalized.startswith("non-"):
        return set()

    normalized = _singular(normalized)

    if normalized in BROAD_CONCEPTS:
        return set()

    name = normalized.replace("-", " ")

    subtype = _matching_name(db.subtypes, name)
    if subtype is not None:
        return set(db.by_subtype(subtype))

    type_name = _matching_name(db.types, name)
    if type_name is not None:
        return set(db.by_type(type_name))

    supertype = _matching_name(db.supertypes, name)
    if supertype is not None:
        return set(db.by_supertype(supertype))

    keyword = _matching_name(db.keywords, name)
    if keyword is not None:
        return set(db.by_keyword(keyword))

    return set()


def _concept_pool(
    db: CardDatabase,
    concept: str,
) -> set[str]:
    if concept == "historic":
        return (
            set(db.by_type("Artifact"))
            | set(db.by_supertype("Legendary"))
            | set(db.by_subtype("Saga"))
        )

    if concept in CONCEPT_SUBTYPES:
        result: set[str] = set()

        for subtype in CONCEPT_SUBTYPES[concept]:
            result.update(db.by_subtype(subtype))

        return result

    return _simple_concept_pool(db, concept)


def _typal_pool(
    db: CardDatabase,
    concept: str,
) -> set[str]:
    """An exact multiword subtype or a union of named subtypes."""

    if concept.startswith("non-"):
        return set()

    full_name = _matching_name(
        db.subtypes,
        concept.replace("-", " "),
    )

    if full_name is not None:
        return set(db.by_subtype(full_name))

    result: set[str] = set()

    for part in concept.split("-"):
        name = _matching_name(
            db.subtypes,
            _singular(part),
        )

        if name is not None:
            result.update(db.by_subtype(name))

    return result


def parse_synergy_tag(
    db: CardDatabase,
    slug: str,
) -> SynergyPackage | None:
    """Translate a recognized commander tag into a candidate pool."""

    # This tag describes cards that reference multiple creature
    # types, not cards supporting the commander's specific types.
    if slug == "typal-coupling":
        return None

    mode: str
    concept: str

    if slug.startswith("typal-"):
        mode = "typal"
        concept = slug.removeprefix("typal-")

    elif slug.startswith("affinity-for-"):
        mode = "affinity"
        concept = slug.removeprefix("affinity-for-")

    elif slug.startswith("synergy-"):
        mode = "synergy"
        concept = slug.removeprefix("synergy-")

    elif slug.endswith("fall") and len(slug) > len("fall"):
        mode = "fall"
        concept = slug[:-len("fall")].rstrip("-")

    else:
        return None

    if not concept:
        return None

    # Directly tagged payoffs remain relevant even for broad
    # concepts that should not expand into all matching cards.
    pool = set(
        db.by_tag(slug, include_descendants=False)
    )

    if mode == "typal":
        pool.update(_typal_pool(db, concept))
    else:
        pool.update(_concept_pool(db, concept))

    if not pool:
        return None

    return SynergyPackage(
        source_tag=slug,
        mode=mode,
        pool=frozenset(pool),
    )


def get_synergy_packages(
    db: CardDatabase,
    commander_id: str,
) -> tuple[SynergyPackage, ...]:
    """Parse the commander's direct Oracle Tags."""

    packages = []

    for tagging in db.taggings_for(commander_id):
        parsed = parse_synergy_tag(
            db,
            tagging.tag_slug,
        )

        if parsed is not None:
            packages.append(parsed)

    return tuple(packages)


def fill_synergy(
    db: CardDatabase,
    deck: Deck,
    commander_id: str,
    available: set[str],
    target: int,
    rng: Random,
) -> int:
    """Fill synergy slots after functional packages."""

    if target <= 0:
        return 0

    packages = get_synergy_packages(
        db,
        commander_id,
    )

    pool: set[str] = set()

    for package in packages:
        pool.update(package.pool)

    # The caller has already removed illegal cards, land-faced
    # cards, and cards selected by functional packages.
    choices = sorted(available & pool)

    chosen = rng.sample(
        choices,
        min(target, len(choices)),
    )

    for cid in chosen:
        deck.add(
            cid,
            slot="nonland",
            role="synergy",
        )

    available.difference_update(chosen)

    return len(chosen)
