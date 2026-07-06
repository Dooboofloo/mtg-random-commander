from __future__ import annotations

from dataclasses import dataclass, field
from random import choice, randint, random, sample, uniform
from difflib import get_close_matches

from carddb import CardDatabase
from synergy import get_synergy_pool

COLORS = ("W", "U", "B", "R", "G")
COLOR_TO_BASIC = {
    "W": "Plains",
    "U": "Island",
    "B": "Swamp",
    "R": "Mountain",
    "G": "Forest",
    "C": "Wastes",
}


@dataclass(frozen=True)
class DeckPackage:
    name: str
    tags: tuple[str, ...] | str
    count: tuple[int, int] | int
    include_children: bool = True
    exclude_types: tuple[str, ...] = ("Land",)

    def roll_count(self) -> int:
        if isinstance(self.count, int):
            return self.count
        return randint(*self.count)


@dataclass
class DeckSettings:
    commander_name: str = "random"

    land_count: tuple[int, int] = (34, 40)
    nonbasic_percent_delta: tuple[float, float] = (-0.1, 0.1)
    chance_of_snow: float = 0.055

    packages: tuple[DeckPackage, ...] = field(default_factory=lambda: (
        DeckPackage("Ramp", "ramp", (8, 12)),
        DeckPackage("Removal", ("removal", "counterspell"), (8, 12)),
        DeckPackage("Card Draw", "draw", (5, 9))
    ))

    synergy_percent: float = 0.25


