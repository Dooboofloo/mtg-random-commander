from scryfall import fetch_bulk_data
from carddb import CardDatabase

### Main

def main():
    fetch_bulk_data()

    db = CardDatabase()
    db.load()

if __name__ == '__main__':
    main()