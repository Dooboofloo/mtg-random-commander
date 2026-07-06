from __future__ import annotations

from dataclasses import dataclass
import re

from carddb import CardDatabase

@dataclass(frozen=True)
class SynergyPackage:
    source_tag: str
    mode: str
    pool: set[str]

### Public methods

def get_synergy_packages(db: CardDatabase, card_id: str) -> list[SynergyPackage]:
    packages = []

    for tag_id in db.tags_by_card.get(card_id, set()):
        tag = db.tag_by_id[tag_id]
        package = parse_synergy_tag(db, tag)

        if package is not None:
            packages.append(package)

    return packages

def get_synergy_pool(db: CardDatabase, card_id: str) -> set[str]:
    pool = set()

    for package in get_synergy_packages(db, card_id):
        pool |= package.pool

    return pool

def parse_synergy_tag(db: CardDatabase, tag: str) -> SynergyPackage | None:
    for pattern, parser in PARSERS:
        match = pattern.match(tag)
        if match:
            return parser(db, tag, *match.groups())

    return None

### Helpers

def subtype_pool_from_slug(db: CardDatabase, slug: str) -> set[str]:
    """
    Converts slug like

    elf -> Elf
    human-werewolf -> Human + Werewolf
    """

    if slug.startswith("non-"):
        return set()
    
    parts = [part.capitalize() for part in slug.split("-")]

    if not parts:
        return set()

    pools = [
        set(db.cards_by_subtype.get(part, set()))
        for part in parts
    ]

    if not pools or any(not pool for pool in pools):
        return set()

    # For Human Werewolf, Eldrazi Scion, Mutant Ninja Turtle, etc.
    return set.union(*pools)

### Individual Parsers

def parse_typal(db: CardDatabase, source_tag: str, creature_type_slug: str) -> SynergyPackage:
    pool = set()

    # Include cards with the relevant subtype
    pool |= subtype_pool_from_slug(db, creature_type_slug)

    # Include cards that share the same typal tag
    pool |= db.get_indexed_cards_for_tag(source_tag, expand_children=False)

    return SynergyPackage(
        source_tag=source_tag,
        mode="typal",
        pool=pool,
    )

### Parser Registry

PARSERS = [
    (re.compile(r"^typal-(.+)$"), parse_typal),
]

### CLI Testing

if __name__ == '__main__':
    from scryfall import fetch_bulk_data
    
    updated = fetch_bulk_data()

    db = CardDatabase()
    db.load(rebuild_cache=updated)

    goblin_subtype_pool = subtype_pool_from_slug(db, "goblin")
    orc_subtype_pool = subtype_pool_from_slug(db, "orc")
    typal_pool = db.get_indexed_cards_for_tag("typal-goblin-orc")

    total_pool = goblin_subtype_pool | orc_subtype_pool | typal_pool

    orcs_and_goblins = parse_synergy_tag(db, "typal-goblin-orc").pool

    # print(orcs_and_goblins == (total_pool))

    print(len(total_pool), len(orcs_and_goblins))