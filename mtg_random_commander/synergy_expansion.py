"""Additional directional commander-tag synergies (M12).

The keys describe abilities or payoffs a commander may have. The values are
Oracle Tags on *supporting* cards. These are conservative, mechanical links;
there is intentionally no blanket ``gives-*`` or ``repeatable-*`` fallback.
Absent optional tags are ignored by the parser, so older CardDB snapshots work.
"""

from .synergy_resources import (
    ARTIFACT_FODDER_TAGS,
    CREATURE_FODDER_TAGS,
    GRAVEYARD_SETUP_TAGS,
    TOKEN_FODDER_TAGS,
    COUNTER_GROWTH_TAGS,
)

CARD_DRAW = ("pure-draw", "repeatable-pure-draw", "draw-engine", "cantrip", "loot")
SPELL_VELOCITY = ("cantrip", "cost-reducer", "refund", "mini-refund", "ritual-untap")
LAND_VELOCITY = ("land-ramp", "multi-land-ramp", "extra-land", "play-additional-land")
ATTACK_ENABLERS = ("gives-haste", "extra-combat-phase", "gives-myriad", "multiple-bodies")
EVASION = ("gives-flying", "gives-menace", "gives-unblockable", "gives-trample")
ETB_PAYOFFS = (
    "enters-and-leaves-trigger-self", "titan-trigger", "etb-untapper",
    "leaves-battlefield-trigger", "multiple-bodies",
)
CAST_TRIGGERS = ("cast-trigger", "cast-trigger-you", "second-spell-matters", "storm-count-matters")
SACRIFICE_PAYOFFS = ("your-sacrifice-matters", "death-trigger", "death-trigger-self", "blood-artist-ability")
COUNTER_PAYOFFS = ("counters-matter", "pp-counters-matter", "synergy-proliferate")
TOKEN_PAYOFFS = ("creature-count-matters", "artifact-count-matters", "token-doubler", "token-increaser")
EXILE_PAYOFFS = ("cards-in-exile-matter", "synergy-exile-cast", "cast-trigger-you")
GRAVEYARD_PAYOFFS = (
    "cards-in-graveyard-matter", "card-types-in-graveyard-matter",
    "threshold", "undergrowth", "synergy-graveyard-cast",
)

