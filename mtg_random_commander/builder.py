"""Commander generator with functional packages and basic lands.

Synergy, nonbasic lands, and MDFC land accounting are deferred.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from random import Random
from typing import TYPE_CHECKING

from .models import Deck, DeckPlan, DeckSettings
from .packages import fill_packages, roll_allocations
from .policy import CardPolicy, can_be_commander
from .synergy import fill_synergy

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

    role_counts = Counter()
    for entry in deck.entries:
        if entry.slot == "nonland":
            role_counts[entry.role] += entry.quantity
    for allocation in plan.allocations:
        if role_counts[allocation.role] > allocation.target:
            raise ValueError(
                f"Package {allocation.role!r} exceeds its planned target"
            )

    if role_counts["synergy"] > plan.synergy_slots:
        raise ValueError("Synergy exceeds its planned target")
    
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
    """Generate a single-commander deck with functional packages and synergy."""

    rng = rng if rng is not None else Random(settings.seed)

    policy = CardPolicy(
        include_banned=settings.include_banned,
        excluded_cards=settings.excluded_cards,
    )

    if on_progress:
        on_progress("1/6 - Choosing commander...")

    commander_id = _choose_commander(
        db,
        policy,
        settings.commander_name,
        rng,
        candidates=commander_candidates,
    )

    land_slots = rng.randint(*settings.land_range)

    allocations = roll_allocations(
        settings.packages,
        99 - land_slots,
        rng,
    )

    remaining = 99 - land_slots - sum(
        allocation.target for allocation in allocations
    )

    plan = DeckPlan(
        land_slots=land_slots,
        allocations=allocations,
        synergy_slots=int(
            remaining * settings.synergy_percent
        ),
    )

    deck = Deck(commanders=(commander_id,))

    if on_progress:
        on_progress("2/6 - Finding eligible cards...")

    legal = policy.cards_for_commanders(
        db,
        deck.commanders,
    )

    if on_progress:
        on_progress("3/6 - Selecting functional packages...")

    # Cards with any Land face remain excluded for now.
    spell_pool = sorted(
        legal - db.by_type("Land")
    )

    if len(spell_pool) < plan.nonland_slots:
        raise ValueError(
            f"Only {len(spell_pool)} eligible nonlands, "
            f"need {plan.nonland_slots}"
        )

    available = set(spell_pool)

    fill_packages(
        db,
        deck,
        settings.packages,
        plan.allocations,
        available,
        rng,
    )

    if on_progress:
        on_progress("4/6 - Selecting commander synergies...")

    fill_synergy(
        db,
        deck,
        commander_id,
        available,
        plan.synergy_slots,
        rng,
    )

    # Unfilled functional and synergy allocations
    # become miscellaneous slots.
    remaining = plan.nonland_slots - deck.nonland_count

    for cid in rng.sample(sorted(available), remaining):
        deck.add(
            cid,
            slot="nonland",
            role="misc",
        )

    if on_progress:
        on_progress("5/6 - Allocating basic lands...")

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
            cid = _basic_land_id(
                db,
                legal,
                name,
            )

            deck.add(
                cid,
                slot="land",
                role="basic-land",
                quantity=quantity,
            )

    if on_progress:
        on_progress("6/6 - Validating deck...")

    validate_deck(
        db,
        deck,
        plan,
        policy,
    )

    return deck, plan
