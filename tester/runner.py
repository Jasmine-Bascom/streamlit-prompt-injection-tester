from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid


def _normalize_target_result(
    raw_target_result,
    *,
    thread_id=None,
) -> dict:
    """
    Normalize target outputs so the tester has a consistent
    structure regardless of target implementation.
    """

    if isinstance(
        raw_target_result,
        str,
    ):
        return {
            "output": raw_target_result,
            "security_status": None,
            "security_reason": None,
            "route": None,
            "validation_status": None,
            "validation_reason": None,
            "tool_calls": [],
            "thread_id": thread_id,
        }

    if isinstance(
        raw_target_result,
        dict,
    ):
        return {
            "output": raw_target_result.get(
                "output",
                "",
            ),
            "security_status": (
                raw_target_result.get(
                    "security_status"
                )
            ),
            "security_reason": (
                raw_target_result.get(
                    "security_reason"
                )
            ),
            "route": (
                raw_target_result.get(
                    "route"
                )
            ),
            "validation_status": (
                raw_target_result.get(
                    "validation_status"
                )
            ),
            "validation_reason": (
                raw_target_result.get(
                    "validation_reason"
                )
            ),
            "tool_calls": (
                raw_target_result.get(
                    "tool_calls",
                    [],
                )
                or []
            ),
            "thread_id": (
                raw_target_result.get(
                    "thread_id"
                )
                or thread_id
            ),
        }

    return {
        "output": str(
            raw_target_result
        ),
        "security_status": None,
        "security_reason": None,
        "route": None,
        "validation_status": None,
        "validation_reason": None,
        "tool_calls": [],
        "thread_id": thread_id,
    }


def _target_metadata(
    target_result: dict,
) -> dict:
    """
    Extract the structured target metadata stored with
    a test result.
    """

    return {
        "security_status": (
            target_result.get(
                "security_status"
            )
        ),
        "security_reason": (
            target_result.get(
                "security_reason"
            )
        ),
        "route": (
            target_result.get(
                "route"
            )
        ),
        "validation_status": (
            target_result.get(
                "validation_status"
            )
        ),
        "validation_reason": (
            target_result.get(
                "validation_reason"
            )
        ),
        "tool_calls": (
            target_result.get(
                "tool_calls",
                [],
            )
            or []
        ),
        "thread_id": (
            target_result.get(
                "thread_id"
            )
        ),
    }


def _write_log(
    *,
    log_file: Path,
    result: dict,
):
    """
    Append one structured result to the JSONL log.
    """

    log_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with log_file.open(
        "a",
        encoding="utf-8",
    ) as f:
        f.write(
            json.dumps(
                result
            )
            + "\n"
        )


def run_security_test(
    *,
    target_name: str,
    target_fn,
    attack: dict,
    evaluator,
    log_file: Path,
) -> dict:
    """
    Run a single security attack against a target.
    """

    run_id = (
        f"run-{uuid.uuid4().hex[:10]}"
    )

    started = time.perf_counter()

    raw_target_result = target_fn(
        attack["prompt"]
    )

    duration_ms = (
        time.perf_counter()
        - started
    ) * 1000

    target_result = (
        _normalize_target_result(
            raw_target_result
        )
    )

    evaluation = evaluator(
        attack,
        target_result,
    )

    result = {
        "run_id": run_id,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "target_name": target_name,
        "attack": attack,
        "target_response": (
            target_result.get(
                "output",
                "",
            )
        ),
        "target_metadata": (
            _target_metadata(
                target_result
            )
        ),
        "evaluation": evaluation,
        "duration_ms": duration_ms,
    }

    _write_log(
        log_file=log_file,
        result=result,
    )

    return result


def run_benchmark_suite(
    *,
    target_name: str,
    target_fn,
    attacks: list[dict],
    evaluator,
    log_file: Path,
) -> list[dict]:
    """
    Run a collection of attacks against one target and
    return all test results.
    """

    results = []

    for attack in attacks:
        attack_for_run = {
            **attack,
            "source": attack.get(
                "source",
                "saved",
            ),
        }

        result = run_security_test(
            target_name=target_name,
            target_fn=target_fn,
            attack=attack_for_run,
            evaluator=evaluator,
            log_file=log_file,
        )

        results.append(
            result
        )

    return results


def run_multi_turn_security_test(
    *,
    target_name: str,
    target_fn,
    attack: dict,
    evaluator,
    log_file: Path,
) -> dict:
    """
    Run a sequence of attack turns against the same
    LangGraph thread.

    Each turn records its own security status, route,
    validation status, response, and requested tool calls.
    """

    run_id = (
        f"multi-{uuid.uuid4().hex[:10]}"
    )

    thread_id = (
        f"security-test-"
        f"{uuid.uuid4().hex[:8]}"
    )

    turns = attack["turns"]

    turn_results = []

    started = time.perf_counter()

    final_target_result = None

    for index, prompt in enumerate(
        turns,
        start=1,
    ):
        raw_result = target_fn(
            prompt,
            thread_id=thread_id,
        )

        target_result = (
            _normalize_target_result(
                raw_result,
                thread_id=thread_id,
            )
        )

        turn_results.append(
            {
                "turn": index,
                "prompt": prompt,
                "response": (
                    target_result.get(
                        "output",
                        "",
                    )
                ),
                "security_status": (
                    target_result.get(
                        "security_status"
                    )
                ),
                "security_reason": (
                    target_result.get(
                        "security_reason"
                    )
                ),
                "route": (
                    target_result.get(
                        "route"
                    )
                ),
                "validation_status": (
                    target_result.get(
                        "validation_status"
                    )
                ),
                "validation_reason": (
                    target_result.get(
                        "validation_reason"
                    )
                ),
                "tool_calls": (
                    target_result.get(
                        "tool_calls",
                        [],
                    )
                    or []
                ),
            }
        )

        final_target_result = (
            target_result
        )

    duration_ms = (
        time.perf_counter()
        - started
    ) * 1000

    evaluation_attack = {
        **attack,
        "prompt": (
            "\n\n".join(
                (
                    f"Turn {index}: "
                    f"{prompt}"
                )
                for index, prompt
                in enumerate(
                    turns,
                    start=1,
                )
            )
        ),
    }

    evaluation = evaluator(
        evaluation_attack,
        final_target_result,
    )

    result = {
        "run_id": run_id,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "target_name": target_name,
        "attack": attack,
        "thread_id": thread_id,
        "turns": turn_results,
        "target_response": (
            final_target_result.get(
                "output",
                "",
            )
        ),
        "target_metadata": (
            _target_metadata(
                final_target_result
            )
        ),
        "evaluation": evaluation,
        "duration_ms": duration_ms,
    }

    _write_log(
        log_file=log_file,
        result=result,
    )

    return result