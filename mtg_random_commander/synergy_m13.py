"""M13 mechanical synergy expansion.

Explicit, directional Oracle Tag relationships, not blanket recognition of
Tagger's descriptive/metadata labels.  A tag on the left describes a commander;
its values describe cards worth sampling alongside it.  Missing optional tags
are ignored at lookup time.  This module does not alter selection weights.
"""

from .synergy_resources import (
    ARTIFACT_FODDER_TAGS,
    CREATURE_FODDER_TAGS,
    GRAVEYARD_SETUP_TAGS,
)
from .synergy_expansion import (
    ATTACK_ENABLERS,
    CARD_DRAW,
    CAST_TRIGGERS,
    COUNTER_PAYOFFS,
    ETB_PAYOFFS,
    EVASION,
    EXILE_PAYOFFS,
    GRAVEYARD_PAYOFFS,
    LAND_VELOCITY,
    SACRIFICE_PAYOFFS,
    SPELL_VELOCITY,
    TOKEN_PAYOFFS,
)

MANA_PRODUCTION = (
    "mana-producer", "mana-dork", "mana-rock", "mana-increaser",
    "adds-multiple-mana", "land-ramp", "untapper-land",
)
POWER_GROWTH = (
    "power-boost-to-all", "power-doubler", "synergy-power-up",
    "single-target-buff", "giant-growth",
)
LIFE_LOSS_PAYOFFS = (
    "life-loss-matters", "opponent-sacrifice-matters", "group-slug",
    "lifegain-to-damage",
)
TOP_MANIPULATION = (
    "top-deck-manipulation", "scry", "scry-like", "brainstorm",
)
COUNTER_ENABLERS = (
    "gives-pp-counters", "gives-mm-counters", "repeatable-pp-counters",
    "counter-increaser", "counter-doubler", "repeatable-proliferate",
)

