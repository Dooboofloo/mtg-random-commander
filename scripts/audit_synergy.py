"""Audit commander Oracle Tag coverage without changing the card database.

Run from the repository root: python scripts/audit_synergy.py
Requires an existing, initialized mtg-carddb snapshot.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mtg_random_commander.lands import candidate_pools
from mtg_random_commander.policy import CardPolicy
from mtg_random_commander.synergy import (
    SKIPPED_SYNERGY_TAGS, parse_synergy_tag, recognizes_synergy_tag,
)


DEFERRED_FAMILIES = frozenset({
    "*-matters", "tutor-*", "impulse-*", "reanimate*", "regrowth*",
    "copy-*", "cost-reducer-*", "graveyard-fuel-*",
    "sacrifice-outlet-*", "untapper-*", "tap-fuel-*",
    "gives-*", "gains-*", "repeatable-*",
})

COLUMNS = (
    "tag", "family", "status", "commanders", "actionable_commanders",
    "pool_size", "direct_size", "inferred_size", "descendant_extra",
    "eligible_pool_size", "eligible_inferred_size",
    "eligible_nonland_pool_size", "eligible_nonland_inferred_size",
    "eligible_land_pool_size", "actionable_nonland_commanders",
    "example_commanders",
)


def family_for(slug: str) -> str:
    """Group tag patterns for prioritization, not for actual parsing."""
    if slug.startswith("typal-"):
        return "typal-*"
    if slug.startswith("synergy-"):
        return "synergy-*"
    if slug.startswith("affinity-for-"):
        return "affinity-for-*"
    if slug.endswith("fall") and len(slug) > 4:
        return "*fall"
    if slug.startswith("cycle-"):
        return "other/cycle"
    if slug != "x-doesn-t-matter" and slug.endswith(("-matters", "-matter")):
        return "*-matters"

    for prefix, label in (
        ("tutor-", "tutor-*"),
        ("impulse-", "impulse-*"),
        ("reanimate", "reanimate*"),
        ("regrowth", "regrowth*"),
        ("copy-", "copy-*"),
        ("cost-reducer-", "cost-reducer-*"),
        ("graveyard-fuel-", "graveyard-fuel-*"),
        ("sacrifice-outlet-", "sacrifice-outlet-*"),
        ("untapper-", "untapper-*"),
        ("tap-fuel-", "tap-fuel-*"),
        ("gives-", "gives-*"),
        ("gains-", "gains-*"),
        ("repeatable-", "repeatable-*"),
        ("flicker-", "flicker-*"),
        ("sneak-", "sneak-*"),
        ("animate-", "animate-*"),
    ):
        if slug.startswith(prefix):
            return label

    return "other/" + slug.split("-", 1)[0]


def build_report(db: Any, policy: CardPolicy) -> dict[str, Any]:
    """Build a complete inventory of DIRECT tags on eligible commanders.

    An actionable nonland candidate is policy-eligible, color-legal, and
    selectable in a nonland slot. This is a structural test, not a strategic
    judgment about the quality of the match.
    """
    commanders = policy.commander_candidates(db)
    eligible = policy.eligible_cards(db)
    eligible_lands, eligible_nonlands = candidate_pools(db, eligible)
    cards = {card.oracle_id: card for card in db.resolve(commanders)}

    tagged_by_slug: dict[str, set[str]] = defaultdict(set)
    commanders_with_tags: set[str] = set()

    for i, cid in enumerate(sorted(commanders), 1):
        for tagging in db.taggings_for(cid):
            tagged_by_slug[tagging.tag_slug].add(cid)
            commanders_with_tags.add(cid)
        if i % 500 == 0:
            print(
                f"  Read tags for {i:,}/{len(commanders):,} commanders...",
                file=sys.stderr,
            )

    # Reuse color-identity pools rather than querying for every commander.
    identity_pools: dict[frozenset[str], frozenset[str]] = {}

    for card in cards.values():
        identity = card.color_identity
        if identity not in identity_pools:
            identity_pools[identity] = frozenset(
                eligible & db.within_identity("".join(sorted(identity)))
            )

    rows: list[dict[str, Any]] = []
    family_commanders: dict[str, set[str]] = defaultdict(set)
    family_actionable: dict[str, set[str]] = defaultdict(set)
    family_nonland_actionable: dict[str, set[str]] = defaultdict(set)
    family_unsupported_owners: dict[str, set[str]] = defaultdict(set)
    status_commanders: dict[str, set[str]] = defaultdict(set)

    actionable_any: set[str] = set()
    actionable_nonland_any: set[str] = set()
    recognized_any: set[str] = set()

    for i, slug in enumerate(sorted(tagged_by_slug), 1):
        if i % 100 == 0:
            print(
                f"  Classified {i:,}/{len(tagged_by_slug):,} tags...",
                file=sys.stderr,
            )

        family = family_for(slug)
        owners = tagged_by_slug[slug]
        family_commanders[family].update(owners)

        actionable: set[str] = set()
        nonland_actionable: set[str] = set()

        direct_size: int | None = None
        inferred_size: int | None = None
        descendant_extra: int | None = None
        eligible_pool_size: int | None = None
        eligible_inferred_size: int | None = None
        eligible_nonland_pool_size: int | None = None
        eligible_nonland_inferred_size: int | None = None
        eligible_land_pool_size: int | None = None
        pool_size = 0

        if slug in SKIPPED_SYNERGY_TAGS:
            status = "skipped"
        else:
            parsed = parse_synergy_tag(db, slug)

            if not recognizes_synergy_tag(slug):
                status = "unsupported"
                family_unsupported_owners[family].update(owners)
            else:
                direct = db.by_tag(slug, include_descendants=False)
                direct_size = len(direct)
                descendant_extra = len(db.by_tag(slug) - direct)
                recognized_any.update(owners)

                if parsed is None:
                    status = "recognized-empty"
                    inferred_size = 0
                    eligible_pool_size = 0
                else:
                    pool = parsed.pool
                    pool_size = len(pool)

                    inferred = pool - direct
                    inferred_size = len(inferred)

                    eligible_pool = pool & eligible
                    eligible_pool_size = len(eligible_pool)
                    eligible_inferred_size = len(inferred & eligible)

                    eligible_nonland_pool_size = len(
                        pool & eligible_nonlands
                    )
                    eligible_nonland_inferred_size = len(
                        inferred & eligible_nonlands
                    )
                    eligible_land_pool_size = len(
                        pool & eligible_lands
                    )

                    if not inferred_size:
                        status = "direct-only"
                    elif eligible_nonland_inferred_size:
                        status = "expanded"
                    else:
                        status = "expanded-unusable"

                    for cid in owners:
                        color_pool = identity_pools[
                            cards[cid].color_identity
                        ]

                        # Exclude the commander itself from either pool.
                        if (eligible_pool & color_pool) - {cid}:
                            actionable.add(cid)

                        if (
                            pool & eligible_nonlands & color_pool
                        ) - {cid}:
                            nonland_actionable.add(cid)

        status_commanders[status].update(owners)
        family_actionable[family].update(actionable)
        family_nonland_actionable[family].update(nonland_actionable)

        actionable_any.update(actionable)
        actionable_nonland_any.update(nonland_actionable)

        rows.append({
            "tag": slug,
            "family": family,
            "status": status,
            "commanders": len(owners),
            "actionable_commanders": len(actionable),
            "actionable_nonland_commanders": len(nonland_actionable),
            "pool_size": pool_size,
            "direct_size": direct_size,
            "inferred_size": inferred_size,
            "descendant_extra": descendant_extra,
            "eligible_pool_size": eligible_pool_size,
            "eligible_inferred_size": eligible_inferred_size,
            "eligible_nonland_pool_size": eligible_nonland_pool_size,
            "eligible_nonland_inferred_size": eligible_nonland_inferred_size,
            "eligible_land_pool_size": eligible_land_pool_size,
            "example_commanders": [
                cards[cid].name
                for cid in sorted(
                    owners,
                    key=lambda ident: (
                        cards[ident].name.casefold(), ident
                    ),
                )[:3]
            ],
        })

    family_statuses: dict[str, Counter[str]] = defaultdict(Counter)

    for row in rows:
        family_statuses[row["family"]][row["status"]] += 1

    # Upper-bound opportunities, not promises of new synergies:
    # unsupported tags on uncovered commanders deserve investigation.
    uncovered = set(commanders) - actionable_nonland_any

    families = [
        {
            "family": family,
            "tags": sum(family_statuses[family].values()),
            "commanders": len(family_commanders[family]),
            "actionable_commanders": len(family_actionable[family]),
            "actionable_nonland_commanders": len(
                family_nonland_actionable[family]
            ),
            "uncovered_commanders_with_unsupported_tags": len(
                family_unsupported_owners[family] & uncovered
            ),
            "statuses": dict(sorted(family_statuses[family].items())),
        }
        for family in family_commanders
    ]

    families.sort(
        key=lambda row: (
            -row["commanders"], -row["tags"], row["family"]
        )
    )

    info = db.info()
    source_info = [
        {
            "type": source.source_type,
            "updated_at": source.source_updated_at,
        }
        for source in info.sources
    ]

    return {
        "metadata": {
            "database_created_at": info.created_at,
            "database_schema": info.schema_version,
            "sources": source_info,
            "include_banned": policy.include_banned,
        },
        "summary": {
            "eligible_commanders": len(commanders),
            "commanders_with_direct_tags": len(commanders_with_tags),
            "distinct_direct_tags": len(rows),
            "commanders_with_recognized_tags": len(recognized_any),
            "commanders_with_actionable_synergy": len(actionable_any),
            "commanders_with_actionable_nonland_synergy": len(
                actionable_nonland_any
            ),
            "commanders_without_actionable_nonland_synergy": len(
                uncovered
            ),
            "tag_statuses": dict(sorted(Counter(
                row["status"] for row in rows
            ).items())),
            "commander_status_counts": {
                status: len(owners)
                for status, owners in sorted(status_commanders.items())
            },
        },
        "families": families,
        "tags": sorted(
            rows,
            key=lambda row: (-row["commanders"], row["tag"]),
        ),
    }


def compare_inventory(report: dict[str, Any], path: Path) -> dict[str, Any]:
    """Optionally compare against the legacy one-slug-per-line inventory."""
    original = {
        line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    current = {row["tag"] for row in report["tags"]}
    return {
        "historical_tags": len(original),
        "current_tags": len(current),
        "added": sorted(current - original),
        "removed": sorted(original - current),
    }


def write_reports(report: dict[str, Any], json_path: Path, csv_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        for row in report["tags"]:
            writer.writerow({
                **row,
                "example_commanders": "; ".join(row["example_commanders"]),
            })


def write_inventory(report: dict[str, Any], path: Path) -> None:
    """Export current commander tags, sorted one per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    slugs = sorted({row["tag"] for row in report["tags"]})
    path.write_text(
        "".join(f"{slug}\n" for slug in slugs),
        encoding="utf-8",
    )


