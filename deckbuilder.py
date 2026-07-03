from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from random import choice, randint, random, sample, uniform
from typing import Iterable

from carddb import CardDatabase

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
    tags: tuple[str, ...]
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
    nonbasic_percent: tuple[float, float] = (0.25, 0.9) # TODO: Increases linearly by number of colors in identity. 1 color = (0.25, 0.4) -> 5 color = (0.75, 0.9) -> (0.25 + (x-1)/8, 0.4 + (x-1)/8)
    chance_of_snow: float = 0.055

    packages: tuple[DeckPackage, ...] = field(default_factory=lambda: (
        DeckPackage("Ramp", ("ramp",), (8, 12)),
        DeckPackage("Removal", ("removal", "counterspell"), (8, 12)),
        DeckPackage("Card Draw", ("draw"), (5, 9))
    ))

    synergy_percent: float = 0.25


class DeckBuilder:
    def __init__(self, db: CardDatabase, settings: DeckSettings):
        self.db = db
        self.settings = settings

        self.commander_id: str | None = None
        self.deck_ids: set[str] = set()
        self.card_colors = {c: 0 for c in (*COLORS, "C")}

    
    def build(self) -> list[str]:
        self._choose_commander()

        land_count = randint(*self.settings.land_count)
        nonland_count = 99 - land_count

        for package in self.settings.packages:
            self._add_package(package)

        remaining_nonlands = nonland_count - len(self.deck_ids)

        synergy_count = int(remaining_nonlands * self.settings.synergy_percent)
        misc_count = remaining_nonlands - synergy_count

        self._add_synergy_cards(synergy_count)
        self._add_misc_cards(misc_count)
        self._add_lands(land_count)

        return self.export_lines()

    
    def _choose_commander(self) -> None:
        if self.settings.commander_name == "random":
            self.commander_id = choice(tuple(self.db.commander_candidates))
        else:
            self.commander_id = self.db.cards_by_name[self.settings.commander_name]
    
    @property
    def commander(self) -> dict:
        return self.db.cards_by_id[self.commander_id]
    
    @property
    def commander_colors(self) -> frozenset[str]:
        colors = frozenset(self.commander["color_identity"])
        return colors if colors else frozenset({"C"})
    
    """
    TODO:

    _base_nonland_pool
    _add_package
    _add_synergy_cards
    _add_misc_cards

    _add_lands
    _add_nonbasic_lands
    _add_basic_lands
    _add_basic_name

    _land_is_useful

    _add_random_cards
    _add_card

    _count_card_colors

    """

    def export_lines(self) -> list[str]:
        lines = []

        for card_id in sorted(self.deck_ids, key=self._sort_name):
            if card_id[0].isdigit():
                lines.append(card_id)
            else:
                lines.append(f"1 {self.db.cards_by_id[card_id]['name']}")
        
        lines.append("")
        lines.append("// COMMANDER")
        lines.append(f"1 {self.commander['name']}")

        return lines
    

    def _sort_name(self, card_id: str) -> str:
        if card_id[0].isdigit():
            return card_id
        return self.db.cards_by_id[card_id]['name']