class DeckBuilder:
    def __init__(self, db: CardDatabase, settings: DeckSettings):
        self.db = db
        self.settings = settings

        self.commander_id: str | None = None
        self.deck_ids: set[str] = set()
        self.basic_lands: list[str] = []
        self.card_colors = {c: 0 for c in (*COLORS, "C")}

    ### Main Driver
    
    def build(self) -> list[str]:
        self._choose_commander()

        print(f"Building Commander: {self.commander['name']}...")

        target_land_count = randint(*self.settings.land_count)
        target_nonland_count = 99 - target_land_count

        for package in self.settings.packages:
            print(f"Adding package: {package.name}...")
            self._add_package(package)

        if self.land_count > target_land_count:
            raise ValueError(
                f"Packages added too many lands: "
                f"{self.land_count} lands, target was {target_land_count}"
            )

        if self.nonland_count > target_nonland_count:
            raise ValueError(
                f"Packages added too many nonlands: "
                f"{self.nonland_count} nonlands, target was {target_nonland_count}"
            )
        
        remaining_nonlands = target_nonland_count - self.nonland_count
        synergy_count = int(remaining_nonlands * self.settings.synergy_percent)

        print("Adding synergy cards...")
        self._add_synergy_cards(synergy_count)
        
        remaining_nonlands = target_nonland_count - self.nonland_count

        print("Adding misc cards...")
        self._add_misc_cards(remaining_nonlands)

        print("Filling lands...")
        self._fill_lands(target_land_count)

        if self.maindeck_count != 99:
            raise ValueError(f"Deck has {self.maindeck_count} maindeck cards, expected 99")
        
        return self.export_lines()

    ### Properties

    @property
    def commander(self) -> dict:
        return self.db.cards_by_id[self.commander_id]
    
    @property
    def commander_colors(self) -> frozenset[str]:
        colors = frozenset(self.commander["color_identity"])
        return colors if colors else frozenset({"C"})
    
    @property
    def basic_land_count(self) -> int:
        return sum(int(line.split(" ", 1)[0]) for line in self.basic_lands)

    @property
    def deck_land_ids(self) -> set[str]:
        return self.deck_ids & self.db.cards_by_type["Land"]

    @property
    def deck_nonland_ids(self) -> set[str]:
        return self.deck_ids - self.db.cards_by_type["Land"]

    @property
    def land_count(self) -> int:
        return len(self.deck_land_ids) + self.basic_land_count

    @property
    def nonland_count(self) -> int:
        return len(self.deck_nonland_ids)

    @property
    def maindeck_count(self) -> int:
        return self.land_count + self.nonland_count

    ### Build Methods

    def _choose_commander(self) -> None:
        if self.settings.commander_name == "random":
            self.commander_id = choice(tuple(self.db.commander_candidates))
        else:
            self.commander_id = self._find_commander_by_name(
                self.settings.commander_name
            )
    
    def _find_commander_by_name(self, name: str) -> str:
        if name in self.db.cards_by_name:
            cid = self.db.cards_by_name[name]
            if cid in self.db.commander_candidates:
                return cid

        lowered_to_name = {}

        for card_name, cid in self.db.cards_by_name.items():
            if cid not in self.db.commander_candidates:
                continue

            lowered_to_name[card_name.lower()] = card_name

            if " // " in card_name:
                lowered_to_name[card_name.lower().split(" // ")[0]] = card_name # Also match just the front face of double-faced commanders

        query = name.lower()

        if query in lowered_to_name:
            return self.db.cards_by_name[lowered_to_name[query]]

        matches = get_close_matches(
            query,
            lowered_to_name.keys(),
            n=5,
            cutoff=0.6,
        )

        if not matches:
            raise ValueError(f'No commander found matching "{name}"')

        best_name = lowered_to_name[matches[0]]
        return self.db.cards_by_name[best_name]

    def _base_pool(self) -> set[str]:
        pool = self.db.cards_legal_for_commander(self.commander_colors)
        pool -= self.deck_ids
        pool.discard(self.commander_id)
        return pool

    def _base_nonland_pool(self) -> set[str]:
        pool = self._base_pool()
        pool -= self.db.cards_by_type["Land"]
        return pool

    def _add_package(self, package: DeckPackage) -> None:
        count = package.roll_count()

        pool = self._base_pool()

        tags = package.tags
        if isinstance(tags, str):
            tags = (tags,)

        tag_pool = set()
        for tag in tags:
            tag_pool |= self.db.get_cards_for_tag(
                tag,
                expand_children=package.include_children,
            )
        
        pool &= tag_pool

        for card_type in package.exclude_types:
            pool -= self.db.cards_by_type[card_type]

        self._add_random_cards(pool, count, allow_shortfall=True)

    def _add_synergy_cards(self, count: int) -> None:
        pool = get_synergy_pool(self.db, self.commander_id)
        pool &= self._base_pool()
        self._add_random_cards(pool, count, allow_shortfall=True)

    def _add_misc_cards(self, count: int) -> None:
        pool = self._base_nonland_pool()
        self._add_random_cards(pool, count)
    
    def _fill_lands(self, target_land_count: int) -> None:
        lands_needed = target_land_count - self.land_count

        if lands_needed <= 0:
            return

        # Amount of nonbasics is proportional to the deck's number of colors
        if self.commander_colors == frozenset({"C"}):
            # 0 colors = 0.6 (utility lands are far more important in colorless decks)
            nonbasic_percent_base = 0.6
        else:
            # 1 color = 0.3; 5 colors = 0.7
            nonbasic_percent_base = 0.2 + 0.1 * len(self.commander_colors)
        
        nonbasic_percent = nonbasic_percent_base + uniform(*self.settings.nonbasic_percent_delta)

        desired_total_nonbasics = int(target_land_count * nonbasic_percent)
        current_nonbasics = len(self.deck_land_ids)

        nonbasics_needed = max(0, desired_total_nonbasics - current_nonbasics)
        nonbasics_needed = min(nonbasics_needed, lands_needed)

        self._add_nonbasic_lands(nonbasics_needed)

        basics_needed = target_land_count - self.land_count

        self._add_basic_lands(basics_needed)

    def _add_nonbasic_lands(self, count: int) -> None:
        pool = self.db.cards_legal_for_commander(self.commander_colors)
        pool &= self.db.cards_by_type["Land"]
        pool -= self.db.cards_by_supertype["Basic"]
        pool -= self.deck_ids

        # Filter out useless fetchlands
        pool = {
            cid for cid in pool
            if self._land_is_useful(cid)
        }

        self._add_random_cards(pool, count, allow_shortfall=True)

    def _add_basic_lands(self, count: int) -> None:
        colors = tuple(c for c in self.commander_colors if c in COLORS)

        if not colors:
            self._add_basic_name("Wastes", count)
            return
        
        total_pips = sum(self.card_colors[c] for c in colors)

        if total_pips == 0:
            for _ in range(count):
                self._add_basic_name(COLOR_TO_BASIC[choice(colors)], 1)
            return
        
        assigned = 0

        for color in colors:
            n = int(count * (self.card_colors[color] / total_pips))
            assigned += n
            self._add_basic_name(COLOR_TO_BASIC[color], n)
        
        while assigned < count:
            self._add_basic_name(COLOR_TO_BASIC[choice(colors)], 1)
            assigned += 1

    def _add_basic_name(self, name: str, count: int) -> None:
        if count <= 0:
            return
        
        if self.db.card_has_tag(self.commander_id, "synergy-snow"):
            # If commander cares about snow permanents, make all basics snow
            snow = count
        else:
            # Otherwise, have a fun random chance to include snow-covered basics
            snow = 0
            for _ in range(count):
                if random() < self.settings.chance_of_snow:
                    snow += 1
        
        normal = count - snow

        if normal:
            self.basic_lands.append(f"{normal} {name}")
        
        if snow:
            self.basic_lands.append(f"{snow} Snow-Covered {name}")

    def _land_is_useful(self, card_id: str) -> bool:
        # Filter out useless fetchlands (Scalding Tarn can fetch an Island or Mountain -> Useless in a Golgari (BG) deck)

        card = self.db.cards_by_id[card_id]

        # Non-fetchlands are allowed by default.
        if card_id not in self.db.get_cards_for_tag("fetchland"):
            return True
        
        text = card.get("oracle_text", "")

        # Fetchlands that grab any basic are also okay
        if "basic land card" in text:
            return True

        return any(
            COLOR_TO_BASIC[color] in text
            for color in self.commander_colors
            if color in COLOR_TO_BASIC
        )

    def _add_random_cards(self, pool: set[str], count: int, allow_shortfall: bool = False) -> None:
        available = tuple(pool - self.deck_ids)

        if len(available) < count:
            if not allow_shortfall:
                raise ValueError(f"Not enough candidates: needed {count}, found: {len(available)}")
            
            # If there is a shortfall (and we allow there to be), we simply take the whole pool
            count = len(available)
        
        for card_id in sample(available, count):
            self._add_card(card_id)

    def _add_card(self, card_id: str) -> None:
        self.deck_ids.add(card_id)
        self._count_card_colors(card_id)

    def _count_card_colors(self, card_id: str) -> None:
        card = self.db.cards_by_id[card_id]

        costs = []

        if "mana_cost" in card:
            costs.append(card["mana_cost"])
        
        for face in card.get("card_faces", []):
            if "mana_cost" in face:
                costs.append(face["mana_cost"])
        
        for cost in costs:
            for color in COLORS:
                self.card_colors[color] += cost.count(color)

    ### Exporting

    def export_lines(self) -> list[str]:
        lines = []

        for card_id in sorted(self.deck_ids, key=self._sort_name):
            lines.append(f"1 {self.db.cards_by_id[card_id]['name']}")
        
        for basic_land in sorted(self.basic_lands):
            lines.append(basic_land)

        lines.append("")
        lines.append("// COMMANDER")
        lines.append(f"1 {self.commander['name']}")

        return lines
    
    def _sort_name(self, card_id: str) -> str:
        return self.db.cards_by_id[card_id]['name']