M13_ENABLER_TAGS: dict[str, tuple[str, ...]] = {
    # Combat payoffs, engines, and go-wide effects.
    "scales-with-power": POWER_GROWTH,
    "scales-with-damage-dealt": POWER_GROWTH + EVASION + ("gives-double-strike",),
    "power-matters-individual": POWER_GROWTH,
    "keyword-anthem": CREATURE_FODDER_TAGS + ("multiple-bodies", "synergy-token-creature"),
    "anthem": CREATURE_FODDER_TAGS + ("multiple-bodies", "synergy-token-creature"),
    "gives-saboteur": EVASION + ("gives-double-strike", "extra-combat-phase"),
    "curiosity": EVASION + ("pinger", "gives-double-strike"),
    "curiosity-like": EVASION + ("pinger", "gives-double-strike"),
    "impulsive-curiosity": EVASION + ("pinger",),
    "unblockable": ("saboteur", "unblocked-trigger", "curiosity", "curiosity-like"),
    "gives-evasion": ("saboteur", "unblocked-trigger", "curiosity"),
    "gives-skulk": ("saboteur", "unblocked-trigger", "curiosity"),
    "gains-skulk": ("saboteur", "unblocked-trigger", "curiosity"),
    "gives-fear": ("saboteur", "unblocked-trigger", "curiosity"),
    "gains-fear": ("saboteur", "unblocked-trigger", "curiosity"),
    "gives-shadow": ("saboteur", "unblocked-trigger", "curiosity"),
    "gives-intimidate": ("saboteur", "unblocked-trigger", "curiosity"),
    "gives-horsemanship": ("saboteur", "unblocked-trigger", "curiosity"),
    "gains-horsemanship": ("saboteur", "unblocked-trigger", "curiosity"),
    "gives-exalted": ("attacking-matters-self", "solo-attack", "neo-solo-attack"),
    "gives-melee": ATTACK_ENABLERS + CREATURE_FODDER_TAGS,
    "gives-dethrone": ATTACK_ENABLERS + ("counters-matter", "gives-pp-counters"),
    "gives-training": ATTACK_ENABLERS + POWER_GROWTH,
    "gives-renown": ATTACK_ENABLERS + EVASION + COUNTER_PAYOFFS,
    "gains-renown": ATTACK_ENABLERS + EVASION + COUNTER_PAYOFFS,
    "gives-rampage": ATTACK_ENABLERS + ("force-blocker", "gives-trample"),
    "gains-rampage": ATTACK_ENABLERS + ("force-blocker", "gives-trample"),
    "gives-wither": ("synergy-pp-counters", "counters-matter", "gives-first-strike"),
    "gains-wither": ("synergy-pp-counters", "counters-matter", "gives-first-strike"),
    "gives-toxic": ("synergy-poison", "repeatable-proliferate", "synergy-proliferate"),
    "gives-poisonous": ("synergy-poison", "repeatable-proliferate", "synergy-proliferate"),
    "gives-ingest": ("synergy-exile", "cards-in-exile-matter", "gives-unblockable"),
    "gains-ingest": ("synergy-exile", "cards-in-exile-matter", "gives-unblockable"),
    "gives-lifelink-noncreature": ("lifegain-matters", "pridemate", "lifegain-to-damage"),
    "gives-deathtouch-noncreature": ("pinger", "one-sided-fight", "synergy-deathtouch"),
    "gives-split-second": ("cast-trigger-you", "off-turn-casting-matters"),
    "gives-uncounterable": ("cast-trigger-you", "synergy-high-mv"),
    "gives-player-hexproof": ("life-total-matters-self", "synergy-control"),
    "gives-player-protection": ("life-total-matters-self", "synergy-control"),
    "gives-shroud": ("synergy-aura", "synergy-equipment"),
    # Resources and mana engines.
    "mana-sink": MANA_PRODUCTION,
    "bottomless-mana-sink": MANA_PRODUCTION,
    "unspent-mana-matters": MANA_PRODUCTION + ("mana-storage",),
    "mana-dork": ("untapper-creature", "tap-fuel-creature", "mana-abilities-matter"),
    "mana-producer": ("mana-sink", "mana-spent-matters", "unspent-mana-matters"),
    "adds-multiple-mana": ("mana-sink", "mana-spent-matters", "x-cost-matters"),
    "ramp": ("landfall", "land-count-matters", "mana-sink"),
    "combat-ramp": ATTACK_ENABLERS + EVASION,
    "opponent-loses-life": LIFE_LOSS_PAYOFFS,
    "burn-player": LIFE_LOSS_PAYOFFS + ("damage-increaser", "damage-multiplier"),
    "burn-player-each": LIFE_LOSS_PAYOFFS + ("damage-increaser", "damage-multiplier"),
    "burn-any": ("damage-increaser", "damage-multiplier", "synergy-burn"),
    "burn-creature": ("gives-deathtouch", "damage-increaser", "synergy-burn"),
    "drain-life": ("life-loss-matters", "lifegain-matters", "pridemate"),
    "life-for-cards": ("lifegain", "repeatable-lifegain", "self-life-loss-matters"),
    "life-payment": ("lifegain", "repeatable-lifegain", "self-life-loss-matters"),
    "scales-with-multiple": ("multiple-bodies", "repeatable-creature-tokens", "repeatable-artifact-tokens"),
    "scales-with-mana-value": MANA_PRODUCTION + ("synergy-cascade",),
    "mana-cost-matters": ("mana-fix", "mana-filter", "synergy-multicolor"),
    # Repeatable engines with identifiable payoffs (not all repeatable-* tags).
    "repeatable-scry": ("synergy-scry", "top-matters", "gives-miracle") + TOP_MANIPULATION,
    "repeatable-surveil": ("synergy-surveil", "cards-in-graveyard-matter", "threshold", "undergrowth") + GRAVEYARD_PAYOFFS,
    "repeatable-proliferate": COUNTER_PAYOFFS + ("synergy-poison", "energy-generator", "synergy-planeswalker"),
    "repeatable-draw": ("draw-matters", "second-draw-matters", "hand-size-matters"),
    "repeatable-land-tokens": ("landfall", "lands-matter", "land-count-matters"),
    "repeatable-vibranium": ("artifact-count-matters", "synergy-artifact", "your-sacrifice-matters"),
    "repeatable-plunder": ("synergy-treasure", "artifact-count-matters", "your-sacrifice-matters"),
    "repeatable-modal-choice": ("modal", "synergy-modal"),
    "repeatable-mutagens": ("synergy-modified", "counters-matter", "synergy-pp-counters"),
    # Direct mechanic/payoff relationships.
    "high-mana-value-matters": MANA_PRODUCTION + ("free-cast-another", "synergy-cascade"),
    "low-mana-value-matters": ("cantrip", "synergy-spellslinger") + SPELL_VELOCITY,
    "even-odd-matters": ("synergy-odd", "synergy-even", "mana-value-matters"),
    "card-types-matter": GRAVEYARD_SETUP_TAGS + ("synergy-delirium", "card-types-in-graveyard-matter"),
    "library-size-matters": ("mill-self", "mill-opponent", "draw-engine"),
    "phasing-matters": ("phasing", "gives-phasing", "phase-out-creature"),
    "speed-matters": ("gives-flash", "off-turn-casting-matters", "synergy-flash"),
    # The repeatable-crime tag denotes a crime *enabler*, not a payoff. A
    # synthetic text package (below) additionally handles crime payoffs.
    # Specialty graveyard/copy/flicker relationships.
    "flicker-slow": ETB_PAYOFFS + ("leaves-battlefield-trigger", "landfall"),
    "flicker-self": ETB_PAYOFFS + ("leaves-battlefield-trigger", "trigger-doubler"),
    "flicker-land": ("landfall", "lands-matter", "land-count-matters", "untapper-land"),
    "copy-from-graveyard": GRAVEYARD_SETUP_TAGS + GRAVEYARD_PAYOFFS + CAST_TRIGGERS,
    "copy-nonland": ETB_PAYOFFS + ("synergy-token", "synergy-modified"),
    "copy-noncreature": ("synergy-artifact", "synergy-enchantment", "synergy-planeswalker"),
    "copy-self": ("token-doubler", "token-increaser", "enters-and-leaves-trigger-self"),
    "reanimate-self": GRAVEYARD_SETUP_TAGS + ("free-sacrifice-outlet", "death-trigger-self"),
    "reanimate-from-opponent": ("mill-opponent", "removal-creature", "opponent-sacrifices"),
    "reanimate-face-down": GRAVEYARD_SETUP_TAGS + ("synergy-face-down", "synergy-morph"),
    "regrowth-self": GRAVEYARD_SETUP_TAGS + ("self-discard-matters",),
    "tutor-to-hand": ("hand-size-matters", "self-discard-matters", "draw-matters"),
    "tutor-to-battlefield": ETB_PAYOFFS + ("titan-trigger",),
    "tutor-to-exile": EXILE_PAYOFFS,
    "tutor-to-graveyard": GRAVEYARD_PAYOFFS + ("reanimate", "synergy-graveyard-cast"),
    "tutor-to-top": TOP_MANIPULATION + ("top-matters", "synergy-miracle"),
    "tutor-land-to-battlefield": ("landfall", "land-count-matters", "lands-matter"),
    "tutor-from-opponent": ("theft-cast", "nightveil-theft", "synergy-theft"),
    "impulse-onto-battlefield": ETB_PAYOFFS + EXILE_PAYOFFS,
    "impulse-to-top": TOP_MANIPULATION,
    "gives-miracle": TOP_MANIPULATION + ("synergy-miracle",),
    "gives-jump-start": ("discard-outlet", "self-discard-matters", "synergy-madness"),
    "gives-replicate": SPELL_VELOCITY + ("copy-spell", "cast-trigger-you"),
    "gives-modular": ARTIFACT_FODDER_TAGS + COUNTER_ENABLERS,
    "gives-riot": ATTACK_ENABLERS + COUNTER_ENABLERS,
    "gives-fabricate": CREATURE_FODDER_TAGS + ARTIFACT_FODDER_TAGS,
    "gives-living-weapon": ("synergy-equipment", "creature-count-matters", "synergy-modified"),
    "gives-scavenge": GRAVEYARD_SETUP_TAGS + COUNTER_ENABLERS,
    "gives-read-ahead": ("synergy-saga", "synergy-enchantment", "lore-counters-matter"),
    "gives-firebending": ("mana-sink", "mana-spent-matters", "x-cost-matters"),
    "gains-firebending": ("mana-sink", "mana-spent-matters", "x-cost-matters"),
    "gives-warp": ("enters-and-leaves-trigger-self", "titan-trigger", "cast-trigger-you"),
    "gains-suspend": TOP_MANIPULATION + CAST_TRIGGERS,
    "gives-soulshift": ("synergy-spirit", "cards-in-graveyard-matter"),
    "gains-soulshift": ("synergy-spirit", "cards-in-graveyard-matter"),
}

# Exact public CardDB mana-value query: no scanning every card and no
# importing the library's private SQLite implementation.  Lands are excluded
# in the parser so these are useful as nonland synergy slots.
M13_MANA_VALUE_RANGES: dict[str, tuple[int, int]] = {
    "low-mana-value-matters": (0, 2),
    "high-mana-value-matters": (5, 1000),
    "scales-with-mana-value": (5, 1000),
}

# Only *payoff* wording creates synthetic packages. Most ordinary crime
# enablers have the 'repeatable-crime' tag and should not generate extra
# packages merely because they target opponents.
M13_CRIME_PAYOFF_PATTERN = (
    r"\b(?:whenever|each time) you commit a crime\b"
    r"|\bif you committed a crime\b"
    r"|\b(?:first|second) time you commit a crime\b"
)
M13_CRIME_ENABLERS = (
    "repeatable-crime", "spot-removal", "pinger", "hand-disruption",
)
