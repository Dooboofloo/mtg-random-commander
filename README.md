# MTG Random Commander

A random Commander deck generator using [MTG CardDB](https://github.com/Dooboofloo/mtg-carddb).

**Status:** Rewrite in progress.

## Getting started

Requires **Python 3.11+**. On Windows, download/extract the source and double-click
**`run.bat`**. It will create a local virtual environment, install `mtg-carddb`
when needed, initialize the card database on the first launch, and generate a
Commander deck. First initialization requires internet access; subsequent
launches work offline. Data is stored in CardDB's per-user location, not inside
this repository. If Python is not installed, the launcher cannot install it.

To run manually or on another operating system:

```sh
python -m pip install -r requirements.txt
python main.py
```

If you prefer a virtual environment, create and activate one before installing
dependencies. The program initializes the database itself when necessary.

### Commands

```sh
python main.py --help
python main.py
python main.py --commander "Karn, Legacy Reforged"
python main.py --count 5
python main.py --lands 37 --seed 42
python main.py --package ramp=8-10 --package draw=5-7
python main.py --synergy-percent 0.25
python main.py --nonbasic-fraction 0.6
python main.py --snow-chance 0
python main.py --no-packages --synergy-percent 0
python main.py --update-db
python scripts/audit_synergy.py --compare scripts/legacy_commander_tags.txt
python main.py --database path/to/custom.sqlite
```

The read-only synergy coverage audit reports Oracle Tag parser support across eligible commanders. It writes detailed JSON and CSV reports to `out/`. The optional `--compare` argument compares the current tag inventory against a historical one-slug-per-line list.

Functional packages are enabled by default: ramp (7–12), interaction (7–12),
and card draw (5–9). The `--package` option overrides individual count ranges;
`--no-packages` disables functional packages.

Commander synergy selection defaults to 40% of the nonland slots remaining
after planned functional package allocations. Use `--synergy-percent` to
configure this fraction between 0 and 1. Cards with no recognized synergy
are replaced by miscellaneous selections. Supported payoff tags, such as
lifegain-matters and your-sacrifice-matters, also select cards with matching
enabler tags. Tutor, copy, reanimation, regrowth, impulse, and cost-reduction
tags can also select matching card types, subtypes, and abilities.
Resource synergies connect graveyard fuel, sacrifice outlets, tap/untap
effects, counters, and selected keyword abilities to useful supporting cards.
Each commander synergy package is weighted independently during selection.
Unrecognized tags remain unsupported.

Mana bases mix random nonbasic lands, commander-synergy lands, and basics
distributed according to colored mana costs. Modal land/spell DFCs can occupy
either land or nonland slots. Use `--nonbasic-fraction` to override the
randomized nonbasic proportion and `--snow-chance` to control the chance
of using snow-covered basic lands.

With `run.bat`, arguments can also be passed through, e.g. `run.bat --update-db`.
**Updates are opt-in.** An existing database is opened without any download.
The program will not automatically overwrite a broken or incompatible file.

## Development

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

`main.py` is
the entry point, and `mtg_random_commander/` contains ordinary internal modules.

## Source data

Card data comes from Scryfall through `mtg-carddb`. Magic: The Gathering is
owned by Wizards of the Coast; this project is not affiliated with either.
