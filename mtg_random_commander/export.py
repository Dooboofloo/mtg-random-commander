"""Text decklist output with collision-safe filenames."""

from __future__ import annotations

from itertools import count
from pathlib import Path
import re
from typing import TYPE_CHECKING

from .models import Deck

if TYPE_CHECKING:
    from mtg_carddb import CardDatabase


def export_lines(
    db: CardDatabase,
    deck: Deck,
) -> list[str]:
    quantities = deck.quantities()

    ordered = sorted(
        quantities,
        key=lambda cid: (
            db[cid].name.casefold(),
            cid,
        ),
    )

    lines = [
        f"{quantities[cid]} {db[cid].name}"
        for cid in ordered
    ]

    lines.extend(("", "// COMMANDER"))

    lines.extend(
        f"1 {db[cid].name}"
        for cid in deck.commanders
    )

    return lines


def save_decklist(
    db: CardDatabase,
    deck: Deck,
    out_dir: str | Path,
) -> Path:
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)

    commander_name = db[deck.commanders[0]].name

    basename = (
        re.sub(r'[<>:"/\\|?*]', "_", commander_name)
        .strip(" .")
        or "Commander"
    )

    text = "\n".join(export_lines(db, deck)) + "\n"

    for index in count(1):
        suffix = "" if index == 1 else f"_{index}"
        path = directory / f"{basename}{suffix}.txt"

        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(text)

            return path

        except FileExistsError:
            continue
