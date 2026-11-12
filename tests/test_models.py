import pytest

from mtg_random_commander.models import Deck, DeckPlan, DeckSettings


def test_deck_plan_reserves_commander_slot():
    plan = DeckPlan(land_slots=37)

    assert plan.mainboard_slots == 99
    assert plan.nonland_slots == 62

    assert DeckPlan(
        land_slots=37,
        commander_count=2
    ).nonland_slots == 61


@pytest.mark.parametrize(
    "lands",
    [(-1, 40), (41, 40), (34, 100)]
)
def test_invalid_land_settings(lands):
    with pytest.raises(ValueError):
        DeckSettings(land_range=lands)


def test_invalid_plan():
    with pytest.raises(ValueError):
        DeckPlan(land_slots=99, commander_count=2)


def test_deck_tracks_slots_roles_and_quantities():
    deck = Deck(commanders=("commander-id",))

    deck.add(
        "land-id",
        slot="land",
        role="mana-base",
        quantity=5,
    )

    deck.add("spell-id", slot="nonland", role="ramp")
    deck.add("spell-id", slot="nonland", role="synergy")

    assert deck.land_count == 5
    assert deck.nonland_count == 2
    assert deck.total_count == 8

    assert deck.quantities() == {
        "land-id": 5,
        "spell-id": 2,
    }


def test_commander_cannot_be_in_mainboard():
    deck = Deck(commanders=("commander-id",))

    with pytest.raises(ValueError):
        deck.add(
            "commander-id",
            slot="nonland",
            role="misc",
        )

def test_synergy_targets_are_bounded():
    from mtg_random_commander.models import (
        DeckPackage,
        PackageAllocation,
    )

    with pytest.raises(
        ValueError,
        match="synergy_percent",
    ):
        DeckSettings(
            synergy_percent=float("nan")
        )

    with pytest.raises(
        ValueError,
        match="Package and synergy targets",
    ):
        DeckPlan(
            land_slots=37,
            allocations=(
                PackageAllocation("ramp", 30),
            ),
            synergy_slots=33,
        )

    with pytest.raises(
        ValueError,
        match="reserved role",
    ):
        DeckPackage(
            "synergy",
            ("draw",),
            (3, 5),
        )

def test_land_settings_are_bounded():
    assert DeckSettings(nonbasic_fraction=None).nonbasic_fraction is None
    assert DeckSettings(nonbasic_fraction=0).nonbasic_fraction == 0
    assert DeckSettings(nonbasic_fraction=1).nonbasic_fraction == 1

    for bad in (-0.1, 1.1, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="nonbasic_fraction"):
            DeckSettings(nonbasic_fraction=bad)

        with pytest.raises(ValueError, match="snow_chance"):
            DeckSettings(snow_chance=bad)