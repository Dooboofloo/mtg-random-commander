"""Command-line entry point and first-run database setup."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from collections.abc import Sequence

from mtg_carddb import CardDatabase

from .database import ensure_database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="MTG Random Commander (database integration milestone)."
    )
    parser.add_argument(
        "--update-db",
        action="store_true",
        help="Refresh the installed CardDB snapshot before continuing.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        metavar="PATH",
        help="Use a custom CardDB SQLite file instead of the per-user default.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        path = ensure_database(path=args.database, update=args.update_db)
        with CardDatabase.open(path) as db:
            print(f"Database: {path}")
            print(f"Oracle cards: {len(db):,}")
            legal = db.by_legality("commander", "legal")
            print(f"Commander-legal cards: {len(legal):,}")
    except Exception as exc:
        # Do not silently delete or overwrite an existing invalid database.
        print(f"Database setup/query failed: {exc}", file=sys.stderr)
        return 1

    print("Database integration complete. Deck generation comes next.")
    return 0
