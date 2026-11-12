"""Randomized mana bases, including modal DFCs and basic-land balancing."""

from __future__ import annotations

from collections import Counter
from random import Random
import re
from typing import TYPE_CHECKING

from .models import Deck
from .synergy import get_synergy_packages

if TYPE_CHECKING:
    from mtg_carddb import Card, CardDatabase


BASICS = {
    "W": "Plains",
    "U": "Island",
    "B": "Swamp",
    "R": "Mountain",
    "G": "Forest",
}
COLORS = "WUBRG"
LAND_TYPES = frozenset(BASICS.values())
MANA_SYMBOL = re.compile(r"\{([^{}]+)\}")
FETCH_TEXT = re.compile(
    r"search your library for (?:up to )?(?:a|an|one|two) "
    r"(?:basic )?((?:(?:Plains|Island|Swamp|Mountain|Forest)"
    r"(?: or | and |, |, or |, and )?)+) card",
    re.IGNORECASE,
)
TYPE_WORD = re.compile(
    r"\b(?:Plains|Island|Swamp|Mountain|Forest)\b",
    re.IGNORECASE,
)


def slot_eligible(card: Card, slot: str) -> bool:
    """Use playable faces; modal land/spell DFCs qualify for both."""
    playable = (
        card.faces
        if card.layout == "modal_dfc"
        else card.faces[:1]
    )

    if slot == "land":
        return any(
            "Land" in face.types for face in playable
        )

    if slot == "nonland":
        return any(
            "Land" not in face.types for face in playable
        )

    raise ValueError(f"Unknown slot: {slot}")


def candidate_pools(
    db: CardDatabase,
    legal: frozenset[str],
) -> tuple[set[str], set[str]]:
    """Return land/nonland Oracle IDs; modal DFCs may occur in both."""
    any_land = legal & db.by_type("Land")

    land = set()
    spell = set(legal - any_land)

    for cid in any_land:
        card = db[cid]

        if slot_eligible(card, "land"):
            land.add(cid)

        if slot_eligible(card, "nonland"):
            spell.add(cid)

    return land, spell


def mana_demand(db: CardDatabase, deck: Deck) -> Counter[str]:
    """Count colored symbols of playable nonland faces, including commander."""
    demand: Counter[str] = Counter()

    ids = set(deck.commanders) | {
        entry.oracle_id
        for entry in deck.entries
        if entry.slot == "nonland"
    }

    for cid in sorted(ids):
        card = db[cid]
        faces = (
            card.faces
            if card.layout == "modal_dfc"
            else card.faces[:1]
        )

        for face in faces:
            if "Land" in face.types:
                continue

            for symbol in MANA_SYMBOL.findall(face.mana_cost or ""):
                colors = set(symbol.upper()) & set(COLORS)

                # Hybrid symbols share their weight.
                # Phyrexian {G/P} counts as green.
                for color in sorted(colors):
                    demand[color] += 1 / len(colors)

    return demand


def _basic_id(
    db: CardDatabase,
    legal: frozenset[str],
    name: str,
) -> str:
    ids = (
        db.by_name(name)
        & db.by_supertype("Basic")
        & db.by_type("Land")
        & legal
    )

    ids = {
        cid for cid in ids
        if db[cid].name == name
    }

    if len(ids) != 1:
        raise ValueError(
            f"Expected one eligible basic named "
            f"{name!r}; found {len(ids)}"
        )

    return next(iter(ids))


def _fetch_types(card: Card) -> frozenset[str]:
    """Basic land types a typed fetch can search for."""
    text = card.faces[0].oracle_text or ""
    match = FETCH_TEXT.search(text)

    if not match:
        return frozenset()

    return frozenset(
        word.title()
        for word in TYPE_WORD.findall(match.group(1))
    )


def _nonbasic_fraction(color_count: int, rng: Random) -> float:
    bounds = {
        0: (0.25, 0.45),
        1: (0.20, 0.40),
        2: (0.40, 0.60),
        3: (0.50, 0.70),
        4: (0.55, 0.75),
        5: (0.60, 0.80),
    }
    return rng.uniform(*bounds[color_count])


