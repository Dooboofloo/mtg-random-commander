"""Offline mutation tests for the independent M9 deck auditor."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from mtg_random_commander.models import Deck, DeckPlan, PackageAllocation
from scripts.audit_integration import (
    _can_command,
    _fits_slot,
    check_deck,
    check_export,
    deck_digest,
    select_random_commanders,
    write_reports,
)


@dataclass(frozen=True)
class Face:
    types: frozenset[str]
    supertypes: frozenset[str] = frozenset()
    subtypes: frozenset[str] = frozenset()
    oracle_text: str = ""
    power: str | None = None
    toughness: str | None = None


def card(cid, name, types, *, supertypes=(), colors=(), layout="normal", back=None):
    faces = (Face(frozenset(types), frozenset(supertypes)),)
    if back is not None:
        faces += (Face(frozenset(back)),)
    return SimpleNamespace(
        oracle_id=cid,
        name=name,
        faces=faces,
        layout=layout,
        color_identity=frozenset(colors),
    )


class FakeDB:
    def __init__(self):
        self.cards = {
            "cmd": card("cmd", "Commander", {"Creature"}, supertypes={"Legendary"}, colors={"W"}),
            "basic": card("basic", "Plains", {"Land"}, supertypes={"Basic"}),
            "spell": card("spell", "White Spell", {"Instant"}, colors={"W"}),
            "blue": card("blue", "Blue Spell", {"Instant"}, colors={"U"}),
            "modal": card("modal", "Modal Spell // Modal Land", {"Sorcery"}, layout="modal_dfc", back={"Land"}, colors={"W"}),
            "transform": card("transform", "Human // Land Back", {"Creature"}, layout="transform", back={"Land"}),
        }
        self.status = {cid: "legal" for cid in self.cards}

    def __getitem__(self, cid):
        return self.cards[cid]

    def legalities_for(self, cid):
        return (SimpleNamespace(format="commander", status=self.status[cid]),)


def make_deck(db, *, spell="spell", amount=1, slot="nonland"):
    deck = Deck(commanders=("cmd",))
    deck.add(spell, slot=slot, role="misc" if slot == "nonland" else "nonbasic-land", quantity=amount)
    deck.add("basic", slot="land", role="basic-land", quantity=99 - amount)
    return deck, DeckPlan(land_slots=99 - amount + (amount if slot == "land" else 0))


def codes(issues):
    return {issue.code for issue in issues}


def test_legal_deck_and_export():
    db = FakeDB()
    deck, plan = make_deck(db)
    assert check_deck(db, deck, plan) == []
    assert check_export(db, deck, ["98 Plains", "1 White Spell", "", "// COMMANDER", "1 Commander"]) == []


def test_color_and_ban_checks_are_independent():
    db = FakeDB()
    deck, plan = make_deck(db, spell="blue")
    assert "color-identity" in codes(check_deck(db, deck, plan))
    db.status["blue"] = "banned"
    assert "commander-legality" in codes(check_deck(db, deck, plan))
    assert "commander-legality" not in codes(check_deck(db, deck, plan, include_banned=True))
    assert "excluded-card" in codes(check_deck(db, deck, plan, excluded_ids=frozenset({"blue"})))


def test_duplicate_nonbasic_and_wrong_slot():
    db = FakeDB()
    deck, plan = make_deck(db, amount=2)
    assert "duplicate-oracle-id" in codes(check_deck(db, deck, plan))
    deck, plan = make_deck(db, spell="transform", slot="land")
    assert "wrong-slot" in codes(check_deck(db, deck, plan))


def test_modal_dfc_is_eligible_for_either_slot():
    db = FakeDB()
    assert _fits_slot(db["modal"], "land")
    assert _fits_slot(db["modal"], "nonland")
    assert not _fits_slot(db["transform"], "land")
    deck, plan = make_deck(db, spell="modal", slot="land")
    assert check_deck(db, deck, plan) == []


def test_invalid_commander_and_wrong_card_count():
    db = FakeDB()
    db.cards["cmd"] = card("cmd", "Not Legendary", {"Creature"})
    deck, plan = make_deck(db)
    assert "ineligible-commander" in codes(check_deck(db, deck, plan))
    deck.entries.pop()
    assert "deck-size" in codes(check_deck(db, deck, plan))


def test_roles_and_allocation_limits():
    db = FakeDB()
    deck, plan = make_deck(db)
    plan = DeckPlan(land_slots=98, allocations=(PackageAllocation("draw", 0),))
    deck.entries[0] = type(deck.entries[0])("spell", "nonland", "draw", 1)
    assert "package-overflow" in codes(check_deck(db, deck, plan))


def test_export_detects_mismatched_quantities_and_missing_marker():
    db = FakeDB()
    deck, _ = make_deck(db)
    assert "export-main" in codes(check_export(db, deck, ["99 Plains", "", "// COMMANDER", "1 Commander"]))
    assert "export-marker" in codes(check_export(db, deck, ["99 Plains", "1 Commander"]))


def test_digest_changes_when_role_or_card_changes():
    db = FakeDB()
    first, plan = make_deck(db)
    second, _ = make_deck(db, spell="blue")
    assert deck_digest(first, plan) == deck_digest(first, plan)
    assert deck_digest(first, plan) != deck_digest(second, plan)


def test_commander_sampling_stratifies_and_repeats():
    db = FakeDB()
    db.cards["five"] = card("five", "Five Color", {"Creature"}, supertypes={"Legendary"}, colors={"W", "U", "B", "R", "G"})
    db.cards["zero"] = card("zero", "Colorless", {"Creature"}, supertypes={"Legendary"})
    chosen = select_random_commanders(db, frozenset({"cmd", "five", "zero"}), 8, 42)
    assert len(chosen) == 8
    assert set(chosen) == {"cmd", "five", "zero"}
    assert chosen == select_random_commanders(db, frozenset({"cmd", "five", "zero"}), 8, 42)


def test_report_writers_roundtrip(tmp_path):
    report = {"decks": [{"index": 1, "commander": "Test", "status": "PASS", "issues": []}], "summary": {"failing_decks": 0}}
    json_file, csv_file = tmp_path / "audit.json", tmp_path / "audit.csv"
    write_reports(report, json_file, csv_file)
    assert '"failing_decks": 0' in json_file.read_text(encoding="utf-8")
    assert "commander" in csv_file.read_text(encoding="utf-8")


def test_front_face_commander_rule():
    unknown = card("c", "Nonlegend", {"Planeswalker"})
    assert not _can_command(unknown)
    vehicle = SimpleNamespace(
        oracle_id="v", name="Legendary Vehicle",
        faces=(Face(frozenset({"Artifact"}), frozenset({"Legendary"}), frozenset({"Vehicle"})),),
        color_identity=frozenset(), layout="normal",
    )
    assert _can_command(vehicle)


def test_runner_records_replays_without_using_production_validator(monkeypatch):
    from scripts import audit_integration as audit

    class FixedPolicy:
        excluded_tags = ()

        def __init__(self, **kwargs):
            pass

        def commander_candidates(self, db):
            return frozenset({"cmd"})

    class RunnerDB(FakeDB):
        def by_name(self, name):
            return frozenset({"cmd"}) if name == "Commander" else frozenset()

        def info(self):
            return SimpleNamespace(schema_version=1, created_at="now")

    calls = []

    def fake_build(db, settings, *, rng):
        calls.append(settings.seed)
        return make_deck(db)

    monkeypatch.setattr(audit, "CardPolicy", FixedPolicy)
    monkeypatch.setattr(audit, "build_deck", fake_build)

    report = audit.run_audit(
        RunnerDB(), count=2, seed=42, replay_count=2, progress_every=1
    )
    assert report["summary"]["failing_decks"] == 0
    assert report["summary"]["replayed_decks"] == 2
    assert len(calls) == 4
    assert calls[0] == calls[1]
    assert calls[2] == calls[3]
