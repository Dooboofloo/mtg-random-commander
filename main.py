import requests

### Requests constants
OK = 200
REQ_HEADER = {"User-Agent": "MTGRandomCommanderDeck/2.0", "Accept": "*/*"}

# Request URLs
SCRYFALL_BULK_DATA_URL = r"https://api.scryfall.com/bulk-data"


### Helper Methods

def get_request_as_json(request_url: str):
    try:
        response = requests.get(request_url, headers=REQ_HEADER)

        if response.status_code == OK:
            return response.json()
        else:
            raise ValueError(f'API Request Failed! ({request_url})')
    except Exception as e:
        raise e

### Main

def main():
    
    bulk_data = get_request_as_json(SCRYFALL_BULK_DATA_URL)

    print(bulk_data)

if __name__ == '__main__':
    main()