# These relationships supplement, rather than replace, the M8 payoff and
# resource tables. They are intentionally not inferred from arbitrary spelling.
EXPANDED_ENABLER_TAGS: dict[str, tuple[str, ...]] = {
    # Attack, spell, and permanent triggers.
    "attacking-matters-self": ATTACK_ENABLERS + EVASION,
    "attacking-matters-any": ATTACK_ENABLERS,
    "attack-trigger": ATTACK_ENABLERS + ("gives-double-strike",),
    "unblocked-trigger": EVASION + ATTACK_ENABLERS,
    "saboteur": EVASION + ("gives-double-strike",),
    "block-trigger": ("gives-vigilance", "gives-deathtouch", "gives-first-strike", "gives-reach"),
    "death-trigger": CREATURE_FODDER_TAGS + ("free-sacrifice-outlet", "repeatable-sacrifice-outlet"),
    "death-trigger-self": CREATURE_FODDER_TAGS + ("free-sacrifice-outlet", "repeatable-sacrifice-outlet"),
    "death-trigger-opponent": ("opponent-sacrifices", "mutual-sacrifice", "removal-creature"),
    "cast-trigger": SPELL_VELOCITY,
    "cast-trigger-you": SPELL_VELOCITY,
    "cast-trigger-self": SPELL_VELOCITY,
    "cast-trigger-other": SPELL_VELOCITY,
    "leaves-battlefield-trigger": CREATURE_FODDER_TAGS + ("flicker-creature", "rescue-creature"),
    "enters-and-leaves-trigger-self": ("flicker-creature", "flicker-permanent", "rescue-creature"),
    "trigger-doubler": ETB_PAYOFFS + ("attack-trigger", "death-trigger", "cast-trigger-you"),
    "etb-untapper": ("flicker-creature", "flicker-permanent", "untapper-creature"),
    "titan-trigger": ("flicker-creature", "gives-haste", "extra-combat-phase"),
    "turn-face-up-trigger": ("synergy-face-down", "synergy-face-down-cast", "turn-face-up"),
    "trigger-from-graveyard": GRAVEYARD_SETUP_TAGS,
    "trigger-from-exile": ("impulse-cast", "synergy-exile-cast", "gives-castable-from-exile"),
    # The *effect* enables another part of the deck (reverse relationships).
    "extra-combat-phase": ("attack-trigger", "attacking-matters", "saboteur"),
    "extra-upkeep": ("upkeep-trigger", "upkeep-cost", "cumulative-upkeep"),
    "extra-untap": ("mana-dork", "mana-producer", "tap-outlet"),
    "extra-draw-step": ("draw-matters", "second-draw-matters", "hand-size-matters"),
    "top-deck-manipulation": ("top-matters", "synergy-miracle", "gives-miracle"),
    "scry": ("synergy-scry", "top-matters", "second-draw-matters"),
    "surveil": ("synergy-surveil",) + GRAVEYARD_PAYOFFS,
    "explore-like": ("synergy-explore", "lands-in-graveyard-matter", "landfall"),
    "loot": ("self-discard-matters", "synergy-madness") + GRAVEYARD_PAYOFFS,
    "rummage": ("self-discard-matters", "synergy-madness") + GRAVEYARD_PAYOFFS,
    "discard-outlet": ("self-discard-matters", "synergy-madness") + GRAVEYARD_PAYOFFS,
    "mill-self": ("threshold", "undergrowth", "synergy-graveyard-cast") + GRAVEYARD_PAYOFFS,
    "token-doubler": TOKEN_FODDER_TAGS + ("synergy-token", "synergy-token-creature"),
    "token-increaser": TOKEN_FODDER_TAGS + ("synergy-token",),
    "power-doubler": ("power-matters", "power-matters-total", "greatest-power-matters", "synergy-power-up"),
    "counter-doubler": ("gives-pp-counters", "gives-mm-counters", "gives-charge-counter") + COUNTER_PAYOFFS,
    "counter-increaser": ("gives-pp-counters", "gives-mm-counters", "gives-charge-counter") + COUNTER_PAYOFFS,
    "coin-flip": ("coin-flips-matter", "krarks-other-thumb-effect"),
    "roll-d6": ("synergy-dice", "dice-roller", "dice-reroll"),
    "roll-d20": ("synergy-dice", "dice-roller", "dice-reroll"),
    # Broader payoff concepts with identifiable resource generation.
    "mana-value-matters": ("synergy-cascade", "gives-cascade", "cascade", "top-deck-manipulation"),
    "x-cost-matters": ("mana-producer", "mana-increaser", "mana-gorger", "adds-multiple-mana", "refund"),
    "mana-spent-matters": ("mana-producer", "mana-increaser", "mana-gorger", "adds-multiple-mana"),
    "amount-spent-matters": ("mana-producer", "mana-increaser", "adds-multiple-mana"),
    "color-spent-matters": ("mana-fix", "mana-filter", "mana-producer"),
    "color-count-matters": ("mana-fix", "mana-filter", "synergy-multicolor"),
    "mana-abilities-matter": ("mana-dork", "mana-producer", "mana-ability-with-extra-effect"),
    "power-matters": ("power-boost-to-all", "power-doubler", "synergy-power-up"),
    "power-matters-self": ("power-boost-to-all", "power-doubler", "synergy-power-up"),
    "power-matters-total": ("power-boost-to-all", "power-doubler", "synergy-power-up"),
    "greatest-power-matters": ("power-boost-to-all", "power-doubler", "synergy-power-up"),
    "specific-power-matters": ("power-boost-to-all", "synergy-power-up"),
    "toughness-matters": ("toughness-boost-to-all", "synergy-defender", "buttlink"),
    "specific-toughness-matters": ("toughness-boost-to-all", "synergy-defender"),
    "bottom-of-library-matters": ("bottom-deck-manipulation", "restock-to-bottom", "tuck-self"),
    "top-matters": ("top-deck-manipulation", "scry", "brainstorm", "synergy-scry"),
    "leaving-graveyard-matters": ("reanimate", "reanimate-creature", "regrowth-creature", "delve", "escape"),
    "cards-in-exile-matter": ("impulse-cast", "impulse-impulsive-draw", "synergy-exile-cast", "gives-castable-from-exile"),
    "off-turn-casting-matters": ("gives-flash", "synergy-flash", "counterspell-reusable", "instant-speed-discard"),
    "recasting-commander-matters": ("rescue-creature", "bounce-self", "cost-reducer-creature", "synergy-commander"),
    "commander-tax-matters": ("mana-producer", "land-ramp", "cost-reducer-creature", "synergy-commander"),
    "monarch-matters": EVASION + ("saboteur", "fog", "synergy-initiative"),
    "discarded-type-matters": ("discard-outlet", "loot", "rummage", "free-discard-outlet"),
    "differently-named-lands-matter": LAND_VELOCITY + ("tutor-land-any", "synergy-nonbasic-land"),
    "stun-counters-matter": ("gives-stun-counter", "freeze-creature", "freeze-permanent-any", "repeatable-proliferate"),
    "unique-counters-matter": ("counter-doubler", "counter-increaser", "repeatable-proliferate", "gives-charge-counter"),
    "metalcraft": ARTIFACT_FODDER_TAGS + ("mana-producer", "synergy-artifact"),
    "improvise": ARTIFACT_FODDER_TAGS + ("synergy-artifact",),
    "convoke": CREATURE_FODDER_TAGS + ("synergy-token-creature",),
    "revolt": ("free-sacrifice-outlet", "flicker-creature", "flicker-permanent", "rescue-creature"),
    "heroic": ("single-target-buff", "combat-trick", "gives-hexproof", "gives-indestructible"),
    "synergy-modified": ("gives-pp-counters", "repeatable-pp-counters", "synergy-aura", "synergy-equipment"),
    # Actions that are useful enablers but also need build-around payoffs.
    "repeatable-creature-tokens": TOKEN_PAYOFFS + SACRIFICE_PAYOFFS,
    "repeatable-artifact-tokens": TOKEN_PAYOFFS + ("synergy-artifact", "artifact-count-matters"),
    "repeatable-noncreature-tokens": ("artifact-count-matters", "token-doubler", "synergy-token"),
    "repeatable-enchantment-tokens": ("synergy-enchantment", "synergy-aura", "sacrifice-outlet-enchantment"),
    "repeatable-token-generator": TOKEN_PAYOFFS + SACRIFICE_PAYOFFS,
    "repeatable-treasures": ("synergy-treasure", "artifact-count-matters", "your-sacrifice-matters"),
    "repeatable-clues": ("synergy-clue", "artifact-count-matters", "your-sacrifice-matters"),
    "repeatable-food": ("synergy-food", "lifegain-matters", "artifact-count-matters"),
    "repeatable-blood": ("synergy-blood", "self-discard-matters", "artifact-count-matters"),
    "repeatable-junk": ("synergy-junk", "cards-in-exile-matter", "artifact-count-matters"),
    "repeatable-powerstones": ("artifact-count-matters", "synergy-artifact", "mana-spent-matters"),
    "repeatable-gold": ("artifact-count-matters", "your-sacrifice-matters"),
    "repeatable-roles": ("synergy-aura", "synergy-enchantment", "your-sacrifice-matters"),
    "repeatable-lifegain": ("lifegain-matters", "pridemate", "super-pridemate"),
    "repeatable-pure-draw": ("draw-matters", "second-draw-matters", "hand-size-matters"),
    "repeatable-card-advantage": ("draw-matters", "hand-size-matters", "second-spell-matters"),
    "repeatable-loot": ("self-discard-matters", "synergy-madness") + GRAVEYARD_PAYOFFS,
    "repeatable-rummage": ("self-discard-matters", "synergy-madness") + GRAVEYARD_PAYOFFS,
    "repeatable-mulch": ("lands-in-graveyard-matter", "synergy-land-graveyard") + GRAVEYARD_PAYOFFS,
    "repeatable-removal": ("opponent-sacrifice-matters", "death-trigger-opponent", "synergy-control"),
    "repeatable-impulse": EXILE_PAYOFFS + CAST_TRIGGERS,
    "repeatable-impulsive-draw": EXILE_PAYOFFS + CAST_TRIGGERS,
    "repeatable-pp-counters": COUNTER_PAYOFFS + ("counter-doubler", "counter-increaser"),
    "repeatable-sacrifice-outlet": SACRIFICE_PAYOFFS + CREATURE_FODDER_TAGS,
    "repeatable-rescue": ("enters-and-leaves-trigger-self", "leaves-battlefield-trigger", "titan-trigger"),
    # Broad target/action families that the legacy parser intentionally skipped.
    "copy-spell": ("cantrip", "removal", "counterspell", "burn-any", "ritual-untap"),
    "copy-permanent": ETB_PAYOFFS + ("token-doubler", "synergy-legendary"),
    "copy-permanent-spell": ETB_PAYOFFS + ("cast-trigger-you",),
    "copy-ability": ("mana-ability-with-extra-effect", "pinger", "tap-outlet"),
    "reanimate-permanent": GRAVEYARD_SETUP_TAGS + ("enters-and-leaves-trigger-self", "titan-trigger"),
    "reanimate-nonland": GRAVEYARD_SETUP_TAGS + ("enters-and-leaves-trigger-self", "titan-trigger"),
    "reanimate-cast": GRAVEYARD_SETUP_TAGS + CAST_TRIGGERS,
    "reanimate-from-any": GRAVEYARD_SETUP_TAGS + ("mill-opponent", "mill-self"),
    "regrowth-any": GRAVEYARD_SETUP_TAGS,
    "regrowth-permanent": GRAVEYARD_SETUP_TAGS,
    "regrowth-nonland": GRAVEYARD_SETUP_TAGS,
    "impulse-cast": EXILE_PAYOFFS + CAST_TRIGGERS,
    "impulse-nonland": EXILE_PAYOFFS + CAST_TRIGGERS,
    "impulse-multicolor": EXILE_PAYOFFS + ("synergy-multicolor",),
    "cost-reducer": CAST_TRIGGERS + ("synergy-storm",),
    "cost-reducer-noncreature": ("synergy-instant", "synergy-sorcery", "synergy-enchantment") + CAST_TRIGGERS,
    "cost-reducer-activated-ability": ("activated-ability", "mana-sink", "tap-outlet"),
    "cost-reducer-equip-ability": ("synergy-equipment", "synergy-modified", "synergy-commander"),
    "cost-reducer-colored-mana": ("synergy-multicolor", "mana-fix", "mana-filter"),
    "tap-fuel-power": ("power-boost-to-all", "power-doubler", "synergy-power-up"),
    "untapper-nonland": ("mana-dork", "tap-outlet", "pinger"),
}

