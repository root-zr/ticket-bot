"""Unit tests for RunState persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.persistence.state import RunState, StatePersistence


class TestRunState:
    """Tests for RunState dataclass."""

    def test_construction(self):
        state = RunState(
            state="init",
            attempt=0,
            started_at="2026-06-15T10:00:00+00:00",
            last_update="2026-06-15T10:00:01+00:00",
            error=None,
        )
        assert state.state == "init"
        assert state.attempt == 0
        assert state.error is None

    def test_to_dict(self):
        state = RunState(
            state="selecting_ticket",
            attempt=3,
            started_at="2026-06-15T10:00:00+00:00",
            last_update="2026-06-15T10:00:05+00:00",
            error="timeout",
        )
        d = state.to_dict()
        assert d["state"] == "selecting_ticket"
        assert d["attempt"] == 3
        assert d["error"] == "timeout"
        assert "started_at" in d
        assert "last_update" in d

    def test_to_dict_json_serializable(self):
        state = RunState(
            state="done",
            attempt=1,
            started_at="2026-06-15T10:00:00+00:00",
            last_update="2026-06-15T10:00:10+00:00",
            error=None,
        )
        # This should not raise
        json_str = json.dumps(state.to_dict())
        assert "done" in json_str


class TestStatePersistence:
    """Tests for StatePersistence."""

    def test_save_and_load(self, tmp_path):
        state_file = tmp_path / "run_state.json"
        persistence = StatePersistence(str(state_file))

        state = RunState(
            state="waiting_for_sale",
            attempt=0,
            started_at="2026-06-15T10:00:00+00:00",
            last_update="",
            error=None,
        )
        persistence.save(state)

        assert state_file.exists()

        loaded = persistence.load()
        assert loaded is not None
        assert loaded.state == "waiting_for_sale"
        assert loaded.attempt == 0
        assert loaded.last_update != ""  # Should be auto-filled

    def test_load_nonexistent(self, tmp_path):
        persistence = StatePersistence(str(tmp_path / "nonexistent.json"))
        result = persistence.load()
        assert result is None

    def test_clear(self, tmp_path):
        state_file = tmp_path / "run_state.json"
        persistence = StatePersistence(str(state_file))

        state = RunState(
            state="init",
            attempt=0,
            started_at="2026-01-01T00:00:00+00:00",
            last_update="",
            error=None,
        )
        persistence.save(state)
        assert state_file.exists()

        persistence.clear()
        assert not state_file.exists()

    def test_auto_creates_parent(self, tmp_path):
        nested = tmp_path / "deep" / "logs" / "state.json"
        persistence = StatePersistence(str(nested))

        state = RunState(
            state="init",
            attempt=0,
            started_at="2026-01-01T00:00:00+00:00",
            last_update="",
            error=None,
        )
        persistence.save(state)
        assert nested.exists()

    def test_load_corrupted(self, tmp_path):
        state_file = tmp_path / "bad.json"
        state_file.write_text("{not valid json")
        persistence = StatePersistence(str(state_file))
        result = persistence.load()
        assert result is None

    def test_multiple_saves_update_last_update(self, tmp_path):
        persistence = StatePersistence(str(tmp_path / "state.json"))

        state = RunState(
            state="init",
            attempt=0,
            started_at="2026-01-01T00:00:00+00:00",
            last_update="",
            error=None,
        )
        persistence.save(state)

        import time
        time.sleep(0.01)

        state.state = "logging_in"
        persistence.save(state)

        loaded = persistence.load()
        assert loaded is not None
        assert loaded.state == "logging_in"
