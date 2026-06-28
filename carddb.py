from collections import defaultdict
from pathlib import Path
import json

SUPERTYPES = frozenset({
    "Basic",
    "Legendary",
    "Ongoing",
    "Snow",
    "World",
})

EXCLUDED_CARDS = {
    "bf29b215-d4f5-4641-97ef-b65d4c463e72", 
    "4b9922b9-c5b5-467e-8a5b-1e45e862194d",
    "af147bb6-aa46-4fc9-af96-de3740c19fd5",
    "f71f01bc-caae-426b-a25a-bfbfeb9feb67",
    "d410027b-1c22-461e-939d-06a2c851352e", # Banding lands
}

class CardDatabase:
    def __init__(self, oracle_path: str | Path = r"./data/Oracle Cards.json", tag_path: str | Path = r"./data/Oracle Tags.json"):
        
        self.oracle_path = Path(oracle_path)
        self.tag_path = Path(tag_path)

        # Tag hierarchy
        self.tag_parents: dict[str, set[str]] = defaultdict(set)
        self.tag_children: dict[str, set[str]] = defaultdict(set)

        # Tag lookups
        self.tag_by_id: dict[str, str] = {}
        self.id_by_tag: dict[str, str] = {}

        # Primary card lookup
        self.cards_by_id: dict[str, dict] = {}

        # Secondary card lookups
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

        self.commander_candidates = set()


    ### Construction Helpers

    def _can_be_commander(card: dict) -> bool:

        if card["oracle_id"] == r"0efb0d7e-dea0-4817-a243-15066e9ef333":
            # Special case for Grist, the Hunger Tide
            return True

        oracle_text = card.get("oracle_text", "")

        front_face_obj = card.get("card_faces", [card])[0]

        front_face_tl = front_face_obj.get("type_line", "")
        has_pt = "power" in front_face_obj and "toughness" in front_face_obj

        if "Legendary" not in front_face_tl:
            return False
        if "Background" in front_face_tl:
            return False
        
        # 1. Legendary Creature
        if "Creature" in front_face_tl:
            return True
    
        # 2. Legendary Vehicle
        if "Vehicle" in front_face_tl:
            return True
        
        # 3. Legendary Spacecraft with P/T
        if "Spacecraft" in front_face_tl and has_pt:
            return True
        
        # 4. Planeswalker with commander clause
        if "Planeswalker" in front_face_tl and "can be your commander" in oracle_text.lower():
            return True
        
        return False

    ### Database Construction

    def load(self) -> None:
        self._load_oracle_cards()
        self._load_tags()

    def _load_oracle_cards(self) -> None:
        oracle_cards = json.loads(self.oracle_path.read_text(encoding='utf-8'))

        for card in oracle_cards:

            oracle_id = card["oracle_id"]

            ### Guard Clauses

            # Card must be legal in commander
            if card["legalities"]["commander"] != 'legal':
                continue

            # Skip meld backsides
            if card["layout"] == "meld":
                if any(card["name"] == part["name"] and part["component"] == "meld_result" for part in card["all_parts"]):
                    continue

            # House rule/unfun cards
            if oracle_id in EXCLUDED_CARDS:
                continue


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
            for kw in card.get("keywords", []):
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
                    if word in SUPERTYPES:
                        self.cards_by_supertype[word].add(oracle_id)
                    else:
                        self.cards_by_type[word].add(oracle_id)
                
                for subtype in subtypes:
                    self.cards_by_subtype[subtype].add(oracle_id)
            
            # Register commanders
            if CardDatabase._can_be_commander(card):
                self.commander_candidates.add(oracle_id)
        
    def _load_tags(self) -> None:
        
        tag_data = json.loads(self.tag_path.read_text(encoding='utf-8'))

        for tag in tag_data:
            tag_id = tag["id"]
            label = tag["slug"]

            # Register tag lookups
            self.tag_by_id[tag_id] = label
            self.id_by_tag[label] = tag_id

            # Register tag hierarchy (by ids)
            self.tag_parents[tag_id] |= set(tag["parent_ids"])
            self.tag_children[tag_id] |= set(tag["child_ids"])

            # Register card taggings
            for tagging in tag["taggings"]:

                oracle_id = tagging["oracle_id"]

                self.cards_by_tag[tag_id].add(oracle_id)
                self.tags_by_card[oracle_id].add(tag_id)
    

    def _expand_tag(self, tag_id: str) -> set[str]:
        
        result = set()

        stack = [tag_id]

        while stack:
            t = stack.pop()
            if t in result:
                continue
            result.add(t)
            stack.extend(self.tag_children.get(t, []))
        
        return result

    ### Database Queries

    def get_cards_for_tag(self, tag_name: str, expand_children: bool = True) -> set[str]:

        if not tag_name in self.id_by_tag:
            return set()
        
        tag_id = self.id_by_tag[tag_name]

        if not expand_children:
            return self.cards_by_tag[tag_id]

        expanded = self._expand_tag(tag_id)

        result = set()
        for t in expanded:
            result |= self.cards_by_tag[t]
        
        return result

    def cards_legal_for_commander(self, commander_colors: frozenset[str]) -> set[str]:
        
        legal = set()

        for identity, cards in self.cards_by_color_identity.items():
            if identity <= commander_colors:
                legal |= cards
        
        return legal
            