# Only keyword abilities with a plausible payoff or enabling relationship.
# E.g. a commander that gains flying may benefit from evasion payoffs; we do
# not interpret arbitrary 'gains-*' strings as a deckbuilding instruction.
KEYWORD_SUPPORT: dict[str, tuple[str, ...]] = {
    "flying": ("synergy-flying", "saboteur", "unblocked-trigger"),
    "first-strike": ("synergy-first-strike", "synergy-deathtouch", "attack-trigger"),
    "double-strike": ("synergy-double-strike", "saboteur", "attack-trigger"),
    "trample": ("synergy-trample", "synergy-power-up", "attack-trigger"),
    "menace": ("synergy-menace", "saboteur", "unblocked-trigger"),
    "unblockable": ("saboteur", "unblocked-trigger", "attacking-matters"),
    "haste": ("synergy-haste", "attack-trigger", "attacking-matters"),
    "vigilance": ("synergy-vigilance", "tap-outlet", "block-trigger"),
    "lifelink": ("lifegain-matters", "pridemate", "lifegain-to-damage"),
    "deathtouch": ("synergy-deathtouch", "pinger", "one-sided-fight"),
    "hexproof": ("synergy-hexproof", "synergy-aura", "synergy-equipment"),
    "indestructible": ("synergy-indestructible", "board-wipe", "your-sacrifice-matters"),
    "ward": ("synergy-hexproof", "synergy-aura", "synergy-equipment"),
    "protection": ("synergy-protection", "synergy-aura", "saboteur"),
    "prowess": ("synergy-instant", "synergy-sorcery", "cantrip"),
    "flash": ("off-turn-casting-matters", "synergy-flash", "cast-trigger-you"),
    "myriad": ("attacking-matters", "attack-trigger", "creature-count-matters"),
    "bushido": ("synergy-bushido", "block-trigger", "attack-trigger"),
    "annihilator": ("attacking-matters", "attack-trigger", "gives-haste"),
    "reach": ("synergy-reach", "block-trigger"),
    "forestwalk": ("saboteur", "unblocked-trigger", "attack-trigger"),
}

