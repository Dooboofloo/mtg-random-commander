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
