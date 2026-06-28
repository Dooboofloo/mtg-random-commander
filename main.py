from scryfall import fetch_bulk_data
from carddb import CardDatabase

### Main

def main():
    fetch_bulk_data()

    db = CardDatabase()
    db.load()

    import random
    chosen_commander = random.choice(list(db.commander_candidates))
    print(db.cards_by_id[chosen_commander]["name"])

if __name__ == '__main__':
    main()
