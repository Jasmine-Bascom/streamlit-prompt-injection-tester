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

    response = target_fn(
        attack["prompt"]
    )

    duration_ms = (
        time.perf_counter() - started
    ) * 1000

    evaluation = evaluator(
        attack,
        response,
    )

    result = {
        "run_id": run_id,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "target_name": target_name,
        "attack": attack,
        "target_response": response,
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