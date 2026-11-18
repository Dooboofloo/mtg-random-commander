"""Commander deck eligibility rules, separate from CardDB's card facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mtg_carddb import Card, CardDatabase


GRIST_ORACLE_ID = "0efb0d7e-dea0-4817-a243-15066e9ef333"

# Additional user exclusions can be supplied.
DEFAULT_HOUSE_BANS = frozenset({
    # Legendary banding lands
    "bf29b215-d4f5-4641-97ef-b65d4c463e72",
    "4b9922b9-c5b5-467e-8a5b-1e45e862194d",
    "af147bb6-aa46-4fc9-af96-de3740c19fd5",
    "f71f01bc-caae-426b-a25a-bfbfeb9feb67",
    "d410027b-1c22-461e-939d-06a2c851352e",

    # Shahrazad
    "fc04f621-338b-4d4c-bf57-5e5a00d990f0",

    # Wish-only cards
    "13a884b5-8970-4d71-9082-a8b6c8db9a01",  # Burning Wish
    "bdf80a55-b524-4d17-9be8-a0005403a0e7",  # Cunning Wish
    "1f47c869-f4a9-43b0-aec0-8da4e3a3fec5",  # Extrapolate the Impossible
    "45c29ac0-f9ca-4ab9-b93e-8b678509bcd7",  # Glittering Wish
    "e5f25cbd-39e4-4806-8dba-9a552356696d",  # Golden Wish
    "b9d186f5-1c92-4539-a5b5-e7fbd4b726fe",  # Living Wish
    "c79b9187-cbfe-43a0-bdc8-4f7e0d215607",  # Ring of Ma'rûf
    "2ccbf0ee-c856-4f67-8579-811fe8571a2e",  # Wish
})


def can_be_commander(card: Card) -> bool:
    """Determine commander eligibility from the front face."""

    if card.oracle_id == GRIST_ORACLE_ID:
        return True

    front = card.faces[0]
    text = (front.oracle_text or "").casefold()

    if "can be your commander" in text:
        return True

    if "Legendary" not in front.supertypes:
        return False

    if "Creature" in front.types or "Vehicle" in front.subtypes:
        return True

    return (
        "Spacecraft" in front.subtypes
        and front.power is not None
        and front.toughness is not None
    )


@dataclass(frozen=True)
class CardPolicy:
    include_banned: bool = False
    excluded_cards: frozenset[str] = frozenset()
    excluded_tags: tuple[str, ...] = ("draft-matters", "ante-matters", "dexterity",)

    def eligible_cards(self, db: CardDatabase) -> frozenset[str]:
        """Eligible cards before commander color-identity filtering."""

        pool = db.by_legality("commander", "legal")

        if self.include_banned:
            pool |= db.by_legality("commander", "banned")

        excluded = (
            db.by_subtype("Attraction")
            | db.by_type("Stickers")
            | db.by_type("Conspiracy")
            | DEFAULT_HOUSE_BANS
            | self.excluded_cards
        )

        for slug in self.excluded_tags:
            excluded |= db.by_tag(slug)

        return frozenset(pool - excluded)

    def allows_card(
        self,
        db: CardDatabase,
        oracle_id: str,
    ) -> bool:
        """Check one card without hydrating bulk search indexes."""

        if (
            oracle_id in DEFAULT_HOUSE_BANS
            or oracle_id in self.excluded_cards
        ):
            return False

        card = db[oracle_id]

        if any(
            "Stickers" in face.types
            or "Conspiracy" in face.types
            or "Attraction" in face.subtypes
            for face in card.faces
        ):
            return False

        allowed_statuses = {"legal"}
        if self.include_banned:
            allowed_statuses.add("banned")

        if not any(
            legality.format == "commander"
            and legality.status in allowed_statuses
            for legality in db.legalities_for(oracle_id)
        ):
            return False

        # A requested exclusion also excludes cards tagged with a descendant.
        # CardDB v1.2 handles aliases and the ancestor walk without loading
        # the global tag index.
        if any(
            db.has_tag(oracle_id, slug, include_ancestors=True)
            for slug in self.excluded_tags
        ):
            return False

        return True

    def commander_candidates(
        self,
        db: CardDatabase,
        *,
        eligible_cards: frozenset[str] | None = None,
    ) -> frozenset[str]:
        """Eligible single-commander candidates."""

        possible = (
            db.by_type("Creature")
            | db.by_subtype("Vehicle")
            | db.by_subtype("Spacecraft")
            | db.by_type("Planeswalker")
        )

        eligible = self.eligible_cards(db) if eligible_cards is None else eligible_cards
        return frozenset(
            card.oracle_id
            for card in db.resolve(eligible & possible)
            if can_be_commander(card)
        )

    def cards_for_commanders(
        self,
        db: CardDatabase,
        commander_ids: tuple[str, ...],
        *,
        eligible_cards: frozenset[str] | None = None,
    ) -> frozenset[str]:
        """
        Eligible cards within the commanders' combined color identity.

        Does not validate whether multiple commanders can legally pair.
        """

        if not commander_ids:
            raise ValueError("At least one commander is required")

        if len(set(commander_ids)) != len(commander_ids):
            raise ValueError("Commander identities must be distinct")

        colors = set().union(
            *(db[cid].color_identity for cid in commander_ids)
        )

        eligible = self.eligible_cards(db) if eligible_cards is None else eligible_cards
        return frozenset(
            (
                eligible
                & db.within_identity("".join(sorted(colors)))
            )
            - set(commander_ids)
        )