def _weighted_sample(
    ids: set[str],
    weights: dict[str, float],
    count: int,
    rng: Random,
) -> list[str]:
    """Weighted selection without replacement, stable under a fixed seed."""
    chosen: list[str] = []
    available = sorted(ids)

    for _ in range(min(count, len(available))):
        selection = rng.choices(
            available,
            weights=[weights[cid] for cid in available],
        )[0]
        chosen.append(selection)
        available.remove(selection)

    return chosen


def build_mana_base(
    db: CardDatabase,
    deck: Deck,
    legal: frozenset[str],
    land_pool: set[str],
    land_slots: int,
    rng: Random,
    *,
    nonbasic_fraction: float | None = None,
    snow_chance: float = 0.055,
) -> None:
    """Fill land slots with nonbasics and pip-weighted basics."""
    commander = db[deck.commanders[0]]
    colors = [
        color for color in COLORS
        if color in commander.color_identity
    ]

    fraction = (
        nonbasic_fraction
        if nonbasic_fraction is not None
        else _nonbasic_fraction(len(colors), rng)
    )

    target = round(land_slots * fraction)

    # Do not duplicate MDFCs already selected as spells.
    used = set(deck.quantities()) | set(deck.commanders)
    basics = db.by_supertype("Basic") & db.by_type("Land")
    candidates = set(land_pool - basics - used)

    synergies: set[str] = set()
    weights: dict[str, float] = {}
    chosen: list[str] = []

    if target and candidates:
        for package in get_synergy_packages(
            db, deck.commanders[0]
        ):
            synergies.update(package.pool)

        fixing = set()
        for color in colors:
            fixing.update(db.produces_mana(color))

        for cid in candidates:
            card = db[cid]
            produced = (
                set(card.produced_mana or ())
                & set(colors)
            )

            weights[cid] = (
                1.0
                + (1.5 if cid in fixing else 0)
                + 0.8 * max(0, len(produced) - 1)
                + (3.0 if cid in synergies else 0)
            )

        chosen = _weighted_sample(
            candidates, weights, target, rng
        )

    # Reject typed fetchlands with no targets in the mana base.
    def targets() -> set[str]:
        guaranteed_basics = colors[
            :max(0, land_slots - len(chosen))
        ]
        actual_basics = {
            BASICS[color] for color in guaranteed_basics
        }

        return actual_basics | {
            subtype
            for cid in chosen
            for subtype in db[cid].subtypes
            if subtype in LAND_TYPES
        }

    for cid in list(chosen):
        types = _fetch_types(db[cid])

        if types and not types & targets():
            chosen.remove(cid)

            alternatives = candidates - set(chosen) - {cid}

            usable = {
                other for other in alternatives
                if not _fetch_types(db[other])
                or _fetch_types(db[other]) & targets()
            }

            if usable:
                chosen.extend(
                    _weighted_sample(
                        usable, weights, 1, rng
                    )
                )

    for cid in chosen:
        role = (
            "synergy-land"
            if cid in synergies
            else "nonbasic-land"
        )
        deck.add(cid, slot="land", role=role)

    basic_slots = land_slots - len(chosen)

    if not basic_slots:
        return

    snowy = bool(colors) and (
        "Snow" in commander.supertypes
        or any(
            "snow" in tagging.tag_slug
            for tagging in db.taggings_for(
                deck.commanders[0]
            )
        )
        or rng.random() < snow_chance
    )

    if not colors:
        deck.add(
            _basic_id(db, legal, "Wastes"),
            slot="land",
            role="basic-land",
            quantity=basic_slots,
        )
        return

    demand = mana_demand(db, deck)

    # Guarantee one of each appropriate basic type when possible.
    counts: Counter[str] = Counter()

    for color in colors[:basic_slots]:
        counts[color] += 1

    remaining = basic_slots - sum(counts.values())

    if remaining:
        weights = [
            max(demand[color], 0.25)
            for color in colors
        ]

        counts.update(
            rng.choices(
                colors,
                weights=weights,
                k=remaining,
            )
        )

    for color in colors:
        if counts[color]:
            name = (
                ("Snow-Covered " if snowy else "")
                + BASICS[color]
            )

            deck.add(
                _basic_id(db, legal, name),
                slot="land",
                role="basic-land",
                quantity=counts[color],
            )
