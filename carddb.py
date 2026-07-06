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

EXCLUDED_TYPES = frozenset({
    "Sticker",
    "Attraction",
})

class CardDatabase:
    def __init__(self,
            oracle_path: str | Path = r"./data/Oracle Cards.json",
            tag_path: str | Path = r"./data/Oracle Tags.json",
            cache_path: str | Path = r"./data/carddb.cache.json",
            **options
        ):
        
        # File paths
        self.oracle_path = Path(oracle_path)
        self.tag_path = Path(tag_path)
        self.cache_path = Path(cache_path)

        # Construction Helpers
        self.excluded_by_tag: set[str] = set()
        self.expanded_tags_cache: dict[tuple[str, bool], set[str]] = {}

        # Options
        self.include_banned: bool = options.get("include_banned", False)
        self.excluded_cards: set[str] = options.get("excluded_cards", set())
        self.excluded_tags: set[str] = options.get("excluded_tags", {"draft-matters"})

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
        self.cards_by_mana_value: dict[float, set[str]] = defaultdict(set)

        self.commander_candidates = set()


    ### Construction Helpers

    def _should_index_card(self, card: dict) -> bool:

        oracle_id = card["oracle_id"]

        # House bans / unfun cards
        if oracle_id in self.excluded_cards:
            return False

        # Exclude cards that have effects when drafted
        if oracle_id in self.excluded_by_tag:
            return False

        # Exclude certain card types that are "legal" in commander but not included in the main deck
        if any((card_type in card["type_line"]) for card_type in EXCLUDED_TYPES):
            return False
        
        # If banned in commander but chosen to be included regardless, allow inclusion (except for the below exceptions)
        if card["legalities"]["commander"] == "banned" and self.include_banned:
            if (
                "Conspiracy" in card["type_line"]
                or self.card_has_tag(oracle_id, "ante-matters")
                or card["name"] in ["Chaos Orb", "Falling Star", "Shahrazad"]
            ):
                return False
            
            return True

        # Exclude back side of melded permanents
        if (
            card["layout"] == "meld"
            and any(
                part["component"] == "meld_result"
                and part["name"] == card["name"]
                for part in card["all_parts"]
            )
        ):
            return False

        # Only allow cards legal in commander (unless the above option is chosen)
        if card["legalities"]["commander"] != "legal":
            return False

        return True


    @staticmethod
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

    def load(self, rebuild_cache: bool = False) -> None:
        
        if not rebuild_cache and self.cache_path.exists():
            self.load_cache()
            return

        print("Building CardDB Cache...")

        self._load_tags()

        self.excluded_by_tag = set()
        for tag in self.excluded_tags:
            self.excluded_by_tag |= self.get_cards_for_tag(tag)

        self._load_oracle_cards()
        self.save_cache()

    def _load_oracle_cards(self) -> None:
        oracle_cards = json.loads(self.oracle_path.read_text(encoding='utf-8'))

        for card in oracle_cards:

            # Guard Clauses
            if not self._should_index_card(card):
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

    
    ### Database File Management

    def save_cache(self) -> None:
        print("Saving CardDB Cache...")

        cache_path = Path(self.cache_path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        cache = {
            "tag_parents": {k: list(v) for k, v in self.tag_parents.items()},
            "tag_children": {k: list(v) for k, v in self.tag_children.items()},

            "tag_by_id": self.tag_by_id,
            "id_by_tag": self.id_by_tag,

            "cards_by_id": self.cards_by_id,
            "cards_by_name": self.cards_by_name,

            "cards_by_tag": {k: list(v) for k, v in self.cards_by_tag.items()},
            "tags_by_card": {k: list(v) for k, v in self.tags_by_card.items()},

            "cards_by_type": {k: list(v) for k, v in self.cards_by_type.items()},
            "cards_by_supertype": {k: list(v) for k, v in self.cards_by_supertype.items()},
            "cards_by_subtype": {k: list(v) for k, v in self.cards_by_subtype.items()},
            "cards_by_keywords": {k: list(v) for k, v in self.cards_by_keywords.items()},

            "cards_by_colors": {
                ",".join(sorted(k)): list(v)
                for k, v in self.cards_by_colors.items()
            },
            "cards_by_color_identity": {
                ",".join(sorted(k)): list(v)
                for k, v in self.cards_by_color_identity.items()
            },

            "cards_by_mana_value": {
                str(k): list(v)
                for k, v in self.cards_by_mana_value.items()
            },


            "commander_candidates": list(self.commander_candidates),
        }

        cache_path.write_text(json.dumps(cache), encoding="utf-8")
    
    def load_cache(self) -> None:
        print("Loading CardDB Cache...")

        cache_path = Path(self.cache_path)
        cache = json.loads(cache_path.read_text(encoding="utf-8"))

        self.cards_by_id = cache["cards_by_id"]
        self.cards_by_name = cache["cards_by_name"]

        self.cards_by_tag = defaultdict(set, {
            k: set(v) for k, v in cache["cards_by_tag"].items()
        })
        self.tags_by_card = defaultdict(set, {
            k: set(v) for k, v in cache["tags_by_card"].items()
        })

        self.cards_by_type = defaultdict(set, {
            k: set(v) for k, v in cache["cards_by_type"].items()
        })
        self.cards_by_supertype = defaultdict(set, {
            k: set(v) for k, v in cache["cards_by_supertype"].items()
        })
        self.cards_by_subtype = defaultdict(set, {
            k: set(v) for k, v in cache["cards_by_subtype"].items()
        })
        self.cards_by_keywords = defaultdict(set, {
            k: set(v) for k, v in cache["cards_by_keywords"].items()
        })

        self.cards_by_colors = defaultdict(set, {
            frozenset(k.split(",")) if k else frozenset(): set(v)
            for k, v in cache["cards_by_colors"].items()
        })

        self.cards_by_color_identity = defaultdict(set, {
            frozenset(k.split(",")) if k else frozenset(): set(v)
            for k, v in cache["cards_by_color_identity"].items()
        })

        self.cards_by_mana_value = defaultdict(set, {
            float(k): set(v)
            for k, v in cache["cards_by_mana_value"].items()
        })

        self.commander_candidates = set(cache["commander_candidates"])

        self.tag_parents = defaultdict(set, {
            k: set(v) for k, v in cache["tag_parents"].items()
        })
        self.tag_children = defaultdict(set, {
            k: set(v) for k, v in cache["tag_children"].items()
        })

        self.tag_by_id = cache["tag_by_id"]
        self.id_by_tag = cache["id_by_tag"]

    ### Database Queries

    def get_cards_for_tag(self, tag_name: str, expand_children: bool = True) -> set[str]:

        if not tag_name in self.id_by_tag:
            raise ValueError(f"Unknown tag label: {tag_name}")
        
        cache_key = (tag_name, expand_children)

        if cache_key in self.expanded_tags_cache:
            return self.expanded_tags_cache[cache_key]
        
        tag_id = self.id_by_tag[tag_name]

        if not expand_children:
            return self.cards_by_tag[tag_id]

        expanded = self._expand_tag(tag_id)

        result = set()
        for t in expanded:
            result |= self.cards_by_tag[t]
        
        self.expanded_tags_cache[cache_key] = result

        return result
    
    def get_indexed_cards_for_tag(self, tag_name: str, expand_children: bool = True) -> set[str]:
        return self.get_cards_for_tag(tag_name, expand_children) & set(self.cards_by_id)

    def card_has_tag(self, card_id: str, tag_name: str) -> bool:
        tag_id = self.id_by_tag.get(tag_name)
        return tag_id is not None and tag_id in self.tags_by_card[card_id]

    def cards_legal_for_commander(self, commander_colors: frozenset[str]) -> set[str]:
        
        legal = set()

        for identity, cards in self.cards_by_color_identity.items():
            if identity <= commander_colors:
                legal |= cards
        
        return legal
            