for _keyword, _support in KEYWORD_SUPPORT.items():
    # Keep the more targeted M8 mappings (lifelink, haste, deathtouch) intact.
    for _verb in ("gains", "gives"):
        EXPANDED_ENABLER_TAGS.setdefault(f"{_verb}-{_keyword}", _support)

# Other abilities that explicitly grant a resource/mechanic to your cards.
EXPANDED_ENABLER_TAGS.update({
    "gives-flashback": GRAVEYARD_SETUP_TAGS + CAST_TRIGGERS,
    "gives-escape": GRAVEYARD_SETUP_TAGS,
    "gives-dredge": GRAVEYARD_SETUP_TAGS + GRAVEYARD_PAYOFFS,
    "gives-retrace": LAND_VELOCITY + ("synergy-land-graveyard",),
    "gives-unearth": GRAVEYARD_SETUP_TAGS + ("death-trigger",),
    "gives-encore": GRAVEYARD_SETUP_TAGS + ("attack-trigger",),
    "gives-ninjutsu": EVASION + ("saboteur", "unblocked-trigger"),
    "gives-cascade": ("cast-trigger-you", "storm-count-matters", "top-deck-manipulation"),
    "gives-storm": SPELL_VELOCITY,
    "gives-conspire": CREATURE_FODDER_TAGS + SPELL_VELOCITY,
    "gives-casualty": CREATURE_FODDER_TAGS + SPELL_VELOCITY,
    "gives-blitz": CREATURE_FODDER_TAGS + ("death-trigger", "attack-trigger"),
    "gives-offspring": CREATURE_FODDER_TAGS + ("creature-count-matters",),
    "gives-evoke": ("enters-and-leaves-trigger-self", "death-trigger", "titan-trigger"),
    "gives-exploit": CREATURE_FODDER_TAGS + SACRIFICE_PAYOFFS,
    "gives-persist": ("death-trigger", "your-sacrifice-matters", "counter-increaser"),
    "gives-undying": ("death-trigger", "your-sacrifice-matters", "counter-increaser"),
    "gives-castable-from-exile": EXILE_PAYOFFS,
    "gives-castable-from-graveyard": GRAVEYARD_SETUP_TAGS + CAST_TRIGGERS,
    "gives-castable-from-library": ("top-deck-manipulation", "scry", "brainstorm"),
    "gives-mana-ability": ("mana-abilities-matter", "mana-spent-matters", "mana-sink"),
    "gives-tap-ability": ("untapper-creature", "untapper-permanent", "synergy-tapped"),
    "gives-charge-counter": COUNTER_GROWTH_TAGS + COUNTER_PAYOFFS,
    "gives-mm-counters": COUNTER_GROWTH_TAGS + COUNTER_PAYOFFS,
})

