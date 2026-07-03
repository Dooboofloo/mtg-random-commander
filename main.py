from scryfall import fetch_bulk_data
from carddb import CardDatabase
from deckbuilder import DeckSettings, DeckBuilder
from pathlib import Path
import re

### Constants

# Some house banned cards that we don't ever want to see
EXCLUDED_CARDS = {
    "bf29b215-d4f5-4641-97ef-b65d4c463e72", 
    "4b9922b9-c5b5-467e-8a5b-1e45e862194d",
    "af147bb6-aa46-4fc9-af96-de3740c19fd5",
    "f71f01bc-caae-426b-a25a-bfbfeb9feb67",
    "d410027b-1c22-461e-939d-06a2c851352e", # Banding lands
}

### Helpers

def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name)

### Main

def main():
    updated = fetch_bulk_data()

    db = CardDatabase(excluded_cards=EXCLUDED_CARDS)
    db.load(rebuild_cache=updated)

    settings = DeckSettings()
    builder = DeckBuilder(db, settings)
    decklist = builder.build()

    print(f"Saving decklist...")

    commander_name = safe_filename(builder.commander['name'])

    out_path = Path(f'./out/{commander_name}.txt')
    out_path.parent.mkdir(exist_ok=True, parents=True)

    out_path.write_text('\n'.join(decklist), encoding='utf-8')

    print("Decklist saved!")

### Tests

def validate_decks(n: int = 1000):
    updated = fetch_bulk_data()

    db = CardDatabase(excluded_cards=EXCLUDED_CARDS)
    db.load(rebuild_cache=updated)

    settings = DeckSettings()
    builder = DeckBuilder(db, settings)
    decklist = builder.build()

    num_invalid = 0

    for i in range(n):
        print(f"===== Iteration {i} =====")

        print()

        settings = DeckSettings()
        builder = DeckBuilder(db, settings)
        decklist = builder.build()

        print(f"Validating decklist...")

        valid = True

        # Test number of cards in maindeck

        num_singleton = len(builder.deck_ids)
        num_basics = sum(int(line.split(' ')[0]) for line in builder.basic_lands)
        total = num_singleton + num_basics

        print(total)
        if total != 99:
            valid = False

        # Test cards CI against commander's

        print(f"Commander CI: {builder.commander_colors}")
        for cid in builder.deck_ids:
            card = builder.db.cards_by_id[cid]
            identity = frozenset(card["color_identity"])

            if not (identity <= builder.commander_colors):
                valid = False
                print(card['name'], identity)
                break

        # Test excluded type inclusions

        EXCLUDED_TYPE_WORDS = {"Attraction", "Sticker"}

        for cid in builder.deck_ids:
            card = builder.db.cards_by_id[cid]
            type_line = card["type_line"]

            if any(t in type_line for t in EXCLUDED_TYPE_WORDS):
                valid = False
                print("Excluded type:", card["name"], type_line)
                break

        # Text excluded tag inclusions

        for cid in builder.deck_ids:
            for tag in db.excluded_tags:
                if cid in db.get_cards_for_tag(tag):
                    valid = False
                    print("Excluded tag:", card["name"], tag)
                    break

        if not valid:
            num_invalid += 1
            print(f"INVALID!!! Saving decklist...")

            commander_name = safe_filename(builder.commander['name'])

            out_path = Path(f'./out/{commander_name}.txt')
            out_path.parent.mkdir(exist_ok=True, parents=True)

            out_path.write_text('\n'.join(decklist), encoding='utf-8')

            print("Decklist saved!")

        print()
    
    print(num_invalid)

if __name__ == '__main__':
    validate_decks()
