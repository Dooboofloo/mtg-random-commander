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

IRREGULAR_PLURALS = {
    "abilities": "ability",
    "bodies": "body",
}

def singularize_slug(slug: str) -> str:
    if slug in IRREGULAR_PLURALS:
        return IRREGULAR_PLURALS[slug]

    if slug.endswith("s"):
        return slug[:-1]

    return slug

def slug_to_name(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))

def subtype_pool_from_slug(db: CardDatabase, slug: str) -> set[str]:
    """
    Converts slug like

    elf -> Elf
    human-werewolf -> Human or Werewolf
    """

    if slug.startswith("non-"):
        return set()

    pool = set()

    for part in slug.split("-"):
        pool |= concept_pool_from_slug(db, part)

    return pool

def concept_pool_from_slug(db: CardDatabase, slug: str) -> set[str]:
    
    if slug.startswith("non-"):
        return set()
    
    candidates = [slug]

    singular = singularize_slug(slug)
    if singular != slug:
        candidates.append(singular)
    
    pool = set()

    for candidate in candidates:
        name = slug_to_name(candidate)

        # Type
        pool |= db.cards_by_type.get(name, set())

        # Supertype
        pool |= db.cards_by_supertype.get(name, set())

        # Subtype
        pool |= db.cards_by_subtype.get(name, set())

        # Keywords
        pool |= db.cards_by_keywords.get(name, set())

        # TODO: More concepts. Hardcode concepts like "outlaw"?
    
    return pool

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

def update_parsed_tags(db: CardDatabase):
    from pathlib import Path

    tags = Path('./synergy/commander_tags.txt').read_text().split('\n')

    unparsed_tags = set()
    parsed_tags = set()

    for tag in tags:
        package = parse_synergy_tag(db, tag)
        
        if package is None:
            unparsed_tags.add(tag)
            continue

        parsed_tags.add(f"{package.source_tag} {len(package.pool)}")
    
    unparsed_tags = sorted(unparsed_tags)
    parsed_tags = sorted(parsed_tags)

    Path('./out/unparsed_tags.txt').write_text('\n'.join(unparsed_tags))
    Path('./out/parsed_tags.txt').write_text('\n'.join(parsed_tags))

if __name__ == '__main__':
    from scryfall import fetch_bulk_data
    
    updated = fetch_bulk_data()

    db = CardDatabase()
    db.load()

    artifact_pool = concept_pool_from_slug(db, 'artifact')

    print(len(artifact_pool))