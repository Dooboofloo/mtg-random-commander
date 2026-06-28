import requests
import json
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

def save_dict(data: dict, file_path: str) -> None:
    output_file = Path(file_path)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f)


def save_bytes(data, file_path: str) -> None:
    output_file = Path(file_path)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    output_file.write_bytes(data)


def get_request_as_json(request_url: str) -> dict:
    response = requests.get(request_url, headers=REQ_HEADER)
    response.raise_for_status()
    return response.json()


def save_request_as_file(request_url: str, file_path: str) -> None:
    response = requests.get(request_url, headers=REQ_HEADER)
    response.raise_for_status()
    save_bytes(response.content, file_path)


def fetch_bulk_data(ids_to_save: tuple[str, ...] = (ORACLE_CARDS_ID, ORACLE_TAGS_ID)) -> None:

    # Retrieve bulk data manifest
    bulk_data = get_request_as_json(SCRYFALL_BULK_DATA_URL)

    obj_to_save = [
        obj for obj in bulk_data['data']
        if obj['id'] in ids_to_save
    ]

    # Prepare local metadata for comparison against up-to-date manifest
    saved_metadata = {}

    data_meta_file = Path('./data/.meta')
    if data_meta_file.exists():
        saved_metadata = json.loads(data_meta_file.read_text(encoding='utf-8'))

    updated_metadata = {}

    for obj in obj_to_save:
        obj_id = obj['id']
        obj_name = obj['name']
        download_uri = obj['download_uri']

        local_file = Path(f"./data/{obj_name}.json")

        saved_timestamp = saved_metadata.get(obj_id)

        should_download = (
            not local_file.exists()
            or saved_timestamp is None
            or obj["updated_at"] > saved_timestamp # ISO format timestamps sort lexicographically
        )

        if should_download:
            print(f"Downloading {obj_name}...")
            save_request_as_file(download_uri, local_file)
        else:
            print(f"{obj_name} is already up to date.")
        
        updated_metadata[obj_id] = obj["updated_at"]

    save_dict(updated_metadata, './data/.meta') # Save timestamp metadata locally