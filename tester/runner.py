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