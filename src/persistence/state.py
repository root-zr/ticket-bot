"""Run state persistence — checkpointing the bot's progress."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger


@dataclass
class RunState:
    """Captures the bot's current state for resume/debugging."""
    state: str              # State machine state name
    attempt: int            # Current retry attempt number
    started_at: str         # ISO timestamp of when this run started
    last_update: str        # ISO timestamp of last state update
    error: Optional[str]    # Last error message if any

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "attempt": self.attempt,
            "started_at": self.started_at,
            "last_update": self.last_update,
            "error": self.error,
        }


class StatePersistence:
    """Saves and loads run state checkpoints to disk.

    Useful for:
    - Debugging: see where the bot was when it failed
    - Resume: theoretically could resume from a checkpoint
    - Audit trail: record of each run's progress
    """

    def __init__(self, path: str = "data/logs/run_state.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, state: RunState) -> None:
        """Save current run state to disk."""
        state.last_update = datetime.now(timezone.utc).isoformat()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        logger.debug(f"Run state saved: {state.state} (attempt {state.attempt})")

    def load(self) -> Optional[RunState]:
        """Load last run state from disk."""
        if not self.path.exists():
            return None
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return RunState(**data)
        except Exception as e:
            logger.warning(f"Failed to load run state: {e}")
            return None

    def clear(self) -> None:
        """Delete saved run state."""
        if self.path.exists():
            self.path.unlink()
            logger.info("Run state cleared")
