from __future__ import annotations

from dataclasses import dataclass
from functools import singledispatchmethod
import re

from carddb import CardDatabase

PARSERS = [
    (re.compile(r"^typal-(.+)$"), parse_typal),
    (re.compile(r"^synergy-(.+)$"), parse_synergy),
    (re.compile(r"^(.+)-matters$"), parse_matters),
    (re.compile(r"^tutor-(.+)$"), parse_tutor),
    (re.compile(r"^affinity-for-(.+)$"), parse_affinity),
    (re.compile(r"^(.+)fall$"), parse_fall),
    (re.compile(r"^karnstructs$"), parse_karnstructs),
    (re.compile(r"^token-increaser$"), parse_token_increaser),
    (re.compile(r"draw-matters$"), parse_draw), 
]

@dataclass(frozen=True)
class SynergyPackage:
    source_tag: str
    mode: str
    pool: set[str]


def get_synergy_packages(db: CardDatabase, card_id: str) -> list[SynergyPackage]:
    packages = []

    for tag_id in db.tags_by_card.get(card_id, set()):
        tag = db.tag_by_id[tag_id]
        package = parse_synergy_tag(db, tag)

        if package is not None:
            packages.append(package)
    
    return packages

def parse_synergy_tag(db: CardDatabase, tag: str) -> SynergyPackage | None:
    for pattern, parser in PARSERS:
        match = pattern.match(tag)
        if match:
            return parser(db, tag, *match.groups())

    return None

# TODO: Implement individual parsers