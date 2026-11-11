"""Command-line interface for the minimal Commander generator."""

from __future__ import annotations

import argparse
from time import perf_counter
from collections.abc import Sequence
from pathlib import Path
from random import Random
import sys

from mtg_carddb import CardDatabase

from .builder import build_deck
from .database import ensure_database
from .export import save_decklist
from .models import DeckSettings
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
    )

    rng = Random(settings.seed)

    try:
        path = ensure_database(
            path=args.database,
            update=args.update_db,
        )

        with CardDatabase.open(path) as db:
            # Warm CardDB's lazily loaded indexes before generation.
            print("Preparing card database for generation...", flush=True)
            started = perf_counter()

            policy = CardPolicy(
                include_banned=settings.include_banned,
                excluded_cards=settings.excluded_cards,
            )

            policy.eligible_cards(db)

            print(
                f"Card database ready ({perf_counter() - started:.1f}s).",
                flush=True,
            )

            # Build the commander pool only for random selection.
            commander_candidates = None

            if settings.commander_name is None:
                print("Preparing eligible commander pool...", flush=True)
                started = perf_counter()

                commander_candidates = policy.commander_candidates(db)

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

    except Exception as exc:
        print(
            f"Unable to generate deck: {exc}",
            file=sys.stderr,
        )
        return 1

    return 0
