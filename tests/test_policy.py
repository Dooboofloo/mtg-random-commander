from dataclasses import dataclass

from mtg_random_commander.policy import CardPolicy, can_be_commander


@dataclass(frozen=True)
class FakeFace:
    supertypes: frozenset[str] = frozenset()
    types: frozenset[str] = frozenset()
    subtypes: frozenset[str] = frozenset()
    oracle_text: str | None = None
    power: str | None = None
    toughness: str | None = None


@dataclass(frozen=True)
class FakeCard:
    oracle_id: str
    faces: tuple[FakeFace, ...]
    color_identity: frozenset[str] = frozenset()


class FakeDB:
    def __init__(self, cards, *, legal, banned=frozenset(), tags=None):
        self.cards = cards
        self.legal = frozenset(legal)
        self.banned = frozenset(banned)
        self.tags = tags or {
            "draft-matters": frozenset(),
            "ante-matters": frozenset(),
            "dexterity": frozenset(),
        }

    def __getitem__(self, oracle_id):
        return self.cards[oracle_id]

    def resolve(self, oracle_ids):
        return tuple(
            self.cards[cid] for cid in sorted(oracle_ids)
        )

    def by_legality(self, name, status):
        assert name == "commander"
        return self.legal if status == "legal" else self.banned

    def by_type(self, name):
        return frozenset(
            cid for cid, card in self.cards.items()
            if any(name in face.types for face in card.faces)
        )

    def by_subtype(self, name):
        return frozenset(
            cid for cid, card in self.cards.items()
            if any(name in face.subtypes for face in card.faces)
        )

    def by_tag(self, name):
        return self.tags[name]

    def by_name(self, name):
        return frozenset()

    def within_identity(self, colors):
        return frozenset(
            cid for cid, card in self.cards.items()
            if card.color_identity <= set(colors)
        )


def face(
    *,
    legendary=False,
    types=(),
    subtypes=(),
    oracle_text=None,
    pt=None,
):
    return FakeFace(
        frozenset({"Legendary"} if legendary else ()),
        frozenset(types),
        frozenset(subtypes),
        oracle_text,
        pt[0] if pt else None,
        pt[1] if pt else None,
    )


def test_commander_uses_front_face_not_union():
    good = FakeCard(
        "good",
        (face(legendary=True, types=("Creature",)),),
    )

    back_only = FakeCard(
        "back",
        (
            face(types=("Artifact",)),
            face(legendary=True, types=("Creature",)),
        ),
    )

    vehicle = FakeCard(
        "vehicle",
        (
            face(
                legendary=True,
                types=("Artifact",),
                subtypes=("Vehicle",),
            ),
        ),
    )

    no_pt = FakeCard(
        "ship1",
        (
            face(
                legendary=True,
                types=("Artifact",),
                subtypes=("Spacecraft",),
            ),
        ),
    )

    pt = FakeCard(
        "ship2",
        (
            face(
                legendary=True,
                types=("Artifact",),
                subtypes=("Spacecraft",),
                pt=("4", "4"),
            ),
        ),
    )

    planeswalker = FakeCard(
        "pw",
        (
            face(
                legendary=True,
                types=("Planeswalker",),
                oracle_text="This can be your commander.",
            ),
        ),
    )

    for card in (good, vehicle, pt, planeswalker):
        assert can_be_commander(card)

    for card in (back_only, no_pt):
        assert not can_be_commander(card)


def test_policy_filters_by_legality_house_exclusions_and_identity():
    cards = {
        "cmd": FakeCard(
            "cmd",
            (face(legendary=True, types=("Creature",)),),
            frozenset("BG"),
        ),
        "green": FakeCard(
            "green",
            (face(types=("Creature",)),),
            frozenset("G"),
        ),
        "blue": FakeCard(
            "blue",
            (face(types=("Creature",)),),
            frozenset("U"),
        ),
        "draft": FakeCard(
            "draft",
            (face(types=("Artifact",)),),
        ),
        "banned": FakeCard(
            "banned",
            (face(types=("Creature",)),),
            frozenset("G"),
        ),
    }

    db = FakeDB(
        cards,
        legal={"cmd", "green", "blue", "draft"},
        banned={"banned"},
        tags={
            "draft-matters": frozenset({"draft"}),
            "ante-matters": frozenset(),
            "dexterity": frozenset(),
        },
    )

    policy = CardPolicy()

    assert policy.commander_candidates(db) == {"cmd"}

    assert policy.cards_for_commanders(
        db, ("cmd",)
    ) == {"green"}

    assert CardPolicy(
        include_banned=True
    ).cards_for_commanders(db, ("cmd",)) == {
        "green",
        "banned",
    }

def test_excluded_tags_override_include_banned():
    cards = {
        "ante": FakeCard("ante", (face(types=("Artifact",)),)),
        "dexterity": FakeCard("dexterity", (face(types=("Artifact",)),)),
        "ordinary": FakeCard("ordinary", (face(types=("Artifact",)),)),
    }

    db = FakeDB(
        cards,
        legal={"ordinary"},
        banned={"ante", "dexterity"},
        tags={
            "draft-matters": frozenset(),
            "ante-matters": frozenset({"ante"}),
            "dexterity": frozenset({"dexterity"}),
        },
    )

    policy = CardPolicy(include_banned=True)

    assert policy.eligible_cards(db) == {"ordinary"}


def test_stickers_and_attractions_are_excluded():
    cards = {
        "sticker": FakeCard(
            "sticker",
            (face(types=("Stickers",)),),
        ),
        "attraction": FakeCard(
            "attraction",
            (
                face(
                    types=("Artifact",),
                    subtypes=("Attraction",),
                ),
            ),
        ),
        "ordinary": FakeCard(
            "ordinary",
            (face(types=("Artifact",)),),
        ),
    }

    db = FakeDB(
        cards,
        legal=set(cards),
        tags={
            "draft-matters": frozenset(),
            "ante-matters": frozenset(),
            "dexterity": frozenset(),
        },
    )

    assert CardPolicy().eligible_cards(db) == {"ordinary"}
