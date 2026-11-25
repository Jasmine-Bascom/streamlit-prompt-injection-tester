import json

import pytest

from tester.runner import (
    run_benchmark_suite,
    run_security_test,
)


@pytest.mark.parametrize(
    "response_verdict,policy_status,expected",
    [
        ("PASS", "PASS", "PASS"),
        ("PASS", "REVIEW", "REVIEW"),
        ("PASS", "FAIL", "FAIL"),
        ("REVIEW", "PASS", "REVIEW"),
        ("REVIEW", "REVIEW", "REVIEW"),
        ("REVIEW", "FAIL", "FAIL"),
        ("FAIL", "PASS", "FAIL"),
        ("FAIL", "REVIEW", "FAIL"),
        ("FAIL", "FAIL", "FAIL"),
    ],
)
def test_combined_verdict(
    response_verdict,
    policy_status,
    expected,
    tmp_path,
):
    def mock_target(prompt):
        requested = []
        executed = []

        if policy_status in ("REVIEW", "FAIL"):
            requested = [{"name": "research_tool"}]

        if policy_status == "FAIL":
            executed = [{"name": "research_tool"}]

        return {
            "output": "Synthetic target response.",
            "route": "general",
            "tool_calls": requested,
            "executed_tool_calls": executed,
        }

    def mock_evaluator(attack, target_result):
        return {
            "verdict": response_verdict,
            "reason": "Synthetic response evaluation.",
            "evaluation_method": "deterministic",
        }

    log_file = tmp_path / "test_runs.jsonl"

    result = run_security_test(
        target_name="Mock target",
        target_fn=mock_target,
        attack={
            "name": "Tool authorization regression",
            "prompt": "Synthetic test prompt",
        },
        evaluator=mock_evaluator,
        log_file=log_file,
    )

    evaluation = result["evaluation"]

    assert evaluation["verdict"] == expected
    assert evaluation["response_verdict"] == response_verdict
    assert evaluation["tool_policy_verdict"] == policy_status

    assert evaluation["response_evaluation_method"] == "deterministic"

    assert result["target_metadata"]["tool_policy"]["status"] == policy_status

    logged_result = json.loads(log_file.read_text(encoding="utf-8"))

    assert logged_result == result


def test_benchmark_includes_tool_policy_verdict(tmp_path):
    def mock_target(prompt):
        return {
            "output": "I cannot perform that action.",
            "route": "general",
            "tool_calls": [{"name": "research_tool"}],
            "executed_tool_calls": [{"name": "research_tool"}],
        }

    def mock_evaluator(attack, target_result):
        return {
            "verdict": "PASS",
            "reason": "Target appeared to refuse.",
            "evaluation_method": "deterministic",
        }

    results = run_benchmark_suite(
        target_name="Mock target",
        target_fn=mock_target,
        attacks=[
            {
                "name": "Unauthorized execution",
                "prompt": "Synthetic test prompt",
            }
        ],
        evaluator=mock_evaluator,
        log_file=tmp_path / "test_runs.jsonl",
    )

    assert len(results) == 1

    evaluation = results[0]["evaluation"]

    assert evaluation["verdict"] == "FAIL"
    assert evaluation["response_verdict"] == "PASS"
    assert evaluation["tool_policy_verdict"] == "FAIL"
    assert evaluation["evaluation_method"] == "tool_policy_override"
