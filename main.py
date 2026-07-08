from pathlib import Path
import argparse
import re

from scryfall import fetch_bulk_data
from carddb import CardDatabase
from deckbuilder import DeckSettings, DeckBuilder, DeckPackage

### Constants

# Some house banned cards that we don't ever want to see
EXCLUDED_CARDS = {
    "bf29b215-d4f5-4641-97ef-b65d4c463e72", 
    "4b9922b9-c5b5-467e-8a5b-1e45e862194d",
    "af147bb6-aa46-4fc9-af96-de3740c19fd5",
    "f71f01bc-caae-426b-a25a-bfbfeb9feb67",
    "d410027b-1c22-461e-939d-06a2c851352e", # Banding lands
    "6d6a25fb-0432-4c7d-b0e6-e787ddc71218", # Cryptic Spire
}

### Helpers

def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name)

def save_decklist(decklist: list[str], out_dir: str | Path, commander_name: str, index: int | None = None) -> Path:
    
    if index is None:
        filename = f"{commander_name}"
    else:
        filename = f"{index}_{commander_name}"

    out_path = Path(out_dir) / f"{safe_filename(filename)}.txt"
    out_path.parent.mkdir(exist_ok=True, parents=True)

    new_id = 0
    while out_path.exists():
        new_id += 1
        out_path = Path(out_dir) / f"{safe_filename(filename)} ({new_id}).txt"

    out_path.write_text('\n'.join(decklist), encoding='utf-8')

    return out_path

def parse_range(value: str, type_func=int):
    
    if '-' not in value:
        return type_func(value)
    
    lo, hi = value.split('-')
    return type_func(lo), type_func(hi)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a random Commander decklist."
    )

    parser.add_argument(
        "-c", "--commander",
        default="random",
        help='Commander name. Defaults to "random".',
    )

    parser.add_argument(
        "-o", "--out-dir",
        default="./out",
        help="Output directory for generated decklists.",
    )

    parser.add_argument(
        "--lands",
        default="34-40",
        help='Number of lands, either fixed or range. Example: "36" or "34-40".',
    )

    parser.add_argument(
        "--snow-chance",
        type=float,
        default=0.055,
        help="Chance that each basic land is snow-covered. Overridden to 1.0 if commander has snow synergy.",
    )

    parser.add_argument(
        "--synergy-percent",
        type=float,
        default=0.25,
        help="Percent of remaining nonland slots filled from commander synergy tags.",
    )

    parser.add_argument(
        "--include-banned",
        action="store_true",
        help="Allow Commander-banned cards except for structurally problematic cards.",
    )

    parser.add_argument(
        "--rebuild-cache",
        action="store_true",
        help="Force rebuild of the local CardDatabase cache.",
    )

    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of decklists to generate.",
    )

    parser.add_argument(
        "--package",
        nargs=2,
        action="append",
        metavar=("TAG_SLUG", "RANGE"),
        default=None,
        help=(
            "Add a deck package by Scryfall Tagger slug and count/range. "
            'Repeatable. Example: --package ramp 8-12 --package removal 8'
        ),
    )

    parser.add_argument(
        "--packages-include-lands",
        action="store_true",
        help="Allows user-defined packages to include lands."
    )

    parser.add_argument(
        "--no-packages",
        action="store_true",
        help="Causes there to be no predefined packages in deck creation."
    )

    return parser

def packages_from_args(args: argparse.Namespace) -> tuple[DeckPackage, ...] | None:
    if not args.package:
        return None

    packages = []

    for tag_slug, count_text in args.package:
        count = parse_range(count_text, int)

        if isinstance(count, int):
            count = (count, count)

        packages.append(
            DeckPackage(
                name=tag_slug,
                tags=(tag_slug,),
                count=count,
                exclude_types=("Land",) if not args.packages_include_lands else ()
            )
        )

    return tuple(packages)

def settings_from_args(args: argparse.Namespace) -> DeckSettings:
    lands = parse_range(args.lands, int)

    if isinstance(lands, int):
        lands = (lands, lands)

    packages = packages_from_args(args)

    if args.no_packages:
        return DeckSettings(
            commander_name=args.commander,
            land_count=lands,
            chance_of_snow=args.snow_chance,
            synergy_percent=args.synergy_percent,
            packages=(),
        )

    if packages is None:
        return DeckSettings(
            commander_name=args.commander,
            land_count=lands,
            chance_of_snow=args.snow_chance,
            synergy_percent=args.synergy_percent,
        )

    return DeckSettings(
        commander_name=args.commander,
        land_count=lands,
        chance_of_snow=args.snow_chance,
        synergy_percent=args.synergy_percent,
        packages=packages,
    )

### Validation

def validate_decklist(db: CardDatabase, builder: DeckBuilder) -> None:
    # Test number of cards in maindeck

    num_singleton = len(builder.deck_ids)
    num_basics = sum(int(line.split(' ')[0]) for line in builder.basic_lands)
    total = num_singleton + num_basics

    total = builder.maindeck_count

    # Test maindeck size
    if total != 99:
        raise ValueError(f"Invalid maindeck size: {total}")

    # Test cards CI against commander's
    for cid in builder.deck_ids:
        card = builder.db.cards_by_id[cid]
        identity = frozenset(card["color_identity"])

        if not (identity <= builder.commander_colors):
            raise ValueError(f"Invalid color identity: {identity} (should be {builder.commander_colors})")

    # Test excluded type inclusions
    for cid in builder.deck_ids:
        card = builder.db.cards_by_id[cid]
        type_line = card["type_line"]

        for t in {"Attraction", "Sticker"}:
            if t in type_line:
                raise ValueError(f"Invalid type inclusion: {type_line}")

    # Text excluded tag inclusions
    for cid in builder.deck_ids:
        for tag in db.excluded_tags:
            if cid in db.get_cards_for_tag(tag):
                raise ValueError(f"Card with excluded tag included: {db.cards_by_id[cid]['name']} (excluded tag: {tag})")

### Main

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        updated = fetch_bulk_data()
    except:
        print("Fetching bulk data failed.")

        cards_exist = Path("./data/Oracle Cards.json").exists()
        tags_exist = Path("./data/Oracle Tags.json").exists()

        if not (cards_exist and tags_exist):
            raise FileExistsError("No local data files exist.")

        updated = False


    db = CardDatabase(
        excluded_cards = EXCLUDED_CARDS,
        include_banned = args.include_banned,
    )
    db.load(rebuild_cache=updated or args.rebuild_cache)

    settings = settings_from_args(args)

    print()

    for i in range(args.count):

        builder = DeckBuilder(db, settings)
        decklist = builder.build()

        validate_decklist(db, builder)

        index = i + 1 if args.count > 1 else None
        out_path = save_decklist(decklist, args.out_dir, builder.commander['name'], index=index)

        print(f"Saved decklist: {out_path}")
        print()

if __name__ == '__main__':
    main()
