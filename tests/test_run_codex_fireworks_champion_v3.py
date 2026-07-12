from __future__ import annotations

import json
import pytest

from scripts.run_codex_fireworks_champion_v3 import merge_atomic, validate_batch


def _batch():
    return [{"blind_id": "x"}, {"blind_id": "y"}]


def test_codex_fireworks_champion_v3_validates_complete_consistent_batch():
    payload = {"judgments": [
        {"blind_id": "x", "valid_a": True, "valid_b": False, "winner": "a", "reason": "A satisfies the rubric."},
        {"blind_id": "y", "valid_a": True, "valid_b": True, "winner": "tie", "reason": "Both satisfy it."},
    ]}
    assert len(validate_batch(_batch(), payload)) == 2


def test_codex_fireworks_champion_v3_rejects_missing_or_inconsistent_rows():
    with pytest.raises(ValueError, match="count mismatch"):
        validate_batch(_batch(), {"judgments": []})
    with pytest.raises(ValueError, match="contradicts"):
        validate_batch([{"blind_id": "x"}], {"judgments": [{"blind_id": "x", "valid_a": False, "valid_b": True, "winner": "a", "reason": "bad"}]})


def test_codex_fireworks_champion_v3_atomic_merge_is_resumable_and_immutable(tmp_path):
    path = tmp_path / "judgments.jsonl"
    row = {"blind_id": "x", "valid_a": True, "valid_b": False, "winner": "a", "reason": "valid"}
    assert merge_atomic(path, [row]) == 1
    assert merge_atomic(path, [row]) == 1
    assert json.loads(path.read_text()) == row
    with pytest.raises(ValueError, match="immutable"):
        merge_atomic(path, [{**row, "winner": "tie"}])
