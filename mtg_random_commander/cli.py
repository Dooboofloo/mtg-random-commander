"""Command-line interface for the minimal Commander generator."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
from math import isfinite
import re
from time import perf_counter
from collections.abc import Sequence
from pathlib import Path
from random import Random
import sys

from mtg_carddb import CardDatabase

from .builder import build_deck
from .database import ensure_database
from .export import save_decklist
from .models import DEFAULT_PACKAGES, DeckPackage, DeckSettings
from .policy import CardPolicy


def _land_range(value: str) -> tuple[int, int]:
    try:
        parts = value.split("-", maxsplit=1)

        if len(parts) == 1:
            low = high = int(parts[0])
        else:
            low, high = int(parts[0]), int(parts[1])

    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Use N or MIN-MAX (e.g. 37 or 34-40)"
        ) from exc

    if not 0 <= low <= high <= 99:
        raise argparse.ArgumentTypeError(
            "Land range must be ordered and between 0 and 99"
        )

    return low, high


def _configure_packages(
    overrides: list[str] | list[list[str]],
    disabled: bool,
    parser: argparse.ArgumentParser,
) -> tuple[DeckPackage, ...]:
    """Configure packages using TAG=RANGE or TAG RANGE.

    Both forms are equivalent. If any packages are specified, they
    replace the complete default configuration.
    """
    if disabled:
        if overrides:
            parser.error(
                "--no-packages cannot be combined with --package"
            )
        return ()

    if not overrides:
        return DEFAULT_PACKAGES

    defaults = {
        package.role: package
        for package in DEFAULT_PACKAGES
    }

    reserved = {
        "misc",
        "synergy",
        "basic-land",
        "nonbasic-land",
        "synergy-land",
    }

    packages: list[DeckPackage] = []
    seen: set[str] = set()

    for raw in overrides:
        parts = [raw] if isinstance(raw, str) else list(raw)

        if len(parts) == 1:
            role, separator, value = parts[0].partition("=")

            if not separator:
                parser.error(
                    f"Invalid --package {parts[0]!r}; "
                    "use TAG=RANGE or TAG RANGE"
                )

        elif len(parts) == 2:
            role, value = parts

            if "=" in role or "=" in value:
                parser.error(
                    f"Invalid --package {parts!r}; "
                    "use TAG=RANGE or TAG RANGE"
                )

        else:
            parser.error(
                f"Invalid --package {parts!r}; "
                "use TAG=RANGE or TAG RANGE"
            )

        if not re.fullmatch(
            r"[a-z0-9]+(?:-[a-z0-9]+)*",
            role,
        ):
            parser.error(
                f"Invalid package tag/role {role!r}"
            )

        if role in reserved:
            parser.error(
                f"Package role {role!r} is reserved"
            )

        if role in seen:
            parser.error(
                f"Package {role!r} was specified more than once"
            )

        seen.add(role)

        try:
            count_range = _land_range(value)
        except argparse.ArgumentTypeError as exc:
            parser.error(
                f"Invalid --package {role!r}: {exc}"
            )

        if role in defaults:
            # Preserve built-in tag definitions, including
            # interaction = removal + counterspell.
            packages.append(
                replace(
                    defaults[role],
                    count_range=count_range,
                )
            )
        else:
            packages.append(
                DeckPackage(
                    role=role,
                    tags=(role,),
                    count_range=count_range,
                )
            )

    return tuple(packages)


def _validate_custom_package_tags(
    db: CardDatabase,
    options: list[str] | list[list[str]],
    parser: argparse.ArgumentParser,
) -> None:
    """Validate custom Oracle Tags, regardless of CLI syntax."""
    if not options:
        return

    known = db.tag_slugs

    builtin_roles = {
        package.role
        for package in DEFAULT_PACKAGES
    }

    custom_slugs: set[str] = set()

    for raw in options:
        parts = [raw] if isinstance(raw, str) else list(raw)
        role = parts[0].partition("=")[0]

        if role not in builtin_roles:
            custom_slugs.add(role)

    unknown = sorted(custom_slugs - set(known))

    if unknown:
        parser.error(
            "Unknown Oracle Tag slug(s): "
            + ", ".join(unknown)
        )


def _synergy_percent(value: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Expected a fraction between 0 and 1"
        ) from exc

    if not isfinite(result) or not 0 <= result <= 1:
        raise argparse.ArgumentTypeError(
            "Expected a fraction between 0 and 1"
        )

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate random Commander decks."
    )

    parser.add_argument(
        "-c", "--commander",
        help="Exact commander or face name (default: random)",
    )

    parser.add_argument(
        "-o", "--out-dir",
        type=Path,
        default=Path("out"),
    )

    parser.add_argument(
        "--lands",
        type=_land_range,
        default=(34, 40),
        metavar="N|MIN-MAX",
    )

    parser.add_argument(
        "--seed",
        type=int,
        help="Reproducible random seed",
    )

    parser.add_argument(
        "--count",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--package",
        action="append",
        nargs="+",
        default=[],
        metavar="PACKAGE",
        help=(
            "Configure a package with TAG=RANGE or TAG RANGE; "
            "any explicit packages replace all defaults. Repeatable."
        ),
    )

    parser.add_argument(
        "--no-packages",
        action="store_true",
        help=(
            "Disable functional packages; synergy remains enabled "
            "unless --synergy-percent is 0"
        ),
    )

    parser.add_argument(
        "--synergy-percent",
        type=_synergy_percent,
        default=0.4,
        metavar="FRACTION",
        help="Share of post-package nonland slots reserved for synergy (0-1)",
    )

    parser.add_argument(
        "--nonbasic-fraction",
        type=_synergy_percent,
        default=None,
        metavar="FRACTION",
        help="Target share of land slots filled with nonbasics (0-1)",
    )

    parser.add_argument(
        "--snow-chance",
        type=_synergy_percent,
        default=0.055,
        metavar="FRACTION",
        help="Chance to use snow-covered basics when not forced by synergy",
    )

    parser.add_argument(
        "--include-banned",
        action="store_true",
    )

    parser.add_argument(
        "--update-db",
        action="store_true",
    )

    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        metavar="PATH",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.count < 1:
        parser.error("--count must be positive")

    settings = DeckSettings(
        commander_name=args.commander,
        land_range=args.lands,
        seed=args.seed,
        include_banned=args.include_banned,
        packages=_configure_packages(args.package, args.no_packages, parser),
        synergy_percent=args.synergy_percent,
        nonbasic_fraction=args.nonbasic_fraction,
        snow_chance=args.snow_chance,
    )

    rng = Random(settings.seed)

    try:
        path = ensure_database(
            path=args.database,
            update=args.update_db,
        )

        with CardDatabase.open(path) as db:
            _validate_custom_package_tags(
                db,
                args.package,
                parser,
            )
            # Share one bulk eligibility pool for batches and random
            # commanders. A single named lookup stays lazy until the name
            # has been resolved by the builder.
            policy = CardPolicy(
                include_banned=settings.include_banned,
                excluded_cards=settings.excluded_cards,
            )
            eligible_pool = (
                policy.eligible_cards(db) if args.count > 1 else None
            )
            commander_candidates = None

            if settings.commander_name is None:
                print(
                    "Preparing eligible commander pool...",
                    flush=True,
                )

                started = perf_counter()

                if eligible_pool is None:
                    eligible_pool = policy.eligible_cards(db)

                commander_candidates = policy.commander_candidates(
                    db, eligible_cards=eligible_pool,
                )

                print(
                    f"Found {len(commander_candidates):,} eligible "
                    f"commanders ({perf_counter() - started:.1f}s).",
                    flush=True,
                )

            for index in range(1, args.count + 1):
                prefix = f"[Deck {index}/{args.count}]"
                started = perf_counter()

                def report(stage: str) -> None:
                    message = f"{prefix} {stage}"

                    if sys.stdout.isatty():
                        # Update the existing terminal line.
                        print(
                            f"\r\033[2K{message}",
                            end="",
                            flush=True,
                        )
                    else:
                        # Keep redirected output readable.
                        print(message, flush=True)

                try:
                    deck, plan = build_deck(
                        db,
                        settings,
                        rng=rng,
                        on_progress=report,
                        commander_candidates=commander_candidates,
                        eligible_cards=eligible_pool,
                    )

                    report("Saving decklist...")

                    output = save_decklist(
                        db,
                        deck,
                        args.out_dir,
                    )

                finally:
                    # Clear the temporary progress line.
                    if sys.stdout.isatty():
                        print("\r\033[2K", end="", flush=True)

                name = db[deck.commanders[0]].name
                elapsed = perf_counter() - started

                print(
                    f"{prefix} Created {name}: "
                    f"{plan.land_slots} lands, "
                    f"{plan.nonland_slots} nonlands "
                    f"({elapsed:.1f}s) -> {output}"
                )

                roles = Counter()

                for entry in deck.entries:
                    if entry.slot == "nonland":
                        roles[entry.role] += entry.quantity

                if plan.allocations:
                    details = ", ".join(
                        f"{allocation.role} "
                        f"{roles[allocation.role]}/{allocation.target}"
                        for allocation in plan.allocations
                    )

                    print(f"{prefix} Packages: {details}")

                print(
                    f"{prefix} Synergy: "
                    f"{roles['synergy']}/{plan.synergy_slots}; "
                    f"misc {roles['misc']}"
                )

                land_roles = Counter()

                for entry in deck.entries:
                    if entry.slot == "land":
                        land_roles[entry.role] += entry.quantity

                nonbasics = (
                    land_roles["nonbasic-land"]
                    + land_roles["synergy-land"]
                )

                snow_basics = sum(
                    entry.quantity
                    for entry in deck.entries
                    if entry.slot == "land"
                    and entry.role == "basic-land"
                    and db[entry.oracle_id].name.startswith("Snow-Covered ")
                )

                print(
                    f"{prefix} Mana base: "
                    f"{nonbasics} nonbasics "
                    f"({land_roles['synergy-land']} synergy), "
                    f"{land_roles['basic-land']} basics "
                    f"({snow_basics} snow)"
                )

    except Exception as exc:
        print(
            f"Unable to generate deck: {exc}",
            file=sys.stderr,
        )
        return 1

    return 0
