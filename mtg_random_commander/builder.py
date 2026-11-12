"""Minimal Commander generator: legal spells plus basic lands.

Composition packages, synergy, nonbasics, and MDFC land
accounting are deferred.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from random import Random
from typing import TYPE_CHECKING

from .models import Deck, DeckPlan, DeckSettings
from .policy import CardPolicy, can_be_commander

if TYPE_CHECKING:
    from mtg_carddb import CardDatabase


BASICS = {
    "W": "Plains",
    "U": "Island",
    "B": "Swamp",
    "R": "Mountain",
    "G": "Forest",
}


def _choose_commander(
    db: CardDatabase,
    policy: CardPolicy,
    name: str | None,
    rng: Random,
    *,
    candidates: frozenset[str] | None = None,
) -> str:
    if name is not None:
        matches = sorted(
            cid
            for cid in db.by_name(name)
            if policy.allows_card(db, cid)
            and can_be_commander(db[cid])
        )

        if not matches:
            raise ValueError(
                f"No eligible commander named {name!r}"
            )

        if len(matches) != 1:
            choices = ", ".join(
                db[cid].name for cid in matches
            )
            raise ValueError(
                f"Ambiguous commander {name!r}: {choices}"
            )

        return matches[0]

    if candidates is None:
        candidates = policy.commander_candidates(db)

    if not candidates:
        raise ValueError("No eligible commanders in the database")

    return rng.choice(sorted(candidates))


def _basic_land_id(
    db: CardDatabase,
    legal_pool: frozenset[str],
    name: str,
) -> str:
    matches = (
        db.by_name(name)
        & db.by_supertype("Basic")
        & db.by_type("Land")
        & legal_pool
    )

    if len(matches) != 1:
        raise ValueError(
            f"Expected one eligible basic land named "
            f"{name!r}, found {len(matches)}"
        )

    return next(iter(matches))


def validate_deck(
    db: CardDatabase,
    deck: Deck,
    plan: DeckPlan,
    policy: CardPolicy,
) -> None:
    """Validate a single-commander deck with basic-land duplicates."""

    if len(deck.commanders) != 1 or plan.commander_count != 1:
        raise ValueError(
            "Only single-commander decks are supported"
        )

    commander_id = deck.commanders[0]

    if (
        commander_id not in policy.eligible_cards(db)
        or not can_be_commander(db[commander_id])
    ):
        raise ValueError("Commander is not eligible")

    if (
        deck.total_count != 100
        or deck.mainboard_count != plan.mainboard_slots
    ):
        raise ValueError("Incorrect deck size")

    if (
        deck.land_count != plan.land_slots
        or deck.nonland_count != plan.nonland_slots
    ):
        raise ValueError(
            "Land/nonland slot counts do not match the plan"
        )

    legal = policy.cards_for_commanders(db, deck.commanders)
    basics = db.by_supertype("Basic") & db.by_type("Land")

    for cid, quantity in deck.quantities().items():
        if cid not in legal:
            raise ValueError(
                f"Illegal mainboard card: {db[cid].name}"
            )

        if quantity > 1 and cid not in basics:
            raise ValueError(
                f"Illegal duplicate: {db[cid].name}"
            )

    for entry in deck.entries:
        if (
            entry.slot == "land"
            and entry.oracle_id not in db.by_type("Land")
        ):
            raise ValueError(
                f"Land slot contains a nonland: "
                f"{db[entry.oracle_id].name}"
            )

def build_deck(
    db: CardDatabase,
    settings: DeckSettings,
    *,
    rng: Random | None = None,
    on_progress: Callable[[str], None] | None = None,
    commander_candidates: frozenset[str] | None = None,
) -> tuple[Deck, DeckPlan]:
    """Generate a single-commander deck with an all-basic mana base."""

    rng = rng if rng is not None else Random(settings.seed)

    policy = CardPolicy(
        include_banned=settings.include_banned,
        excluded_cards=settings.excluded_cards,
    )

    if on_progress:
        on_progress("1/5 - Choosing commander...")

    commander_id = _choose_commander(
        db,
        policy,
        settings.commander_name,
        rng,
        candidates=commander_candidates,
    )

    plan = DeckPlan(
        land_slots=rng.randint(*settings.land_range)
    )

    deck = Deck(commanders=(commander_id,))

    if on_progress:
        on_progress("2/5 - Finding eligible cards...")

    legal = policy.cards_for_commanders(
        db,
        deck.commanders,
    )

    if on_progress:
        on_progress("3/5 - Selecting nonland cards...")

    # Exclude every card with a Land face for now.
    spell_pool = sorted(legal - db.by_type("Land"))

    if len(spell_pool) < plan.nonland_slots:
        raise ValueError(
            f"Only {len(spell_pool)} eligible nonlands, "
            f"need {plan.nonland_slots}"
        )

    for cid in rng.sample(spell_pool, plan.nonland_slots):
        deck.add(
            cid,
            slot="nonland",
            role="misc",
        )

    # Basics: distribute approximately evenly across colors.
    if on_progress:
        on_progress("4/5 - Allocating basic lands...")

    colors = db[commander_id].color_identity

    land_names = [
        name
        for color, name in BASICS.items()
        if color in colors
    ]

    if not land_names:
        land_names = ["Wastes"]

    each, remainder = divmod(
        plan.land_slots,
        len(land_names),
    )

    quantities = Counter({
        name: each for name in land_names
    })

    quantities.update(
        rng.sample(land_names, remainder)
    )

    for name in sorted(quantities):
        quantity = quantities[name]

        if quantity:
            cid = _basic_land_id(db, legal, name)

            deck.add(
                cid,
                slot="land",
                role="basic-land",
                quantity=quantity,
            )

    if on_progress:
        on_progress("5/5 - Validating deck...")

    validate_deck(db, deck, plan, policy)

    return deck, plan
