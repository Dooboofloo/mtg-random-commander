"""Manage the CardDB lifecycle and show human-friendly setup progress.

CardDB is responsible for downloading, indexing, validating and activating the
SQLite snapshot. This module uses only CardDB's public lifecycle callback.
"""

from __future__ import annotations

import sys
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic

from mtg_carddb import (
    WorkflowProgress,
    default_database_path,
    initialize_database,
    update_database,
)


_STAGE_LABELS = {
    "bulk": "Downloading card data from Scryfall",
    "references": "Downloading supplementary card catalogs",
    "build": "Building and checking the local card database",
    "activation": "Installing the finished database",
}


def _elapsed(seconds: float) -> str:
    """Show elapsed wall-clock time as MM:SS or HH:MM:SS."""
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    return f"{minutes:02}:{seconds:02}"


class DatabaseProgress:
    """Print phase changes and periodic heartbeats during blocking CardDB work.

    WorkflowProgress has phase start/complete events, but no byte or card-level
    counts until completion. A heartbeat thread assures users that the program
    is still running without making up percentage-completion estimates.
    """

    def __init__(self, *, interval_seconds: float = 10.0) -> None:
        if interval_seconds <= 0:
            raise ValueError("Progress interval must be positive")
        self._interval_seconds = interval_seconds
        self._stop = Event()
        self._lock = Lock()
        self._thread: Thread | None = None
        self._started = 0.0
        self._stage: str | None = None
        self._stage_started = 0.0

    def __enter__(self) -> DatabaseProgress:
        self._started = monotonic()
        self._stage_started = self._started
        self._stage = "preparing"
        self._write("[00:00] Preparing card database...")
        self._thread = Thread(
            target=self._heartbeat,
            name="random-commander-db-progress",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()

    def _label(self, stage: str) -> str:
        if stage == "preparing":
            return "Preparing card database"
        return _STAGE_LABELS.get(stage, f"Processing database step: {stage}")

    @staticmethod
    def _write(message: str) -> None:
        print(message, file=sys.stderr, flush=True)

    def __call__(self, event: WorkflowProgress) -> None:
        """Receive a public CardDB progress event."""
        now = monotonic()
        with self._lock:
            total = _elapsed(now - self._started)
            label = self._label(event.stage)
            if event.status == "start":
                self._stage = event.stage
                self._stage_started = now
                self._write(f"[{total}] {label}...")
            elif event.status == "complete":
                duration = (
                    now - self._stage_started
                    if self._stage == event.stage
                    else 0.0
                )
                suffix = f" — {event.detail}" if event.detail else ""
                self._write(f"[{total}] Finished: {label} ({_elapsed(duration)}){suffix}")
                self._stage = None

    def _heartbeat(self) -> None:
        while not self._stop.wait(self._interval_seconds):
            with self._lock:
                if self._stage is None:
                    continue
                now = monotonic()
                self._write(
                    f"[{_elapsed(now - self._started)}] "
                    f"Still working: {self._label(self._stage)} "
                    f"({_elapsed(now - self._stage_started)} in this step)"
                )


def ensure_database(*, path: str | Path | None = None, update: bool = False) -> Path:
    """Initialize on first run, optionally update; ordinary runs remain offline.

    Existing but incompatible/corrupt files are never automatically overwritten.
    CardDatabase.open() in the caller reports such errors.
    """
    target = default_database_path() if path is None else Path(path)

    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        print(
            "First-time setup: downloading Magic card data and building a local database.\n"
            "This may take several minutes. Progress updates will appear below.",
            file=sys.stderr,
            flush=True,
        )
        with DatabaseProgress() as progress:
            initialize_database(target, on_progress=progress)
    elif update:
        print(
            "Refreshing card data. Your existing database will remain in place "
            "until the new version is ready.",
            file=sys.stderr,
            flush=True,
        )
        with DatabaseProgress() as progress:
            update_database(target, on_progress=progress)

    return target
