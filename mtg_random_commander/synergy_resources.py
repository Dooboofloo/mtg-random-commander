"""Curated commander resource and archetype synergy relationships.

Keys are commander Oracle Tag slugs. Values are tags identifying
useful supporting cards, not necessarily cards with the same ability.

These are deliberately explicit relationships, rather than a blanket
interpretation of descriptive tags such as gains-* or repeatable-*.
"""

GRAVEYARD_SETUP_TAGS = (
    "mill-self",
    "surveil",
    "repeatable-surveil",
    "mulch",
    "repeatable-mulch",
    "loot",
    "repeatable-loot",
    "rummage",
    "discard-outlet",
)

CREATURE_FODDER_TAGS = (
    "repeatable-creature-tokens",
    "multiple-bodies",
    "leaves-body-behind",
    "splits-on-death",
)

ARTIFACT_FODDER_TAGS = (
    "repeatable-artifact-tokens",
    "repeatable-treasures",
    "repeatable-clues",
    "repeatable-food",
    "repeatable-blood",
)

TOKEN_FODDER_TAGS = CREATURE_FODDER_TAGS + ARTIFACT_FODDER_TAGS

COUNTER_GROWTH_TAGS = (
    "counter-doubler",
    "counter-increaser",
    "repeatable-proliferate",
)


RESOURCE_ENABLER_TAGS: dict[str, tuple[str, ...]] = {
    # Graveyard fuel is something a card consumes.
    # Self-mill and similar effects supply that fuel.
    **{
        slug: GRAVEYARD_SETUP_TAGS
        for slug in (
            "graveyard-fuel",
            "graveyard-fuel-artifact",
            "graveyard-fuel-creature",
            "graveyard-fuel-enchantment",
            "graveyard-fuel-historic",
            "graveyard-fuel-instant",
            "graveyard-fuel-land",
            "graveyard-fuel-legendary",
            "graveyard-fuel-noncreature",
            "graveyard-fuel-nonland",
            "graveyard-fuel-permanent",
            "graveyard-fuel-sorcery",
            "threshold",
            "undergrowth",
            "affinity-undergrowth",
            "delve",
            "gives-delve",
            "synergy-graveyard-cast",
        )
    },

    "synergy-land-graveyard": (
        "mill-self",
        "mulch",
        "repeatable-mulch",
        "crucible-of-worlds",
    ),

    # Reverse relationship: a commander that mills itself
    # can benefit from effects that use its graveyard.
    "mill-self": (
        "reanimate",
        "reanimate-creature",
        "regrowth-creature",
        "graveyard-fuel",
        "graveyard-fuel-creature",
        "cards-in-graveyard-matter",
        "threshold",
        "undergrowth",
        "delve",
    ),

    # Sacrifice outlets need expendable permanents.
    **{
        slug: CREATURE_FODDER_TAGS
        for slug in (
            "sacrifice-outlet-creature",
            "free-sacrifice-outlet",
            "repeatable-sacrifice-outlet",
        )
    },

    "sacrifice-outlet-artifact": ARTIFACT_FODDER_TAGS,
    "sacrifice-outlet-token": TOKEN_FODDER_TAGS,

    "sacrifice-outlet-enchantment": (
        "repeatable-enchantment-tokens",
        "leaves-body-behind",
    ),

    "sacrifice-outlet-land": (
        "land-ramp",
        "multi-land-ramp",
        "extra-land",
        "play-additional-land",
        "crucible-of-worlds",
    ),

    "sacrifice-outlet-nonland": TOKEN_FODDER_TAGS,
    "sacrifice-outlet-universal": TOKEN_FODDER_TAGS,

    # Tapping creatures/artifacts as a resource.
    "tap-fuel-creature": CREATURE_FODDER_TAGS + (
        "untapper-creature",
        "gives-haste",
    ),

    "tap-fuel-artifact": ARTIFACT_FODDER_TAGS + (
        "untapper-artifact",
    ),

    "tap-fuel-token": TOKEN_FODDER_TAGS,

    # Untappers prefer permanents with useful tap abilities.
    "untapper-creature": (
        "mana-dork",
        "pinger",
        "tap-outlet",
    ),

    "untapper-artifact": (
        "mana-producer",
        "mana-sink",
        "utility-mana-rock",
    ),

    "untapper-land": (
        "mana-producer",
        "mana-sink",
    ),

    "untapper-permanent": (
        "mana-dork",
        "mana-producer",
        "pinger",
        "tap-outlet",
    ),

    "synergy-tapped": (
        "tapper-creature",
        "tapper-permanent",
        "tap-outlet",
    ),

    "synergy-untapped": (
        "untapper-creature",
        "untapper-permanent",
        "extra-untap",
    ),

    # Counter-consuming abilities want counter generation
    # and/or repeated proliferation.
    "counter-fuel-pp": (
        "gives-pp-counters",
        "repeatable-pp-counters",
        "repeatable-proliferate",
    ),

    "counter-fuel-energy": (
        "energy-generator",
        "energy-increaser",
        "repeatable-proliferate",
    ),

    **{
        slug: COUNTER_GROWTH_TAGS
        for slug in (
            "counter-fuel-any",
            "counter-fuel-other",
            "counter-fuel-charge",
            "counter-fuel-oil",
            "counter-fuel-loyalty",
            "counter-fuel-lore",
            "gains-pp-counters",
        )
    },

    "gives-pp-counters": COUNTER_GROWTH_TAGS + (
        "pp-counters-matter",
    ),

    "gives-pp-counters-to-all": COUNTER_GROWTH_TAGS + (
        "pp-counters-matter",
    ),

    "synergy-proliferate": (
        "gives-pp-counters",
        "repeatable-pp-counters",
        "energy-generator",
        "gains-pp-counters",
    ),

    # Selective keyword interactions. We do not automatically
    # interpret every gains-* or gives-* tag.
    "gives-lifelink": (
        "lifegain-matters",
        "pridemate",
        "lifegain-to-damage",
    ),

    "gains-lifelink": (
        "lifegain-matters",
        "pridemate",
        "lifegain-to-damage",
    ),

    "gives-deathtouch": (
        "pinger",
        "one-sided-fight",
    ),

    "gives-haste": (
        "attack-trigger",
        "saboteur",
        "attacking-matters",
    ),

    "gives-convoke": CREATURE_FODDER_TAGS,
    "gives-improvise": ARTIFACT_FODDER_TAGS,

    "super-pridemate": (
        "lifegain",
        "repeatable-lifegain",
        "soul-warden-ability",
    ),
}


# These commander abilities specifically untap a target card type.
# Restrict inferred matches accordingly rather than selecting every
# mana producer, regardless of what kind of permanent it is.
RESOURCE_TYPE_FILTERS = {
    "untapper-creature": "Creature",
    "untapper-artifact": "Artifact",
    "untapper-land": "Land",
}