# Explicit target-dependent abilities. The main parser resolves these using
# CardDB type/subtype/keyword indexes; no text scanning or arbitrary parsing.
# Exclude self-only effects, which provide no reliable target-building signal.
TARGET_ABILITY_EXPRESSIONS: dict[str, str] = {
    "animate-artifact": "artifact",
    "animate-battle": "battle",
    "animate-enchantment": "enchantment",
    "animate-land": "land",
    "animate-planeswalker": "planeswalker",
    "animate-vehicle": "vehicle",
    "flicker-artifact": "artifact",
    "flicker-creature": "creature",
    "flicker-nonland": "nonland",
    "flicker-permanent": "permanent",
    "sneak-artifact": "artifact",
    "sneak-artifact-creature": "artifact-creature",
    "sneak-aura": "aura",
    "sneak-creature": "creature",
    "sneak-equipment": "equipment",
    "sneak-land": "land",
    "sneak-permanent": "permanent",
}

# Descend requires a permanent card to reach your graveyard. Self-mill,
# rummaging, and sacrificing permanents are plausible enablers; this is an
# explicit card-text exception because no direct 'descend' Oracle Tag exists
# in the older commander tag inventory.
DESCEND_ENABLERS = GRAVEYARD_SETUP_TAGS + (
    "free-sacrifice-outlet", "repeatable-sacrifice-outlet",
    "sacrifice-outlet-creature", "sacrifice-outlet-land",
    "discard-outlet-creature", "discard-outlet-land",
)

# If Tagger later gains a direct 'descend' slug, prefer its ordinary tag
# package over the synthetic commander-text fallback.
EXPANDED_ENABLER_TAGS["descend"] = DESCEND_ENABLERS

# Additional support for ETB value when blinking, and attack triggers when
# cheating things into play. The card's own direct tag is also retained.
TARGET_ABILITY_SUPPORT = {
    "flicker": ETB_PAYOFFS + ("leaves-battlefield-trigger", "trigger-doubler"),
    "sneak": ETB_PAYOFFS + ("attack-trigger", "gives-haste"),
    "animate": ("synergy-creatureland", "synergy-modified", "power-boost-to-all"),
}

