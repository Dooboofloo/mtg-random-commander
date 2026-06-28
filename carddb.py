from collections import defaultdict
from pathlib import Path
import json


class CardDatabase:
    def __init__(self, oracle_path: str | Path = r"./data/Oracle Cards.json", tag_path: str | Path = r"./data/Oracle Tags.json"):
        
        self.oracle_path = Path(oracle_path)
        self.tag_path = Path(tag_path)

        # Primary lookup
        self.cards_by_id: dict[str, dict] = {}

        # Secondary lookups
        self.cards_by_name: dict[str, str] = {}

        self.cards_by_tag: dict[str, set[str]] = defaultdict(set)
        self.tags_by_card: dict[str, set[str]] = defaultdict(set)

        self.cards_by_type: dict[str, set[str]] = defaultdict(set)
        self.cards_by_supertype: dict[str, set[str]] = defaultdict(set)
        self.cards_by_subtype: dict[str, set[str]] = defaultdict(set)

        self.cards_by_keywords: dict[str, set[str]] = defaultdict(set)

        self.cards_by_colors: dict[frozenset[str], set[str]] = defaultdict(set)
        self.cards_by_color_identity: dict[frozenset[str], set[str]] = defaultdict(set)
        self.cards_by_mana_value: dict[int, set[str]] = defaultdict(set)

        self.commanders = set() # TODO


    ### Database Construction

    def load(self) -> None:
        self._load_oracle_cards()
        self._load_tags()

    def _load_oracle_cards(self) -> None:
        oracle_cards = json.loads(self.oracle_path.read_text(encoding='utf-8'))

        for card in oracle_cards:

            if card["legalities"]["commander"] != 'legal':
                continue

            oracle_id = card["oracle_id"]

            self.cards_by_id[oracle_id] = card
            self.cards_by_name[card["name"]] = oracle_id

            # Mana Value
            self.cards_by_mana_value[card["cmc"]].add(oracle_id)

            # Color
            all_colors = set(card.get("colors", []))

            if not all_colors and "card_faces" in card:
                for face in card["card_faces"]:
                    all_colors |= set(face.get("colors", []))
        
            self.cards_by_colors[frozenset(all_colors)].add(oracle_id)

            # Color Identity
            self.cards_by_color_identity[
                frozenset(card["color_identity"])
            ].add(oracle_id)

            # Keywords
            for kw in card["keywords"]:
                self.cards_by_keywords[kw].add(oracle_id)


            # Split behavior based on card layout (Colors and Type Lines)
            if "card_faces" in card:
                type_lines = [face["type_line"] for face in card["card_faces"]]
            else:
                type_lines = [card["type_line"]]

            # Type Lines
            for type_line in type_lines:
                if "—" in type_line:
                    left, right = type_line.split("—", 1)
                    subtypes = right.strip().split()
                else:
                    left = type_line
                    subtypes = []

                for word in left.split():
                    if word in {
                        "Basic",
                        "Legendary",
                        "Ongoing",
                        "Snow",
                        "World",
                        "Token"
                    }:
                        self.cards_by_supertype[word].add(oracle_id)
                    else:
                        self.cards_by_type[word].add(oracle_id)
                
                for subtype in subtypes:
                    self.cards_by_subtype[subtype].add(oracle_id)
        
    def _load_tags(self) -> None:
        
        tag_data = json.loads(self.tag_path.read_text(encoding='utf-8'))

        for tag in tag_data:
            
            label = tag["label"]

            for tagging in tag["taggings"]:

                oracle_id = tagging["oracle_id"]

                self.cards_by_tag[label].add(oracle_id)
                self.tags_by_card[oracle_id].add(label)
    

    ### Database Queries

    def cards_legal_for_commander(self, commander_colors: frozenset[str]) -> set[str]:
        
        legal = set()

        for identity, cards in self.cards_by_color_identity.items():
            if identity <= commander_colors:
                legal |= cards
        
        return legal
            
