"""
In-memory run manager for the scraper pipeline.

Single concurrent run only. Captures `run_snapshot.py` stdout line-by-line
into a buffer that the /run/status HTMX endpoint reads.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Literal

State = Literal["idle", "running", "completed", "failed"]

ROOT = Path(__file__).resolve().parent.parent

# Rough estimate: ~120s for a default --budget 5 --max-results 400 run.
# Used only to render a soft progress indicator; the run is never killed by this.
ETA_SECONDS = 150


class _Run:
    def __init__(self) -> None:
        self.state: State = "idle"
        self.started_at: float | None = None
        self.ended_at: float | None = None
        self.lines: list[str] = []
        self.exit_code: int | None = None
        self.budget: float | None = None
        self.max_results: int | None = None
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None

    # ---- state queries ----

    def status(self) -> dict:
        with self._lock:
            elapsed = (
                (self.ended_at or time.time()) - self.started_at
                if self.started_at else 0.0
            )
            return {
                "state": self.state,
                "elapsed_s": int(elapsed),
                "eta_s": ETA_SECONDS,
                "remaining_s": max(0, ETA_SECONDS - int(elapsed)) if self.state == "running" else 0,
                "progress_pct": min(99, int(elapsed / ETA_SECONDS * 100)) if self.state == "running" else (100 if self.state == "completed" else 0),
                "lines": list(self.lines[-200:]),  # tail
                "line_count": len(self.lines),
                "exit_code": self.exit_code,
                "budget": self.budget,
                "max_results": self.max_results,
            }

    def is_running(self) -> bool:
        return self.state == "running"

    # ---- lifecycle ----

    def start(self, budget: float = 5.0, max_results: int = 400, skip_scrape: bool = False) -> bool:
        with self._lock:
            if self.state == "running":
                return False
            self.state = "running"
            self.started_at = time.time()
            self.ended_at = None
            self.lines = []
            self.exit_code = None
            self.budget = budget
            self.max_results = max_results

        cmd = [
            sys.executable, "-u", "run_snapshot.py",
            "--budget", str(budget),
            "--max-results", str(max_results),
        ]
        if skip_scrape:
            cmd.append("--skip-scrape")
        self.lines.append(f"$ {' '.join(cmd)}")

        try:
            self._proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            with self._lock:
                self.state = "failed"
                self.ended_at = time.time()
                self.lines.append(f"ERROR launching scraper: {e}")
            return True  # state already reflects failure; UI can show it

        self._reader = threading.Thread(target=self._drain, daemon=True)
        self._reader.start()
        return True

    def _drain(self) -> None:
        assert self._proc is not None
        try:
            for raw in self._proc.stdout:  # type: ignore[union-attr]
                line = raw.rstrip("\n")
                with self._lock:
                    self.lines.append(line)
            self._proc.wait()
        finally:
            with self._lock:
                self.ended_at = time.time()
                self.exit_code = self._proc.returncode if self._proc else -1
                self.state = "completed" if self.exit_code == 0 else "failed"
            if self.exit_code == 0:
                # Fresh snapshot on disk — clear cached reads so the UI picks it up.
                from web import data_access as da
                da.invalidate_caches()


run = _Run()
