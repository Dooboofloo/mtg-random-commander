# MTG Random Commander

A randomized Magic: The Gathering Commander deck generator powered by [MTG CardDB](https://github.com/Dooboofloo/mtg-carddb).

Generate complete, legal 100-card Commander decks with randomized functional packages, commander-specific synergies, and mana bases. The goal is variety and interesting combinations, not competitively optimized decklists.

**Status:** CardDB rewrite complete

## Getting started

Requires **Python 3.11+**.

### Windows

Download or clone the repository and run `run.bat`.

The launcher will:

1. Create a local Python virtual environment if needed.
2. Install the required Python dependencies.
3. Initialize the card database on first use.
4. Generate a random Commander deck.

Python must already be installed. Initial database setup requires an internet connection. Subsequent runs can work offline using the existing database.

You can also pass command-line arguments to the launcher:

```bat
run.bat --commander "Karlov of the Ghost Council" --seed 42
run.bat --count 5
run.bat --update-db
```

### Manual installation

On Windows, Linux, or macOS:

```sh
python -m pip install -r requirements.txt
python main.py
```

Creating and activating a virtual environment before installation is recommended.

The application uses `mtg-carddb>=1.1,<2.0` for card data, Oracle Tags, legality information, and database management.

## Usage

Generate a random deck:

```sh
python main.py
```

Select a commander:

```sh
python main.py --commander "Karlov of the Ghost Council"
```

Generate multiple decks:

```sh
python main.py --count 5
```

Use a reproducible seed:

```sh
python main.py --commander "Tatyova, Benthic Druid" --seed 42
```

Customize the land count:

```sh
python main.py --lands 37
python main.py --lands 34-40
```

Specify an output directory:

```sh
python main.py --out-dir my-decks
```

See all available options:

```sh
python main.py --help
```

### Functional packages

The generator includes three functional packages by default:

| Package | Oracle Tags | Default count |
| --- | --- | --- |
| Ramp | `ramp` | 7–12 |
| Interaction | `removal`, `counterspell` | 7–12 |
| Card draw | `draw` | 5–9 |

Each package selects random eligible nonland cards matching its Oracle Tags.

Use `--package` to define your own package configuration.

**If any `--package` argument is supplied, it replaces all default packages. Only explicitly specified packages are used.**

Both forms are equivalent:

```sh
python main.py --package ramp=10
python main.py --package ramp 10
```

A package count can be fixed (`8`) or an inclusive range (`8-12`).

Multiple packages can be combined, including mixed syntax:

```sh
python main.py --package ramp=8-12 --package draw 6
```

The built-in names `ramp`, `interaction`, and `draw` retain their existing Oracle Tag definitions. Other names are interpreted as individual Oracle Tag slugs.

For example:

```sh
python main.py --commander "Karlov of the Ghost Council" --package lifegain=8 --package removal 7 --package ramp=9 --seed 42
```

This requests:

- 8 cards tagged `lifegain`
- 7 cards tagged `removal`
- 9 cards tagged `ramp`

The default `interaction` and `draw` packages are **not** added.

Packages are selected without replacement. If a package does not have enough eligible cards, its unfilled slots are available for miscellaneous selection.

Unknown Oracle Tag slugs are rejected when validated against CardDB.

To disable functional packages altogether:

```sh
python main.py --no-packages
```

Disabling functional packages does not disable commander synergy selection. To disable both:

```sh
python main.py --no-packages --synergy-percent 0
```

### Commander synergies

The generator uses Oracle Tags on the selected commander to identify mechanically related cards.

Supported relationships include:

- Creature-type and other typal synergies
- Artifacts, enchantments, tokens, and landfall
- Payoff-to-enabler relationships, such as lifegain, sacrifice, and card draw
- Tutor, reanimation, copying, recursion, and cost-reduction targets
- Graveyard fuel, tap/untap interactions, counters, and selected keyword synergies

Each recognized commander synergy package receives independent selection weight. A very large candidate pool therefore does not automatically overwhelm a smaller commander theme.

By default, **40% of nonland slots remaining after planned functional packages** are reserved for commander synergy cards.

Change that allocation with:

```sh
python main.py --synergy-percent 0.25
python main.py --synergy-percent 0.75
python main.py --synergy-percent 0
```

The value must be between `0` and `1`. The final target is rounded down to a whole number of cards.

If no suitable synergy cards are available, unfilled slots become miscellaneous selections.

Not every Oracle Tag represents a useful build-around mechanic. Descriptive or ambiguous tags may be deliberately ignored.

### Mana bases

The generator constructs a mana base from:

- Random eligible nonbasic lands
- Nonbasic lands related to the commander's synergies
- Basic lands distributed according to colored mana demand

The default land count is randomly selected between 34 and 40.

Nonbasic-land selection considers mana production, color fixing, and recognized commander synergies.

Control the target nonbasic share:

```sh
python main.py --nonbasic-fraction 0
python main.py --nonbasic-fraction 0.5
python main.py --nonbasic-fraction 1
```

If insufficient eligible nonbasic lands are available, the remaining slots are filled with basics.

Modal double-faced cards with a land face can occupy either a land slot or a nonland slot, but cannot be selected twice.

#### Snow-covered basics

Every basic land independently has a 5.5% chance of being
snow-covered by default. This includes Wastes.

A deck may contain both normal and snow-covered copies of the
same basic land.

Adjust the per-basic probability with:

```sh
python main.py --snow-chance 0
python main.py --snow-chance 0.5
python main.py --snow-chance 1
```

Snow-themed commanders force snow-covered basics regardless of
this probability, including Snow-Covered Wastes for colorless
commanders.

### Card eligibility

The generator uses CardDB's Commander legality and color-identity information.

It also applies a small set of exclusions for cards incompatible with the intended format or generator, including draft/ante/dexterity cards, Attractions, Stickers, Conspiracies, and selected house-banned cards.

Banned Commander cards are excluded by default. To allow cards marked banned in Commander while retaining the application's other exclusions:

```sh
python main.py --include-banned
```

The generator currently supports **one commander per deck**.

## Output

Generated decks are saved as `.txt` files in `out/` by default.

Each file contains an alphabetically sorted card list with quantities and a separate commander section:

```text
1 Arcane Signet
1 Command Tower
1 Sol Ring
...

// COMMANDER
1 Karlov of the Ghost Council
```

Repeated basic lands are represented with quantities.

Existing output files are never overwritten. If a filename already exists, a numbered suffix is added, such as `_2.txt`.

The `out/` directory is ignored by Git.

## Database management

MTG CardDB stores its database in a per-user location outside this repository.

On first use, the application initializes the database automatically.

**Database updates are opt-in.** Ordinary generation does not redownload card data.

To refresh the database:

```sh
python main.py --update-db
```

To use a custom database path:

```sh
python main.py --database path/to/carddb.sqlite
```

An incompatible or corrupted existing database is not automatically overwritten.

Changing the underlying card or Oracle Tag snapshot may change the decks produced by a given random seed.

## Development and testing

Install development dependencies:

```sh
python -m pip install -r requirements-dev.txt
```

Run all tests:

```sh
python -m pytest -q
```

The repository contains two additional auditing tools.

### Integration audit

`scripts/audit_integration.py` independently checks generated decks against CardDB, without relying on the generator's normal deck validator.

It checks deck size, commander eligibility, legality, color identity, singleton restrictions, card-slot eligibility, functional package allocations, configuration constraints, and text-export consistency.

It can also replay selected seeds to test determinism.

Example:

```sh
python scripts/audit_integration.py --count 100 --seed 42 --replays 20
```

Test a custom package configuration:

```sh
python scripts/audit_integration.py --count 25 --seed 42 --package ramp 8-10 --package removal 8
```

The audit writes JSON and CSV reports to `out/audits/` by default.

It reads an existing CardDB snapshot without modifying it.

### Synergy coverage audit

`scripts/audit_synergy.py` examines direct Oracle Tags on eligible commanders and measures how many have recognized, usable synergy pools.

Run it with:

```sh
python scripts/audit_synergy.py
```

By default, it writes:

- `out/synergy-coverage.json`
- `out/synergy-coverage.csv`
- `out/commander_tags.txt`

The text inventory contains one sorted commander Oracle Tag slug per line.

To compare inventories across database updates, preserve an earlier inventory and supply it with `--compare`:

```sh
python scripts/audit_synergy.py --compare path/to/previous_commander_tags.txt
```

The comparison identifies newly appearing and no-longer-present commander tag slugs.

## Current limitations

- Only single-commander decks are generated. Partner, Choose a Background, and other multiple-commander configurations are not supported.
- Commander selection requires a matching card or face name; fuzzy suggestions are not implemented.
- Custom functional packages select nonland cards only.
- Synergy is based on curated Oracle Tag relationships rather than full strategic interpretation of card text.
- Decks are intentionally randomized, not optimized for power level, mana curve, or competitive play.
- Reproducibility depends on using the same settings, random seed, and CardDB snapshot.

## Project structure

- `main.py` — application entry point
- `mtg_random_commander/cli.py` — command-line interface
- `mtg_random_commander/database.py` — database initialization and updates
- `mtg_random_commander/policy.py` — card and commander eligibility
- `mtg_random_commander/models.py` — settings, packages, and deck records
- `mtg_random_commander/builder.py` — deck generation and validation
- `mtg_random_commander/packages.py` — functional package selection
- `mtg_random_commander/synergy.py` — commander synergy parsing and selection
- `mtg_random_commander/synergy_resources.py` — curated resource relationships
- `mtg_random_commander/lands.py` — mana-base construction
- `mtg_random_commander/export.py` — decklist export
- `scripts/` — auditing utilities
- `tests/` — automated tests

## Source data

Card data, legality information, and Oracle Tags are provided by [MTG CardDB](https://github.com/Dooboofloo/mtg-carddb), using data originating from [Scryfall](https://scryfall.com/).

Magic: The Gathering is owned by Wizards of the Coast.

This is an independent project and is not affiliated with or endorsed by Wizards of the Coast or Scryfall.
