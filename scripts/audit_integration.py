"""Independent, read-only integration audit of generated Commander decks.

The checker does not call validate_deck(), slot_eligible(), or
CardPolicy.cards_for_commanders(). It instead checks every selected Oracle ID
against CardDB's card faces, colors, legalities, and configured exclusions.

Run from the repository root:
    python scripts/audit_integration.py --count 300 --seed 42
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
from random import Random
import sys
from time import perf_counter
from typing import Any

# Allow `python scripts/audit_integration.py` from the repository root,
# matching the existing audit_synergy.py workflow.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mtg_random_commander.builder import build_deck
from mtg_random_commander.export import export_lines
from mtg_random_commander.models import DEFAULT_PACKAGES, DeckSettings
from mtg_random_commander.policy import (
    CardPolicy,
    DEFAULT_HOUSE_BANS,
    GRIST_ORACLE_ID,
)


@dataclass(frozen=True)
class Issue:
    code: str
    detail: str


def _can_command(card: Any) -> bool:
    """Independent front-face check for the supported single-commander rules."""
    if card.oracle_id == GRIST_ORACLE_ID:
        return True
    face = card.faces[0]
    if "can be your commander" in (face.oracle_text or "").casefold():
        return True
    return (
        "Legendary" in face.supertypes
        and (
            "Creature" in face.types
            or "Vehicle" in face.subtypes
            or (
                "Spacecraft" in face.subtypes
                and face.power is not None
                and face.toughness is not None
            )
        )
    )


def _fits_slot(card: Any, slot: str) -> bool:
    """Check castable faces, independent of lands.slot_eligible()."""
    faces = card.faces if card.layout == "modal_dfc" else card.faces[:1]
    if slot == "land":
        return any("Land" in face.types for face in faces)
    if slot == "nonland":
        return any("Land" not in face.types for face in faces)
    return False


def _is_basic_land(card: Any) -> bool:
    return any(
        "Basic" in face.supertypes and "Land" in face.types
        for face in card.faces[:1]
    )


def _legal_in_commander(db: Any, cid: str, include_banned: bool) -> bool:
    permitted = {"legal", "banned"} if include_banned else {"legal"}
    return any(
        entry.format == "commander" and entry.status in permitted
        for entry in db.legalities_for(cid)
    )


def check_deck(
    db: Any,
    deck: Any,
    plan: Any,
    *,
    include_banned: bool = False,
    excluded_ids: frozenset[str] = frozenset(),
    house_bans: frozenset[str] = DEFAULT_HOUSE_BANS,
) -> list[Issue]:
    """Audit a generated deck without consulting its production validator.

    excluded_ids contains IDs from forbidden tag descendants and additional
    caller exclusions. Basic lands are the only permitted duplicates, matching
    the application's deliberate current house rules.
    """
    issues: list[Issue] = []

    def problem(code: str, detail: str) -> None:
        issues.append(Issue(code, detail))

    commanders = tuple(deck.commanders)
    if len(commanders) != 1 or plan.commander_count != 1:
        problem("commander-count", f"Expected one commander; got {len(commanders)}")

    quantities: Counter[str] = Counter()
    roles: Counter[str] = Counter()
    land_slots = nonland_slots = 0
    allowed_roles = {allocation.role for allocation in plan.allocations}

    for entry in deck.entries:
        quantities[entry.oracle_id] += entry.quantity
        if not isinstance(entry.quantity, int) or entry.quantity < 1:
            problem("quantity", f"Invalid quantity on {entry.oracle_id}: {entry.quantity}")
        if entry.slot == "land":
            land_slots += entry.quantity
            if entry.role not in {"basic-land", "nonbasic-land", "synergy-land"}:
                problem("land-role", f"Unexpected land role {entry.role!r}")
        elif entry.slot == "nonland":
            nonland_slots += entry.quantity
            roles[entry.role] += entry.quantity
            if entry.role not in allowed_roles | {"synergy", "misc"}:
                problem("nonland-role", f"Unexpected nonland role {entry.role!r}")
        else:
            problem("slot", f"Unknown slot {entry.slot!r}")

    total = len(commanders) + sum(quantities.values())
    if total != 100 or sum(quantities.values()) != 99:
        problem("deck-size", f"Expected 100 cards (99 main), found {total}")
    if land_slots != plan.land_slots or nonland_slots != plan.nonland_slots:
        problem(
            "slot-count",
            f"Expected {plan.land_slots}/{plan.nonland_slots} land/nonland, "
            f"got {land_slots}/{nonland_slots}",
        )

    for allocation in plan.allocations:
        if roles[allocation.role] > allocation.target:
            problem(
                "package-overflow",
                f"{allocation.role}: {roles[allocation.role]} > {allocation.target}",
            )
    if roles["synergy"] > plan.synergy_slots:
        problem("synergy-overflow", f"{roles['synergy']} > {plan.synergy_slots}")

    card_cache: dict[str, Any] = {}
    for cid in set(quantities) | set(commanders):
        try:
            card_cache[cid] = db[cid]
        except (KeyError, LookupError) as exc:
            problem("missing-oracle-id", f"{cid}: {exc}")

    commander_colors: set[str] = set()
    for cid in commanders:
        card = card_cache.get(cid)
        if card is None:
            continue
        commander_colors.update(card.color_identity)
        if not _can_command(card):
            problem("ineligible-commander", card.name)

    # Verify both commander and mainboard against direct CardDB facts.
    for cid in set(quantities) | set(commanders):
        card = card_cache.get(cid)
        if card is None:
            continue
        if cid in house_bans or cid in excluded_ids:
            problem("excluded-card", f"{card.name} ({cid})")
        if not _legal_in_commander(db, cid, include_banned):
            problem("commander-legality", f"{card.name} ({cid})")
        for face in card.faces:
            if (
                "Stickers" in face.types
                or "Conspiracy" in face.types
                or "Attraction" in face.subtypes
            ):
                problem("unsupported-card", f"{card.name} ({cid})")
                break

    names: dict[str, list[str]] = defaultdict(list)
    for cid, quantity in quantities.items():
        card = card_cache.get(cid)
        if card is None:
            continue
        names[card.name].append(cid)
        if cid in commanders:
            problem("commander-in-main", card.name)
        if not set(card.color_identity) <= commander_colors:
            problem("color-identity", f"{card.name}: {sorted(card.color_identity)}")
        if quantity > 1 and not _is_basic_land(card):
            problem("duplicate-oracle-id", f"{quantity} x {card.name}")

    for name, ids in names.items():
        if len(ids) > 1 and not all(_is_basic_land(card_cache[cid]) for cid in ids):
            problem("duplicate-name", f"{name}: {', '.join(sorted(ids))}")

    for entry in deck.entries:
        card = card_cache.get(entry.oracle_id)
        if card is not None and not _fits_slot(card, entry.slot):
            problem("wrong-slot", f"{card.name} in {entry.slot} slot")
        if card is not None and entry.role == "basic-land" and not _is_basic_land(card):
            problem("nonbasic-as-basic", card.name)

    return issues


def check_export(db: Any, deck: Any, lines: list[str]) -> list[Issue]:
    """Independently parse the public text export and compare its card counts."""
    issues: list[Issue] = []
    if lines.count("// COMMANDER") != 1:
        return [Issue("export-marker", "Expected exactly one commander marker")]
    boundary = lines.index("// COMMANDER")
    if boundary == 0 or lines[boundary - 1] != "":
        issues.append(Issue("export-separator", "Missing blank line before marker"))

    def parse(rows: list[str], label: str) -> Counter[str]:
        result: Counter[str] = Counter()
        for row in rows:
            if not row.strip():
                if label == "commander":
                    issues.append(Issue("export-blank", "Blank commander line"))
                continue
            quantity_str, separator, name = row.partition(" ")
            if not separator or not name or not quantity_str.isdecimal():
                issues.append(Issue("export-format", f"Invalid {label} line: {row!r}"))
                continue
            quantity = int(quantity_str)
            if quantity < 1:
                issues.append(Issue("export-quantity", row))
            result[name] += quantity
        return result

    observed_main = parse(lines[:boundary], "main")
    observed_cmd = parse(lines[boundary + 1:], "commander")
    expected_main: Counter[str] = Counter()
    for entry in deck.entries:
        expected_main[db[entry.oracle_id].name] += entry.quantity
    expected_cmd = Counter(db[cid].name for cid in deck.commanders)
    if observed_main != expected_main:
        issues.append(Issue("export-main", "Mainboard text differs from Oracle-ID deck"))
    if observed_cmd != expected_cmd:
        issues.append(Issue("export-commander", "Commander text differs from deck"))
    return issues


def deck_digest(deck: Any, plan: Any) -> str:
    """Stable digest of deck content, roles, slots and the allocation plan."""
    payload = {
        "commanders": sorted(deck.commanders),
        "entries": sorted(
            (entry.oracle_id, entry.slot, entry.role, entry.quantity)
            for entry in deck.entries
        ),
        "plan": {
            "land_slots": plan.land_slots,
            "commander_count": plan.commander_count,
            "synergy_slots": plan.synergy_slots,
            "allocations": sorted(
                (a.role, a.target) for a in plan.allocations
            ),
        },
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def select_random_commanders(db: Any, candidates: frozenset[str], count: int, seed: int) -> list[str]:
    """Sample without replacement, ensuring each available color count is exercised."""
    rng = Random(seed)
    by_colors: dict[int, list[str]] = defaultdict(list)
    for cid in sorted(candidates):
        by_colors[len(db[cid].color_identity)].append(cid)
    chosen: list[str] = []
    for color_count in (0, 5, 4, 3, 2, 1):
        pool = by_colors.get(color_count, [])
        if pool and len(chosen) < count:
            chosen.append(rng.choice(pool))
    remaining = sorted(set(candidates) - set(chosen))
    rng.shuffle(remaining)
    chosen.extend(remaining[:max(0, count - len(chosen))])
    # More than one full commander-pool pass: repeat selections with new seeds.
    if len(chosen) < count:
        cycle = sorted(candidates)
        while len(chosen) < count:
            rng.shuffle(cycle)
            chosen.extend(cycle[:count - len(chosen)])
    return chosen


def write_reports(report: dict[str, Any], json_path: Path, csv_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    fields = (
        "index", "commander", "commander_id", "seed", "colors", "status",
        "land_count", "nonland_count", "synergy_count", "synergy_target",
        "elapsed_seconds", "replayed", "digest", "issue_codes",
    )
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in report["decks"]:
            writer.writerow({
                **{key: row.get(key, "") for key in fields},
                "issue_codes": ";".join(issue["code"] for issue in row["issues"]),
            })


def run_audit(
    db: Any,
    *,
    count: int = 250,
    seed: int = 42,
    named: tuple[str, ...] = (),
    replay_count: int = 20,
    progress_every: int = 25,
    settings: DeckSettings | None = None,
) -> dict[str, Any]:
    settings = settings or DeckSettings()
    if count < 0 or replay_count < 0 or progress_every < 1:
        raise ValueError("count and replay_count must be nonnegative; progress_every >= 1")

    policy = CardPolicy(
        include_banned=settings.include_banned,
        excluded_cards=settings.excluded_cards,
    )
    candidates = policy.commander_candidates(db)
    if not candidates:
        raise ValueError("No eligible commanders found")

    # This exclusion set is computed from the database, independently of
    # CardPolicy.cards_for_commanders and its per-card validator.
    excluded_ids: set[str] = set(settings.excluded_cards)
    for slug in policy.excluded_tags:
        excluded_ids.update(db.by_tag(slug, include_descendants=True))

    selected = select_random_commanders(db, candidates, count, seed)
    for name in named:
        matches = {
            cid for cid in db.by_name(name)
            if cid in candidates and db[cid].name == name
        }
        if len(matches) != 1:
            raise ValueError(f"Expected one eligible commander named {name!r}, got {len(matches)}")
        selected.append(next(iter(matches)))

    master_rng = Random(seed)
    rows: list[dict[str, Any]] = []
    started = perf_counter()
    print(f"Auditing {len(selected):,} decks from {len(candidates):,} eligible commanders...", flush=True)

    for index, cid in enumerate(selected, 1):
        name = db[cid].name
        run_seed = master_rng.getrandbits(63)
        trial_settings = replace(settings, commander_name=name, seed=run_seed)
        trial_start = perf_counter()
        issues: list[Issue] = []
        digest = ""
        land_count = nonland_count = synergy_count = synergy_target = 0
        replayed = False
        try:
            deck, plan = build_deck(db, trial_settings, rng=Random(run_seed))
            digest = deck_digest(deck, plan)
            land_count = sum(e.quantity for e in deck.entries if e.slot == "land")
            nonland_count = sum(e.quantity for e in deck.entries if e.slot == "nonland")
            synergy_count = sum(e.quantity for e in deck.entries if e.role == "synergy")
            synergy_target = plan.synergy_slots
            if deck.commanders != (cid,):
                issues.append(Issue("commander-mismatch", f"Expected {cid}; generated {deck.commanders}"))
            issues.extend(check_deck(
                db, deck, plan,
                include_banned=settings.include_banned,
                excluded_ids=frozenset(excluded_ids),
            ))
            issues.extend(check_export(db, deck, export_lines(db, deck)))
            if index <= replay_count:
                replayed = True
                second, second_plan = build_deck(
                    db, trial_settings, rng=Random(run_seed)
                )
                if deck_digest(second, second_plan) != digest:
                    issues.append(Issue("nondeterministic", "Fixed commander and seed produced a different deck"))
        except Exception as exc:
            issues.append(Issue("generation-error", f"{type(exc).__name__}: {exc}"))

        row = {
            "index": index,
            "commander": name,
            "commander_id": cid,
            "seed": run_seed,
            "colors": "".join(sorted(db[cid].color_identity)),
            "status": "FAIL" if issues else "PASS",
            "land_count": land_count,
            "nonland_count": nonland_count,
            "synergy_count": synergy_count,
            "synergy_target": synergy_target,
            "elapsed_seconds": round(perf_counter() - trial_start, 3),
            "replayed": replayed,
            "digest": digest,
            "issues": [asdict(issue) for issue in issues],
        }
        rows.append(row)
        if issues:
            print(f"  FAIL [{index}] {name}: {issues[0].code}: {issues[0].detail}", flush=True)
        elif index % progress_every == 0 or index == len(selected):
            print(f"  Checked {index:,}/{len(selected):,} decks...", flush=True)

    failing = [row for row in rows if row["issues"]]
    codes = Counter(issue["code"] for row in rows for issue in row["issues"])
    info = db.info()
    return {
        "metadata": {
            "schema_version": str(info.schema_version),
            "created_at": str(info.created_at),
            "sample_seed": seed,
            "random_count": count,
            "named_commanders": list(named),
            "replay_count": replay_count,
            "include_banned": settings.include_banned,
            "land_range": list(settings.land_range),
            "packages": [
                {"role": p.role, "tags": list(p.tags), "count_range": list(p.count_range)}
                for p in settings.packages
            ],
            "synergy_percent": settings.synergy_percent,
            "nonbasic_fraction": settings.nonbasic_fraction,
            "snow_chance": settings.snow_chance,
        },
        "summary": {
            "total_decks": len(rows),
            "passing_decks": len(rows) - len(failing),
            "failing_decks": len(failing),
            "replayed_decks": sum(row["replayed"] for row in rows),
            "issue_counts": dict(sorted(codes.items())),
            "color_count_distribution": dict(sorted(Counter(
                str(len(row["colors"])) for row in rows
            ).items())),
            "total_seconds": round(perf_counter() - started, 2),
        },
        "decks": rows,
    }


def _land_range(value: str) -> tuple[int, int]:
    parts = value.split("-", 1)
    try:
        low = int(parts[0])
        high = int(parts[1]) if len(parts) == 2 else low
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use N or MIN-MAX") from exc
    if not 0 <= low <= high <= 99:
        raise argparse.ArgumentTypeError("Land range must be within 0-99")
    return low, high


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=250, help="Random decks (stratified by commander color count)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--commander", action="append", default=[], help="Extra named commander; repeatable")
    parser.add_argument("--replays", type=int, default=20, help="First N decks rebuilt to verify determinism")
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--include-banned", action="store_true")
    parser.add_argument("--lands", type=_land_range, default=(34, 40))
    parser.add_argument("--no-packages", action="store_true")
    parser.add_argument("--synergy-percent", type=float, default=0.4)
    parser.add_argument("--nonbasic-fraction", type=float)
    parser.add_argument("--snow-chance", type=float, default=0.055)
    parser.add_argument("--json", type=Path, default=Path("out/audits/m9-integration.json"))
    parser.add_argument("--csv", type=Path, default=Path("out/audits/m9-decks.csv"))
    args = parser.parse_args(argv)
    if args.count < 0 or args.replays < 0 or args.progress_every < 1:
        parser.error("--count and --replays must be nonnegative; --progress-every >= 1")
    if args.count == 0 and not args.commander:
        parser.error("Specify at least one random or named commander")
    if args.json.resolve() == args.csv.resolve():
        parser.error("JSON and CSV output paths must be different")

    from mtg_carddb import CardDatabase, default_database_path
    database = args.database or default_database_path()
    if not Path(database).is_file():
        parser.error(f"Existing CardDB snapshot not found: {database}")
    try:
        settings = DeckSettings(
            land_range=args.lands,
            packages=() if args.no_packages else DEFAULT_PACKAGES,
            synergy_percent=args.synergy_percent,
            include_banned=args.include_banned,
            nonbasic_fraction=args.nonbasic_fraction,
            snow_chance=args.snow_chance,
        )
        print(f"Opening CardDB read-only: {database}", flush=True)
        with CardDatabase.open(database) as db:
            report = run_audit(
                db,
                count=args.count,
                seed=args.seed,
                named=tuple(args.commander),
                replay_count=args.replays,
                progress_every=args.progress_every,
                settings=settings,
            )
    except (ValueError, OSError) as exc:
        parser.error(str(exc))

    write_reports(report, args.json, args.csv)
    summary = report["summary"]
    print(
        f"Result: {summary['passing_decks']:,}/{summary['total_decks']:,} passed; "
        f"{summary['failing_decks']:,} failed; "
        f"{summary['replayed_decks']:,} determinism replays."
    )
    if summary["issue_counts"]:
        print(f"Issues: {summary['issue_counts']}")
    print(f"JSON: {args.json}\nCSV:  {args.csv}")
    return 1 if summary["failing_decks"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
