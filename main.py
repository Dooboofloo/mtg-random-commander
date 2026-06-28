from scryfall import fetch_bulk_data
from carddb import CardDatabase

### Main

def main():
    fetch_bulk_data()

    db = CardDatabase()
    db.load()

    candidates = set(db.cards_by_id.keys())
    candidates &= db.cards_by_tag["ramp"]
    candidates &= db.cards_by_type["Creature"]

    LLANOWAR_ELVES = db.cards_by_name["Llanowar Elves"] # Tagged directly as "mana-dork", which is a child of "mana-producer" <- "ramp"

    # print(db.get_cards_for_tag('ramp'))

    # # All of the following should be true
    print(LLANOWAR_ELVES in db.get_cards_for_tag('mana-dork', expand_children=False))
    print(LLANOWAR_ELVES in db.get_cards_for_tag('mana-producer', expand_children=False))
    print(LLANOWAR_ELVES in db.get_cards_for_tag('ramp', expand_children=False))

if __name__ == '__main__':
    main()