# Additional high-frequency, mechanically actionable labels from the earlier
# tag-coverage report. These are engine-to-payoff relationships, not a blanket
# policy for everyday descriptive tags.
EXPANDED_ENABLER_TAGS.update({
    "draw-engine": ("draw-matters", "second-draw-matters", "hand-size-matters"),
    "pure-draw": ("draw-matters", "second-draw-matters", "hand-size-matters"),
    "card-advantage": ("draw-matters", "hand-size-matters", "second-spell-matters"),
    "spot-removal": ("death-trigger-opponent", "opponent-sacrifice-matters", "synergy-control"),
    "evasion": ("saboteur", "unblocked-trigger", "attack-trigger"),
    "power-boost-to-all": ("power-matters", "power-matters-total", "synergy-power-up"),
    "toughness-boost-to-all": ("toughness-matters", "toughness-matters-total", "synergy-defender"),
    "blood-artist-ability": CREATURE_FODDER_TAGS + ("free-sacrifice-outlet", "repeatable-sacrifice-outlet"),
    "pinger": ("gives-deathtouch", "untapper-creature", "synergy-deathtouch"),
    "lifegain-to-damage": ("lifegain", "repeatable-lifegain", "soul-warden-ability"),
    "multiple-bodies": TOKEN_PAYOFFS + SACRIFICE_PAYOFFS,
    "death-trigger-opponent": ("removal-creature", "opponent-sacrifices", "mutual-sacrifice"),
    "attack-trigger": ATTACK_ENABLERS + EVASION,
    "unblocked-trigger": EVASION + ATTACK_ENABLERS,
    "temporary-token": TOKEN_PAYOFFS + SACRIFICE_PAYOFFS,
    "extra-land": ("landfall", "land-count-matters", "synergy-land-graveyard"),
    "play-additional-land": ("landfall", "land-count-matters", "synergy-land-graveyard"),
    "land-ramp": ("landfall", "land-count-matters", "synergy-creatureland"),
    "gives-plot": ("cast-trigger-you", "off-turn-casting-matters", "synergy-plot"),
    "gives-foretell": ("cards-in-exile-matter", "synergy-foretell", "cast-trigger-you"),
    "gives-suspend": ("cards-in-exile-matter", "synergy-suspend", "cast-trigger-you"),
    "gives-rebound": ("cast-trigger-you", "storm-count-matters", "synergy-instant"),
    "gives-cycling": ("synergy-cycling", "self-discard-matters", "cards-in-graveyard-matter"),
    "gives-connive": ("self-discard-matters", "synergy-connive", "synergy-madness"),
    "synergy-cascade": SPELL_VELOCITY + ("top-deck-manipulation",),
    "synergy-kicker": ("mana-producer", "mana-increaser", "adds-multiple-mana"),
    "synergy-storm": SPELL_VELOCITY,
    "synergy-fight": ("gives-deathtouch", "synergy-power-up", "power-boost-to-all"),
    "synergy-blitz": ("attack-trigger", "death-trigger", "your-sacrifice-matters"),
    "synergy-madness": ("discard-outlet", "free-discard-outlet", "loot", "rummage"),
    "synergy-connive": ("self-discard-matters", "synergy-madness", "graveyard-fuel"),
    "synergy-scry": ("scry", "scry-like", "top-deck-manipulation"),
    "synergy-surveil": ("surveil", "repeatable-surveil", "mill-self") + GRAVEYARD_PAYOFFS,
    "synergy-poison": ("gives-toxic", "gives-poisonous", "repeatable-proliferate", "synergy-proliferate"),
    "synergy-incubator": ARTIFACT_FODDER_TAGS + COUNTER_GROWTH_TAGS,
    "synergy-sacrifice": TOKEN_FODDER_TAGS + ("free-sacrifice-outlet", "repeatable-sacrifice-outlet"),
    "synergy-goad": ("force-attacker", "forced-attacker", "gives-menace", "synergy-attack"),
    "synergy-dungeon": ("venture-into-the-dungeon", "initiative", "synergy-initiative"),
    "synergy-initiative": ("initiative", "evasion", "gives-menace", "fog"),
    "synergy-cycling": ("gives-cycling", "cycling", "self-discard-matters"),
    "synergy-ninjutsu": EVASION + ("unblocked-trigger", "saboteur"),
    "synergy-equipment": ("tutor-artifact-equipment", "gives-haste", "synergy-modified"),
    "synergy-aura": ("tutor-enchantment-aura", "gives-hexproof", "synergy-modified"),
    "regrowth": GRAVEYARD_SETUP_TAGS,
})