def print_summary(report: dict[str, Any], top: int) -> None:
    summary = report["summary"]
    print(f"Eligible commanders: {summary['eligible_commanders']:,}")
    print(f"Commanders with direct tags: {summary['commanders_with_direct_tags']:,}")
    print(f"Distinct commander tag slugs: {summary['distinct_direct_tags']:,}")
    print(f"Commanders with recognized tags: {summary['commanders_with_recognized_tags']:,}")
    print(f"Commanders with actionable pools: {summary['commanders_with_actionable_synergy']:,}")
    print(
        "Commanders with nonland synergy: "
        f"{summary['commanders_with_actionable_nonland_synergy']:,}"
    )
    print(
        "Without nonland synergy: "
        f"{summary['commanders_without_actionable_nonland_synergy']:,}"
    )
    print("Tag statuses: " + ", ".join(
        f"{status}={count}" for status, count in summary["tag_statuses"].items()
    ))
    print("\nLargest families (unique affected commanders):")
    for row in report["families"][:top]:
        print(f"  {row['family']:<26} {row['commanders']:>5} commanders; {row['tags']:>4} tags")
    print("\nLargest uncovered opportunities (unsupported family tags):")
    gaps = sorted(
        report["families"],
        key=lambda row: (
            -row["uncovered_commanders_with_unsupported_tags"],
            row["family"],
        ),
    )
    for row in gaps[:top]:
        if row["uncovered_commanders_with_unsupported_tags"]:
            print(
                f"  {row['family']:<26} "
                f"{row['uncovered_commanders_with_unsupported_tags']:>5} "
                "uncovered commanders"
            )

    print("\nDeferred families to investigate:")
    for row in (f for f in report["families"] if f["family"] in DEFERRED_FAMILIES):
        print(f"  {row['family']:<26} {row['commanders']:>5} commanders; {row['tags']:>4} tags")
    print("\nMost common unsupported tags:")
    unsupported = (row for row in report["tags"] if row["status"] == "unsupported")
    for row in list(unsupported)[:top]:
        print(f"  {row['tag']:<38} {row['commanders']:>5} commanders")
    if "baseline" in report:
        baseline = report["baseline"]
        print(f"\nLegacy comparison: {len(baseline['added'])} added, "
              f"{len(baseline['removed'])} removed tags")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=None,
                        help="Existing CardDB SQLite file (default: user database)")
    parser.add_argument("--include-banned", action="store_true",
                        help="Match the generator's include-banned option")
    parser.add_argument("--json", type=Path, default=Path("out/synergy-coverage.json"))
    parser.add_argument("--csv", type=Path, default=Path("out/synergy-coverage.csv"))
    parser.add_argument("--inventory", type=Path, default=Path("out/commander_tags.txt"),
                        help="Export current commander tag slugs, one per line")
    parser.add_argument("--compare", type=Path, default=None,
                        help="Optional legacy inventory: one Oracle Tag slug per line")
    parser.add_argument("--top", type=int, default=20,
                        help="Number of families/tags in console summary")
    args = parser.parse_args(argv)
    if args.top < 0:
        parser.error("--top must be nonnegative")
    output_paths = {args.json.resolve(), args.csv.resolve(), args.inventory.resolve()}
    if len(output_paths) != 3:
        parser.error("--json, --csv, and --inventory must be different files")
    if args.compare is not None and args.compare.resolve() in output_paths:
        parser.error("--compare cannot be the same file as an output")

    from mtg_carddb import CardDatabase

    print("Opening existing CardDB snapshot (read-only)...", file=sys.stderr)
    with CardDatabase.open(args.database) as db:
        print("Auditing eligible commanders and Oracle Tags...", file=sys.stderr)
        report = build_report(db, CardPolicy(include_banned=args.include_banned))

    if args.compare is not None:
        report["baseline"] = compare_inventory(report, args.compare)

    write_reports(report, args.json, args.csv)
    write_inventory(report, args.inventory)
    print_summary(report, args.top)
    print(f"\nJSON: {args.json}\nCSV:  {args.csv}\nTags: {args.inventory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
