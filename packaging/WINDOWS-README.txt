MTG RANDOM COMMANDER - WINDOWS x64 (CLI)
=======================================

Quick start
-----------
1. Extract the complete MTGRandomCommander folder from the release ZIP.
2. Double-click Run.bat to generate a deck. The console stays open.
3. For command-line usage, open PowerShell in the extracted folder:

    .\MTGRandomCommander.exe --help
    .\MTGRandomCommander.exe --commander "Karlov of the Ghost Council" --seed 42
    .\MTGRandomCommander.exe --count 5
    .\MTGRandomCommander.exe --update-db

No separate Python installation is needed. Keep _internal beside the EXE.

On first use, the application downloads Scryfall data and builds a CardDB
snapshot in your persistent user-data folder; an internet connection is
required for this initialization. Later launches reuse that database offline.
Updates are opt-in with --update-db. Database data is not in this ZIP.

The default output directory is "out" relative to the CURRENT WORKING
DIRECTORY. Run.bat switches to the extracted application directory, so its
output appears alongside Run.bat. Invoking the EXE from a console uses that
console's working directory. Use --out-dir PATH to override the location.

Run.bat is optional. It is only provided for convenient double-click usage.
This remains a command-line application, not a graphical interface.
The EXE is not code-signed; verify the release source before deciding how to
handle Windows SmartScreen or antivirus warnings.
