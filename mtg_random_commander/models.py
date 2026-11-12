"""Application-owned deck settings, plans, and selected-card records."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from math import isfinite
from typing import Literal

Slot = Literal["land", "nonland"]


@dataclass(frozen=True)
class DeckPackage:
    role: str
    tags: tuple[str, ...]
    count_range: tuple[int, int]

    def __post_init__(self) -> None:
        if not self.role or self.role in {"misc", "basic-land", "synergy"}:
            raise ValueError("Package requires a distinct non-reserved role")
        if not self.tags or any(not tag for tag in self.tags):
            raise ValueError("Package requires at least one Oracle Tag")
        low, high = self.count_range
        if not 0 <= low <= high <= 99:
            raise ValueError("Package count range must be ordered and within 0-99")


DEFAULT_PACKAGES = (
    DeckPackage("ramp", ("ramp",), (7, 12)),
    DeckPackage("interaction", ("removal", "counterspell"), (7, 12)),
    DeckPackage("draw", ("draw",), (5, 9)),
)


@dataclass(frozen=True)
class DeckSettings:
    commander_name: str | None = None  # None means random
    land_range: tuple[int, int] = (34, 40)
    seed: int | None = None
    include_banned: bool = False
    excluded_cards: frozenset[str] = frozenset()
    packages: tuple[DeckPackage, ...] = DEFAULT_PACKAGES
    synergy_percent: float = 0.4

    def __post_init__(self) -> None:
        low, high = self.land_range
        if not 0 <= low <= high <= 99:
            raise ValueError("land_range must be ordered and between 0 and 99")
        if self.commander_name is not None and not self.commander_name.strip():
            raise ValueError("commander_name cannot be blank")
        if not isfinite(self.synergy_percent) or not 0 <= self.synergy_percent <= 1:
            raise ValueError("synergy_percent must be between 0 and 1")
        roles = [package.role for package in self.packages]
        if len(roles) != len(set(roles)):
            raise ValueError("Package roles must be unique")


@dataclass(frozen=True)
class PackageAllocation:
    role: str
    target: int

    def __post_init__(self) -> None:
        if not self.role or self.target < 0:
            raise ValueError("Package allocation requires a role and nonnegative target")


@dataclass(frozen=True)
class DeckPlan:
    land_slots: int
    commander_count: int = 1
    allocations: tuple[PackageAllocation, ...] = ()
    synergy_slots: int = 0

    def __post_init__(self) -> None:
        if self.commander_count not in (1, 2):
            raise ValueError("A deck must have one or two commanders")
        if not 0 <= self.land_slots <= self.mainboard_slots:
            raise ValueError("land_slots exceeds the available mainboard slots")
        roles = [allocation.role for allocation in self.allocations]
        if len(roles) != len(set(roles)):
            raise ValueError("Package allocation roles must be unique")
        if (
            self.synergy_slots < 0
            or self.package_slots + self.synergy_slots > self.nonland_slots
        ):
            raise ValueError(
                "Package and synergy targets exceed available nonland slots"
            )

    @property
    def mainboard_slots(self) -> int:
        return 100 - self.commander_count

    @property
    def nonland_slots(self) -> int:
        return self.mainboard_slots - self.land_slots

    @property
    def package_slots(self) -> int:
        return sum(allocation.target for allocation in self.allocations)

    @property
    def misc_slots(self) -> int:
        return self.nonland_slots - self.package_slots - self.synergy_slots

@dataclass(frozen=True)
class DeckEntry:
    oracle_id: str
    slot: Slot
    role: str
    quantity: int = 1

    def __post_init__(self) -> None:
        if not self.oracle_id:
            raise ValueError("oracle_id cannot be empty")
        if self.slot not in ("land", "nonland"):
            raise ValueError("slot must be 'land' or 'nonland'")
        if not self.role:
            raise ValueError("role cannot be empty")
        if self.quantity < 1:
            raise ValueError("quantity must be positive")


@dataclass
class Deck:
    commanders: tuple[str, ...]
    entries: list[DeckEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.commanders) not in (1, 2):
            raise ValueError("A deck must have one or two commanders")
        if len(set(self.commanders)) != len(self.commanders):
            raise ValueError("A commander cannot be listed twice")

    def add(
        self,
        oracle_id: str,
        *,
        slot: Slot,
        role: str,
        quantity: int = 1,
    ) -> None:
        if oracle_id in self.commanders:
            raise ValueError("A commander cannot also be in the mainboard")
        self.entries.append(DeckEntry(oracle_id, slot, role, quantity))

    @property
    def mainboard_count(self) -> int:
        return sum(entry.quantity for entry in self.entries)

    @property
    def land_count(self) -> int:
        return sum(
            entry.quantity
            for entry in self.entries
            if entry.slot == "land"
        )

    @property
    def nonland_count(self) -> int:
        return self.mainboard_count - self.land_count

    @property
    def total_count(self) -> int:
        return len(self.commanders) + self.mainboard_count

    def quantities(self) -> Counter[str]:
        counts: Counter[str] = Counter()
        for entry in self.entries:
            counts[entry.oracle_id] += entry.quantity
        return counts
