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

    print()

    settings = DeckSettings()
    builder = DeckBuilder(db, settings)
    decklist = builder.build()

    print(f"Saving decklist...")

    commander_name = safe_filename(builder.commander['name'])

    out_path = Path(f'./out/{commander_name}.txt')
    out_path.parent.mkdir(exist_ok=True, parents=True)

    out_path.write_text('\n'.join(decklist), encoding='utf-8')

    print("Decklist saved!")
    

if __name__ == '__main__':
    main()
