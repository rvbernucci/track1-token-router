from __future__ import annotations

import json

from scripts.merge_judge_consensus import main, merge


def _candidate(candidate_id: str, verdict: str = "uncertain", hard: bool = False):
    return {"id": candidate_id, "task_id": f"task-{candidate_id}", "mechanical": {"hard": hard, "verdict": verdict}}


def _judgment(candidate_id: str, verdict: str, model: str):
    return {"candidate_id": candidate_id, "verdict": verdict, "judge_model": model}


def test_merge_judge_consensus_mechanical_is_authoritative_and_semantic_agreement_labels():
    candidates = [_candidate("mechanical", "correct", True), _candidate("semantic")]
    glm = [_judgment("mechanical", "incorrect", "glm"), _judgment("semantic", "correct", "glm")]
    assigned = [_judgment("mechanical", "incorrect", "codex"), _judgment("semantic", "correct", "agy")]
    rows, audit = merge(candidates, glm, assigned)
    assert {row["candidate_id"]: row["verdict"] for row in rows} == {"mechanical": "correct", "semantic": "correct"}
    assert audit["counts"]["mechanical_authoritative"] == 1
    assert audit["counts"]["semantic_pair_agreement"] == 1


def test_merge_judge_consensus_disagreement_uses_third_else_conservative_incorrect():
    candidates = [_candidate("resolved"), _candidate("closed")]
    glm = [_judgment("resolved", "correct", "glm"), _judgment("closed", "correct", "glm")]
    assigned = [_judgment("resolved", "incorrect", "codex"), _judgment("closed", "incorrect", "agy")]
    third = [_judgment("resolved", "correct", "agy")]
    rows, audit = merge(candidates, glm, assigned, third)
    by_id = {row["candidate_id"]: row for row in rows}
    assert by_id["resolved"]["verdict"] == "correct"
    assert by_id["resolved"]["evidence_source"] == "third_judge_majority"
    assert by_id["closed"]["verdict"] == "incorrect"
    assert by_id["closed"]["evidence_source"] == "conservative_disagreement"
    assert audit["counts"]["semantic_disagreement_resolved_by_third"] == 1
    assert audit["counts"]["semantic_disagreement_without_third"] == 1


def test_merge_judge_consensus_normalizes_uncertain_votes_fail_closed():
    candidates = [_candidate("uncertain")]
    glm = [_judgment("uncertain", "uncertain", "glm")]
    assigned = [_judgment("uncertain", "incorrect", "codex")]
    rows, audit = merge(candidates, glm, assigned)
    assert rows[0]["verdict"] == "incorrect"
    assert rows[0]["evidence_source"] == "judge_consensus"
    assert audit["counts"]["semantic_pair_agreement"] == 1


def test_merge_judge_consensus_cli_emits_builder_compatible_jsonl_and_audit(tmp_path):
    candidates = tmp_path / "candidates.jsonl"
    glm = tmp_path / "glm.jsonl"
    assigned = tmp_path / "assigned.jsonl"
    output = tmp_path / "final.jsonl"
    audit = tmp_path / "audit.json"
    candidates.write_text(json.dumps(_candidate("x")) + "\n")
    glm.write_text(json.dumps(_judgment("x", "correct", "glm")) + "\n")
    assigned.write_text(json.dumps(_judgment("x", "correct", "codex")) + "\n")
    assert main(["--candidates", str(candidates), "--glm", str(glm), "--assigned", str(assigned), "--output", str(output), "--audit", str(audit)]) == 0
    row = json.loads(output.read_text())
    assert row["candidate_id"] == "x"
    assert row["verdict"] == "correct"
    assert row["judge_model"] == "consensus:glm+assigned"
    assert json.loads(audit.read_text())["counts"]["rows"] == 1
