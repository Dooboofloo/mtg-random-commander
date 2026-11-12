"""Functional package allocation and card selection."""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING

from .models import Deck, DeckPackage, PackageAllocation

if TYPE_CHECKING:
    from mtg_carddb import CardDatabase


def roll_allocations(
    packages: tuple[DeckPackage, ...],
    nonland_slots: int,
    rng: Random,
) -> tuple[PackageAllocation, ...]:
    """Roll each configured package target before selecting any cards."""
    allocations = tuple(
        PackageAllocation(package.role, rng.randint(*package.count_range))
        for package in packages
    )
    total = sum(allocation.target for allocation in allocations)
    if total > nonland_slots:
        raise ValueError(
            f"Package targets require {total} nonland slots; "
            f"only {nonland_slots} are available"
        )
    return allocations


def fill_packages(
    db: CardDatabase,
    deck: Deck,
    packages: tuple[DeckPackage, ...],
    allocations: tuple[PackageAllocation, ...],
    available: set[str],
    rng: Random,
) -> None:
    """Select each package from eligible, unselected nonland cards.

    If a tag pool is too small, the missing slots remain available
    to the caller's miscellaneous fill.
    """
    definitions = {package.role: package for package in packages}

    for allocation in allocations:
        if allocation.target == 0:
            continue

        package = definitions[allocation.role]
        tagged: set[str] = set()
        for slug in package.tags:
            tagged.update(db.by_tag(slug))

        choices = sorted(available & tagged)
        take = min(allocation.target, len(choices))
        chosen = rng.sample(choices, take)

        for cid in chosen:
            deck.add(cid, slot="nonland", role=package.role)
        available.difference_update(chosen)
