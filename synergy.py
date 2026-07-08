from __future__ import annotations

from collections.abc import Callable
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

OTHER_CONCEPTS = {
    "outlaw": ("subtype", "assassin-mercenary-pirate-rogue-warlock"),
    "party": ("subtype", "cleric-rogue-warrior-wizard"),
    "neo-solo-attack": ("subtype", "samurai-warrior"),
    "lupine": ("subtype", "wolf-werewolf"),
    "multi-sea-monster": ("subtype", "kraken-leviathan-octopus-serpent"),
    "permanent": ("type", "artifact-battle-creature-enchantment-land-planeswalker"),
    "historic": ("multiple", "artifact-legendary-saga"),
    "legend": ("supertype", "legendary")
}


"""
Below is a list of concepts too broad to include in certain searches.

Ex. "creaturefall" cares about creatures entering, but if we include creatures in the synergy pool,
there are 17720 hits. Compared to the list of applicable cards with just the tag (570), generic creatures
are over represented.
"""
BROAD_CONCEPTS = {
    "creature",
}

def concept_is_too_broad(slug: str) -> bool:
    return slug in BROAD_CONCEPTS or singularize_slug(slug) in BROAD_CONCEPTS

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
        pool |= db.cards_by_subtype.get(part.capitalize(), set())

    # Special groupings
    if slug in OTHER_CONCEPTS:
        concept_type, concept_tag = OTHER_CONCEPTS[slug]

        if concept_type == "subtype":
            pool |= subtype_pool_from_slug(db, concept_tag)

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

    # Other concepts
    if slug in OTHER_CONCEPTS:
        concept_type, concept_tag = OTHER_CONCEPTS[slug]

        match concept_type:
            case 'subtype':
                pool |= subtype_pool_from_slug(db, concept_tag)
            
            case "type":
                for part in concept_tag.split("-"):
                    pool |= db.cards_by_type.get(part.capitalize(), set())
            
            case "supertype":
                for part in concept_tag.split("-"):
                    pool |= db.cards_by_supertype.get(part.capitalize(), set())
            
            case "multiple":
                for part in concept_tag.split("-"):
                    pool |= concept_pool_from_slug(db, part)
    
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

def parse_direct(parser_type: str, excluded_types: tuple[str, ...] = ("Land",)) -> Callable[[CardDatabase, str, str], SynergyPackage]:
    def output(db: CardDatabase, source_tag: str, concept_slug: str):

        pool = set()

        # Include cards with relevant concept (unless concept is too broad)
        if not concept_is_too_broad(concept_slug):
            pool |= concept_pool_from_slug(db, concept_slug)

        # Include other cards that share the same tag
        tag_pool = db.get_indexed_cards_for_tag(source_tag, expand_children=True)

        pool |= tag_pool

        for excluded_type in excluded_types:
            pool -= db.cards_by_type[excluded_type] - tag_pool

        return SynergyPackage(
            source_tag=source_tag,
            mode=parser_type,
            pool=pool
        )
    
    return output

### Parser Registry

"""
TODO:

CORE:
synergy-*
*-matters

MISC:
x-cost-matters
karnstructs / metalcraft / improvise
tutors-by-name
trigger-doubler
untapper-*
reanimate / reanimate-*
regrowth / regrowth-*
impulse-*
copy-*

MAYBE:
animate-*
sneak / sneak-*
flicker-*
cost-reducer-*
"""

PARSERS = [
    (re.compile(r"^typal-(.+)$"), parse_typal),
    (re.compile(r"^affinity-for-(.+)$"), parse_direct("affinity")),
    (re.compile(r"^(.+)fall$"), parse_direct("blankfall"))
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

    print(f"Unparsed: {len(unparsed_tags)} / {len(tags)}")
    print(f"Parsed: {len(parsed_tags)} / {len(tags)}")

    Path('./synergy/unparsed_tags.txt').write_text('\n'.join(unparsed_tags))
    Path('./synergy/parsed_tags.txt').write_text('\n'.join(parsed_tags))

def check_against_scryfall_search(
    parser_pool: set[str],
    search_query: str,
) -> tuple[set[str], set[str]]:
    from scryfall import search_cards

    sf_cards = search_cards(search_query, debug_output=True)
    sf_set = {card["oracle_id"] for card in sf_cards}

    extra_local = parser_pool - sf_set
    missing_local = sf_set - parser_pool

    return extra_local, missing_local

def test_tag_against_scryfall(db: CardDatabase, tag: str, sf_search: str) -> None:

    print(f'Testing tag "{tag}" against scryfall search "{sf_search}"')

    package = parse_synergy_tag(db, tag)
    pool = package.pool

    query = f"f:commander -t:attraction -t:sticker -otag:draft-matters ({sf_search})"

    extra_local, missing_local = check_against_scryfall_search(pool, query)

    print()
    print("Local:", len(pool))
    print("Scryfall:", len(pool) - len(extra_local) + len(missing_local))
    print("Extra local:", len(extra_local))
    print("Missing local:", len(missing_local))

    if len(extra_local) > 0:
        print("\nExtra local:")
        for cid in sorted(extra_local, key=lambda c: db.cards_by_id[c]["name"]):
            card = db.cards_by_id[cid]
            print(f"  - {card['name']} — {card['type_line']}")

    if len(missing_local) > 0:
        print("\nMissing local:")
        for cid in sorted(missing_local):
            card = db.cards_by_id.get(cid)

            if card is None:
                print(f"  - {cid} (not indexed locally)")
            else:
                print(f"  - {card['name']} — {card['type_line']}")

if __name__ == '__main__':
    from scryfall import fetch_bulk_data
    from sys import argv

    updated = fetch_bulk_data()

    db = CardDatabase()
    db.load(rebuild_cache=True)

    print()

    num_args = len(argv) - 1
    if num_args == 0:
        update_parsed_tags(db)
    elif num_args == 2:
        test_tag_against_scryfall(db, argv[1], argv[2])
    else:
        print("Usage: no arguments to update parsed tags OR <tag-slug> <scryfall-search> for testing against scryfall")