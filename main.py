import requests
from pathlib import Path

### Requests constants
OK = 200
REQ_HEADER = {"User-Agent": "MTGRandomCommanderDeck/2.0", "Accept": "*/*"}

# Request URLs
SCRYFALL_BULK_DATA_URL = r"https://api.scryfall.com/bulk-data" # Contains information about the most up-to-date versions of Scryfall's bulk data stores

# Scryfall bulk data ids (stable)
ORACLE_CARDS_ID = r"27bf3214-1271-490b-bdfe-c0be6c23d02e"
ORACLE_TAGS_ID = r"bd8df61e-5d0a-47a2-9086-40137a645b98"

### Helper Methods

def save_json(data: dict, file_path: str) -> None:
    pass

def get_request_as_json(request_url: str) -> dict:
    try:
        response = requests.get(request_url, headers=REQ_HEADER)

        if response.status_code == OK:
            return response.json()
        else:
            raise ValueError(f'API Request Failed! ({request_url})')
    except Exception as e:
        raise e

def save_request_as_file(request_url: str, file_path: str) -> None:
    try:
        response = requests.get(request_url, headers=REQ_HEADER, stream=True)

        if response.status_code == OK:
            
            output_file = Path(file_path)
            output_file.parent.mkdir(exist_ok=True, parents=True)
            output_file.write_bytes(response.content)

            # with open(file_path, 'wb') as file:
            #     file.write(response.content)

        else:
            raise ValueError(f'API Request Failed! ({request_url})')
    except Exception as e:
        raise e

def fetch_bulk_data(ids_to_save: list = [ORACLE_CARDS_ID, ORACLE_TAGS_ID]) -> None:
    # TODO: Check timestamps of existing files, only update if necessary

    bulk_data = get_request_as_json(SCRYFALL_BULK_DATA_URL)

    obj_to_save = [x for x in bulk_data['data'] if x['id'] in ids_to_save]

    for obj in obj_to_save:
        obj_name = obj['name']
        download_uri = obj['download_uri']

        save_request_as_file(download_uri, f'./data/{obj_name}.json')

### Main

def main():
    fetch_bulk_data()

if __name__ == '__main__':
    main()