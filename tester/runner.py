from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid


def run_security_test(
    *,
    target_name: str,
    target_fn,
    attack: dict,
    evaluator,
    log_file: Path,
) -> dict:
    run_id = f"run-{uuid.uuid4().hex[:10]}"

    started = time.perf_counter()

    raw_target_result = target_fn(
        attack["prompt"]
    )

    duration_ms = (
        time.perf_counter() - started
    ) * 1000

    # -----------------------------------------------------
    # Normalize different target types.
    #
    # The demo returns a string.
    # The real LangGraph target returns a metadata dictionary.
    # -----------------------------------------------------

    if isinstance(raw_target_result, str):
        target_result = {
            "output": raw_target_result,
            "security_status": None,
            "security_reason": None,
            "route": None,
            "validation_status": None,
            "validation_reason": None,
            "thread_id": None,
        }

    elif isinstance(raw_target_result, dict):
        target_result = raw_target_result

    else:
        target_result = {
            "output": str(raw_target_result),
            "security_status": None,
            "security_reason": None,
            "route": None,
            "validation_status": None,
            "validation_reason": None,
            "thread_id": None,
        }

    evaluation = evaluator(
        attack,
        target_result,
    )

    target_metadata = {
        "security_status": target_result.get(
            "security_status"
        ),
        "security_reason": target_result.get(
            "security_reason"
        ),
        "route": target_result.get(
            "route"
        ),
        "validation_status": target_result.get(
            "validation_status"
        ),
        "validation_reason": target_result.get(
            "validation_reason"
        ),
        "thread_id": target_result.get(
            "thread_id"
        ),
    }

    result = {
        "run_id": run_id,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "target_name": target_name,
        "attack": attack,
        "target_response": target_result.get(
            "output",
            "",
        ),
        "target_metadata": target_metadata,
        "evaluation": evaluation,
        "duration_ms": duration_ms,
    }

    log_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with log_file.open(
        "a",
        encoding="utf-8",
    ) as f:
        f.write(
            json.dumps(result) + "\n"
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
            "source": attack.get("source", "saved"),
        }

        result = run_security_test(
            target_name=target_name,
            target_fn=target_fn,
            attack=attack_for_run,
            evaluator=evaluator,
            log_file=log_file,
        )

        results.append(result)

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
    Run a sequence of attack turns against the same target thread.
    """

    run_id = (
        f"multi-{uuid.uuid4().hex[:10]}"
    )

    thread_id = (
        f"security-test-{uuid.uuid4().hex[:8]}"
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

        if isinstance(
            raw_result,
            dict,
        ):
            target_result = raw_result

        else:
            target_result = {
                "output": str(
                    raw_result
                ),
                "security_status": None,
                "security_reason": None,
                "route": None,
                "validation_status": None,
                "validation_reason": None,
                "thread_id": thread_id,
            }

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
            }
        )

        final_target_result = (
            target_result
        )

    duration_ms = (
        time.perf_counter() - started
    ) * 1000

    evaluation_attack = {
        **attack,
        "prompt": (
            "\n\n".join(
                f"Turn {i}: {prompt}"
                for i, prompt in enumerate(
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
        "target_metadata": {
            "security_status": (
                final_target_result.get(
                    "security_status"
                )
            ),
            "security_reason": (
                final_target_result.get(
                    "security_reason"
                )
            ),
            "route": (
                final_target_result.get(
                    "route"
                )
            ),
            "validation_status": (
                final_target_result.get(
                    "validation_status"
                )
            ),
            "validation_reason": (
                final_target_result.get(
                    "validation_reason"
                )
            ),
            "thread_id": thread_id,
        },
        "evaluation": evaluation,
        "duration_ms": duration_ms,
    }

    log_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with log_file.open(
        "a",
        encoding="utf-8",
    ) as f:
        f.write(
            json.dumps(result)
            + "\n"
        )

    return result