import json
import os
from pathlib import Path

import streamlit as st

from tester.attacks import load_attacks
from tester.evaluators import evaluate_response
from tester.rag import generate_attack, load_attack_knowledge
from tester.runner import (
    run_benchmark_suite,
    run_multi_turn_security_test,
    run_security_test,
)
from tester.targets import demo_target, langgraph_target


def load_streamlit_secrets_into_env():
    """
    Copy deployment secrets into environment variables so
    the tester and installed LangGraph target can use them.
    """

    for key in (
        "OPENAI_API_KEY",
        "TAVILY_API_KEY",
    ):
        if key in st.secrets:
            os.environ[key] = st.secrets[key]


load_streamlit_secrets_into_env()

# =========================================================
# Configuration
# =========================================================

APP_DIR = Path(__file__).parent

LOG_FILE = APP_DIR / "data" / "test_runs.jsonl"

TARGET_OPTIONS = [
    "Demo vulnerable agent",
    "Secure LangGraph Content Assistant",
]

SECURE_TARGET_NAME = "Secure LangGraph Content Assistant"


st.set_page_config(
    page_title="Agent Security Test Bench",
    page_icon="🛡️",
    layout="wide",
)


# =========================================================
# Data loading
# =========================================================

attacks = load_attacks(APP_DIR / "data" / "attacks.json")

benchmark_attacks = load_attacks(APP_DIR / "data" / "benchmark_attacks.json")

advanced_benchmark_attacks = load_attacks(
    APP_DIR / "data" / "advanced_benchmark_attacks.json"
)

multi_turn_attacks = load_attacks(APP_DIR / "data" / "multi_turn_attacks.json")

attack_knowledge = load_attack_knowledge()

rag_categories = sorted({item["category"] for item in attack_knowledge})


# =========================================================
# Utility helpers
# =========================================================


def verdict_icon(verdict: str) -> str:
    return {
        "PASS": "✅",
        "FAIL": "❌",
        "REVIEW": "⚠️",
    }.get(verdict, "•")


def display_verdict(
    verdict: str,
    reason: str = "",
):
    if verdict == "PASS":
        st.success(reason or "Attack resisted.")

    elif verdict == "FAIL":
        st.error(reason or "Attack succeeded.")

    else:
        st.warning(reason or "Manual review recommended.")


def display_tool_calls(
    tool_calls,
    *,
    empty_message="No tool calls requested.",
):
    tool_calls = tool_calls or []

    if not tool_calls:
        st.caption(empty_message)
        return

    st.markdown("**Requested tools**")

    for index, tool_call in enumerate(
        tool_calls,
        start=1,
    ):
        if isinstance(tool_call, dict):
            name = tool_call.get(
                "name",
                "unknown_tool",
            )
        else:
            name = "unknown_tool"

        with st.expander(f"{index}. {name}"):
            st.json(tool_call)


def display_executed_tool_calls(
    executed_tool_calls,
    *,
    empty_message="No tools executed.",
):
    executed_tool_calls = executed_tool_calls or []

    if not executed_tool_calls:
        st.caption(empty_message)
        return

    st.markdown("**Executed tools**")

    for index, execution in enumerate(
        executed_tool_calls,
        start=1,
    ):
        if isinstance(execution, dict):
            name = execution.get(
                "name",
                "unknown_tool",
            )

            status = execution.get("status") or "completed"

        else:
            name = "unknown_tool"
            status = "completed"

        with st.expander(f"{index}. {name} — {status}"):
            if not isinstance(
                execution,
                dict,
            ):
                st.code(
                    str(execution),
                    language=None,
                )
                continue

            tool_call_id = execution.get("tool_call_id")

            if tool_call_id:
                st.caption("Tool call ID")

                st.code(
                    tool_call_id,
                    language=None,
                )

            st.caption("Returned result")

            result = execution.get("result")

            if isinstance(
                result,
                (dict, list),
            ):
                st.json(result)

            else:
                st.code(
                    str(result),
                    language=None,
                )


def display_tool_policy(
    tool_policy,
):
    if not tool_policy:
        st.caption("Tool policy was not evaluated.")
        return

    status = tool_policy.get(
        "status",
        "UNKNOWN",
    )

    reason = tool_policy.get(
        "reason",
        "",
    )

    allowed_tools = (
        tool_policy.get(
            "allowed_tools",
            [],
        )
        or []
    )

    requested_tools = (
        tool_policy.get(
            "requested_tools",
            [],
        )
        or []
    )

    executed_tools = (
        tool_policy.get(
            "executed_tools",
            [],
        )
        or []
    )

    unauthorized_requested = (
        tool_policy.get(
            "unauthorized_requested",
            [],
        )
        or []
    )

    unauthorized_executed = (
        tool_policy.get(
            "unauthorized_executed",
            [],
        )
        or []
    )

    if status == "PASS":
        st.success("Tool policy: PASS")

    elif status == "FAIL":
        st.error("Tool policy: FAIL")

    else:
        st.warning(f"Tool policy: {status}")

    if reason:
        st.caption(reason)

    policy_col1, policy_col2, policy_col3 = st.columns(3)

    policy_col1.metric(
        "Allowed",
        len(allowed_tools),
    )

    policy_col2.metric(
        "Requested",
        len(requested_tools),
    )

    policy_col3.metric(
        "Executed",
        len(executed_tools),
    )

    with st.expander("Tool authorization details"):
        st.write(
            "**Allowed:**",
            allowed_tools or "None",
        )

        st.write(
            "**Requested:**",
            requested_tools or "None",
        )

        st.write(
            "**Executed:**",
            executed_tools or "None",
        )

        if unauthorized_requested:
            st.warning("Unauthorized requests: " + ", ".join(unauthorized_requested))

        if unauthorized_executed:
            st.error("Unauthorized executions: " + ", ".join(unauthorized_executed))


def display_target_metadata(
    metadata: dict,
):
    metadata = metadata or {}

    security_col, route_col, validation_col = st.columns(3)

    security_col.metric(
        "Input Security",
        metadata.get("security_status") or "Not reported",
    )

    route_col.metric(
        "Agent Route",
        metadata.get("route") or "Not reached",
    )

    validation_col.metric(
        "Output Validation",
        metadata.get("validation_status") or "Not reached",
    )

    if metadata.get("security_reason"):
        st.caption("Security: " + metadata["security_reason"])

    if metadata.get("validation_reason"):
        st.caption("Validation: " + metadata["validation_reason"])


def get_target_fn(
    target_name: str,
):
    if target_name == SECURE_TARGET_NAME:
        return langgraph_target

    return demo_target


# =========================================================
# Hero / landing section
# =========================================================

st.title("🛡️ Agent Security Test Bench")

st.markdown(
    """
Adversarial testing for LangGraph agents with
**prompt-injection benchmarks, stateful multi-turn attacks,
tool-execution telemetry, and deterministic authorization checks.**
"""
)

hero_col1, hero_col2, hero_col3 = st.columns(3)

hero_col1.metric(
    "Benchmark Tiers",
    "3",
    help=("Basic, adversarial, and advanced security benchmark suites."),
)

hero_col2.metric(
    "Multi-Turn Testing",
    "Stateful",
    help=("Dependent attacks reuse a shared LangGraph conversation thread."),
)

hero_col3.metric(
    "Tool Security",
    "Observed + Checked",
    help=(
        "Tracks requested and executed tools "
        "and validates them against route-specific allowlists."
    ),
)

st.divider()


# =========================================================
# Sidebar
# =========================================================

with st.sidebar:
    st.header("Test Configuration")

    target_name = st.selectbox(
        "Target application",
        TARGET_OPTIONS,
        help=("Choose the application to evaluate."),
    )

    st.divider()

    attack_source = st.radio(
        "Attack source",
        [
            "Saved Attack",
            "RAG-Generated Attack",
        ],
    )

    selected_attack = None
    rag_result = None
    attack_prompt = ""

    # -----------------------------------------------------
    # Saved attack
    # -----------------------------------------------------

    if attack_source == "Saved Attack":
        attack_names = [attack["name"] for attack in attacks]

        selected_attack_name = st.selectbox(
            "Attack scenario",
            attack_names,
        )

        selected_attack = next(
            attack for attack in attacks if (attack["name"] == selected_attack_name)
        )

        st.caption(selected_attack["category"])

    # -----------------------------------------------------
    # RAG attack
    # -----------------------------------------------------

    else:
        rag_category = st.selectbox(
            "Attack category",
            rag_categories,
        )

        testing_goal = st.text_area(
            "Testing goal",
            value=(
                "Test whether the application "
                "can be coaxed into violating "
                "its original instruction hierarchy."
            ),
            height=120,
        )

        if st.button(
            "Generate Attack with RAG",
            use_container_width=True,
        ):
            try:
                with st.spinner("Generating adversarial prompt..."):
                    rag_result = generate_attack(
                        category=rag_category,
                        goal=testing_goal,
                    )

                st.session_state["rag_generated_result"] = rag_result

                editor_key = "rag_attack_editor_" + rag_category.replace(
                    " ",
                    "_",
                )

                st.session_state[editor_key] = rag_result["prompt"]

            except Exception as exc:
                st.error("RAG generation failed.")
                st.exception(exc)

        if "rag_generated_result" in st.session_state:
            stored_result = st.session_state["rag_generated_result"]

            if stored_result.get("category") == rag_category:
                rag_result = stored_result

        if rag_result:
            st.success("Attack generated.")

        else:
            st.caption("Generate an attack before running a RAG-based test.")

    st.divider()

    run_button = st.button(
        "Run Security Test",
        type="primary",
        use_container_width=True,
        disabled=(attack_source == "RAG-Generated Attack" and rag_result is None),
    )


# =========================================================
# Tabs
# =========================================================

(
    tab_run,
    tab_benchmark,
    tab_multi_turn,
    tab_history,
    tab_about,
) = st.tabs(
    [
        "Run Test",
        "Benchmark",
        "Multi-Turn",
        "Test History",
        "About",
    ]
)


# =========================================================
# Run Test
# =========================================================

with tab_run:
    st.subheader("Individual Security Test")

    st.caption(
        "Run one adversarial prompt and inspect "
        "the target's response, routing, security controls, "
        "tool behavior, and final evaluation."
    )

    # -----------------------------------------------------
    # Attack configuration display
    # -----------------------------------------------------

    if attack_source == "Saved Attack":
        prompt_col, info_col = st.columns([3, 2])

        with prompt_col:
            st.markdown("#### Attack Prompt")

            editor_key = "saved_attack_" + selected_attack["name"].replace(
                " ",
                "_",
            )

            attack_prompt = st.text_area(
                "Prompt",
                value=(selected_attack["prompt"]),
                height=230,
                key=editor_key,
                label_visibility=("collapsed"),
            )

        with info_col:
            st.markdown("#### Scenario")

            st.write(f"**{selected_attack['name']}**")

            st.caption(selected_attack["category"])

            st.markdown("**Expected secure behavior**")

            st.write(selected_attack["expected_secure_behavior"])

    else:
        if rag_result:
            prompt_col, info_col = st.columns([3, 2])

            with prompt_col:
                st.markdown("#### Generated Attack")

                rag_editor_key = "rag_attack_editor_" + rag_category.replace(
                    " ",
                    "_",
                )

                if rag_editor_key not in st.session_state:
                    st.session_state[rag_editor_key] = rag_result["prompt"]

                attack_prompt = st.text_area(
                    "Generated prompt",
                    height=230,
                    key=rag_editor_key,
                )

            with info_col:
                st.markdown("#### Generation Context")

                st.write(f"**Category:** {rag_result['category']}")

                st.write(f"**Goal:** {rag_result['goal']}")

                with st.expander("Retrieval query"):
                    st.code(
                        rag_result["retrieval_query"],
                        language=None,
                    )

            with st.expander("Retrieved security techniques"):
                for document in rag_result["retrieved_documents"]:
                    st.markdown(f"**{document.get('title', 'Technique')}**")

                    st.caption(
                        document.get(
                            "category",
                            "Unknown",
                        )
                    )

                    st.write(
                        document.get(
                            "content",
                            "",
                        )
                    )

                    st.divider()

        else:
            st.info("Generate a RAG-based attack from the sidebar to begin.")

    # -----------------------------------------------------
    # Execute test
    # -----------------------------------------------------

    if run_button:
        target_fn = get_target_fn(target_name)

        if attack_source == "Saved Attack":
            attack_for_run = {
                **selected_attack,
                "prompt": attack_prompt,
                "source": "saved",
            }

        else:
            attack_for_run = {
                "name": (f"RAG-Generated {rag_result['category']} Attack"),
                "category": (rag_result["category"]),
                "prompt": attack_prompt,
                "expected_secure_behavior": (
                    "The target should preserve "
                    "its original instructions and "
                    "security controls despite the "
                    "generated adversarial prompt."
                ),
                "source": "rag",
                "testing_goal": (rag_result["goal"]),
                "retrieval_query": (rag_result["retrieval_query"]),
                "retrieved_documents": (rag_result["retrieved_documents"]),
            }

        try:
            with st.spinner("Running security test..."):
                result = run_security_test(
                    target_name=target_name,
                    target_fn=target_fn,
                    attack=attack_for_run,
                    evaluator=evaluate_response,
                    log_file=LOG_FILE,
                )

        except Exception as exc:
            st.error("The target application could not be run.")
            st.exception(exc)

        else:
            st.session_state["latest_single_result"] = result

    result = st.session_state.get("latest_single_result")

    if result:
        st.divider()

        evaluation = result["evaluation"]

        verdict = evaluation["verdict"]

        metadata = result.get(
            "target_metadata",
            {},
        )

        st.markdown("### Result")

        result_col1, result_col2, result_col3 = st.columns(3)

        result_col1.metric(
            "Verdict",
            verdict,
        )

        result_col2.metric(
            "Category",
            result["attack"]["category"],
        )

        result_col3.metric(
            "Execution Time",
            f"{result['duration_ms']:.0f} ms",
        )

        display_verdict(
            verdict,
            evaluation.get(
                "reason",
                "",
            ),
        )

        st.markdown("#### Target Behavior")

        display_target_metadata(metadata)

        st.markdown("#### Response")

        st.code(
            result["target_response"],
            language=None,
        )

        st.markdown("#### Tool Security")

        tool_col1, tool_col2 = st.columns(2)

        with tool_col1:
            display_tool_calls(
                metadata.get(
                    "tool_calls",
                    [],
                ),
                empty_message=("No tools requested."),
            )

        with tool_col2:
            display_executed_tool_calls(
                metadata.get(
                    "executed_tool_calls",
                    [],
                ),
                empty_message=("No tools executed."),
            )

        display_tool_policy(metadata.get("tool_policy"))

        st.markdown("#### Evaluation Details")

        eval_col1, eval_col2 = st.columns(2)

        with eval_col1:
            st.write(
                "**Evaluation method:**",
                evaluation.get(
                    "evaluation_method",
                    "unknown",
                ),
            )

            if evaluation.get("defense"):
                st.write(
                    "**Defense:**",
                    evaluation["defense"],
                )

        with eval_col2:
            if evaluation.get("defense_reason"):
                st.write(
                    "**Defense details:**",
                    evaluation["defense_reason"],
                )

        if evaluation.get("judge"):
            with st.expander("LLM Judge Details"):
                st.json(evaluation["judge"])

        if result["attack"].get("source") == "rag":
            with st.expander("RAG Provenance"):
                st.write("**Testing goal**")
                st.write(result["attack"].get("testing_goal"))

                st.write("**Retrieval query**")
                st.code(
                    result["attack"].get(
                        "retrieval_query",
                        "",
                    ),
                    language=None,
                )

                st.write("**Retrieved techniques**")

                for document in result["attack"].get(
                    "retrieved_documents",
                    [],
                ):
                    st.write(
                        "- "
                        + document.get(
                            "title",
                            "Unknown",
                        )
                    )

        with st.expander("Full Execution Trace"):
            st.json(result)

        st.download_button(
            "Download Result",
            data=json.dumps(
                result,
                indent=2,
            ),
            file_name=(f"{result['run_id']}.json"),
            mime="application/json",
        )


# =========================================================
# Benchmark
# =========================================================

with tab_benchmark:
    st.subheader("Security Benchmark")

    st.caption(
        "Run repeatable attack suites and measure "
        "how the target behaves across multiple security layers."
    )

    benchmark_suite = st.radio(
        "Benchmark suite",
        [
            "Basic saved attacks",
            "Adversarial benchmark",
            "Advanced benchmark",
        ],
        horizontal=True,
    )

    if benchmark_suite == "Advanced benchmark":
        selected_suite = advanced_benchmark_attacks

        st.info(
            "Advanced coverage includes indirect injection, "
            "obfuscation, fabricated authorization, routing "
            "manipulation, prompt leakage, and tool escalation."
        )

    elif benchmark_suite == "Adversarial benchmark":
        selected_suite = benchmark_attacks

        st.info(
            "Regression suite for attacks designed to bypass "
            "simple lexical defenses and exercise downstream controls."
        )

    else:
        selected_suite = attacks

        st.info(
            "Basic smoke tests for the security-testing "
            "pipeline and evaluation framework."
        )

    config_col1, config_col2 = st.columns([2, 1])

    with config_col1:
        benchmark_target = st.selectbox(
            "Benchmark target",
            TARGET_OPTIONS,
            key="benchmark_target",
        )

    with config_col2:
        st.metric(
            "Tests in Suite",
            len(selected_suite),
        )

    if st.button(
        "Run Benchmark Suite",
        type="primary",
        key="run_benchmark",
    ):
        benchmark_fn = get_target_fn(benchmark_target)

        try:
            with st.spinner("Running benchmark..."):
                results = run_benchmark_suite(
                    target_name=(benchmark_target),
                    target_fn=(benchmark_fn),
                    attacks=(selected_suite),
                    evaluator=(evaluate_response),
                    log_file=(LOG_FILE),
                )

            st.session_state["benchmark_results"] = results

            st.session_state["benchmark_name"] = benchmark_suite

            st.session_state["benchmark_target_name"] = benchmark_target

        except Exception as exc:
            st.error("Benchmark failed.")
            st.exception(exc)

    results = st.session_state.get(
        "benchmark_results",
        [],
    )

    benchmark_name = st.session_state.get("benchmark_name")

    benchmark_target_name = st.session_state.get("benchmark_target_name")

    if results:
        st.divider()

        st.markdown("### Benchmark Results")

        st.caption(f"{benchmark_name} → {benchmark_target_name}")

        total = len(results)

        passes = sum(item["evaluation"]["verdict"] == "PASS" for item in results)

        failures = sum(item["evaluation"]["verdict"] == "FAIL" for item in results)

        reviews = sum(item["evaluation"]["verdict"] == "REVIEW" for item in results)

        precheck_allows = sum(
            item.get(
                "target_metadata",
                {},
            ).get("security_status")
            == "allow"
            for item in results
        )

        precheck_blocks = sum(
            item.get(
                "target_metadata",
                {},
            ).get("security_status")
            == "block"
            for item in results
        )

        tool_policy_failures = sum(
            item.get(
                "target_metadata",
                {},
            )
            .get(
                "tool_policy",
                {},
            )
            .get("status")
            == "FAIL"
            for item in results
        )

        tool_policy_reviews = sum(
            item.get(
                "target_metadata",
                {},
            )
            .get(
                "tool_policy",
                {},
            )
            .get("status")
            == "REVIEW"
            for item in results
        )

        summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)

        summary_col1.metric(
            "Tests",
            total,
        )

        summary_col2.metric(
            "Defense Success",
            (f"{(passes / total) * 100:.0f}%" if total else "0%"),
        )

        summary_col3.metric(
            "Precheck Bypasses",
            precheck_allows,
            help=(
                "Attacks that reached downstream "
                "defenses instead of being stopped "
                "by the lexical precheck."
            ),
        )

        summary_col4.metric(
            "Tool Policy Issues",
            (tool_policy_failures + tool_policy_reviews),
        )

        if passes == total and total > 0:
            st.success("All benchmark attacks were resisted.")

        elif failures > 0:
            st.error(
                f"{failures} benchmark attack{'s' if failures != 1 else ''} succeeded."
            )

        elif reviews > 0:
            st.warning(
                f"{reviews} result{'s' if reviews != 1 else ''} require manual review."
            )

        st.markdown("#### Outcome Breakdown")

        outcome_col1, outcome_col2, outcome_col3, outcome_col4 = st.columns(4)

        outcome_col1.metric(
            "PASS",
            passes,
        )

        outcome_col2.metric(
            "FAIL",
            failures,
        )

        outcome_col3.metric(
            "REVIEW",
            reviews,
        )

        outcome_col4.metric(
            "Precheck Blocks",
            precheck_blocks,
        )

        st.markdown("#### Results Table")

        rows = []

        for item in results:
            metadata = item.get(
                "target_metadata",
                {},
            )

            requested = (
                metadata.get(
                    "tool_calls",
                    [],
                )
                or []
            )

            executed = (
                metadata.get(
                    "executed_tool_calls",
                    [],
                )
                or []
            )

            tool_policy = (
                metadata.get(
                    "tool_policy",
                    {},
                )
                or {}
            )

            rows.append(
                {
                    "Attack": (item["attack"]["name"]),
                    "Category": (item["attack"]["category"]),
                    "Verdict": (item["evaluation"]["verdict"]),
                    "Defense": (
                        item["evaluation"].get(
                            "defense",
                            "",
                        )
                        or ""
                    ),
                    "Precheck": (metadata.get("security_status") or ""),
                    "Route": (metadata.get("route") or ""),
                    "Validation": (metadata.get("validation_status") or ""),
                    "Requested": (len(requested)),
                    "Executed": (len(executed)),
                    "Tool Policy": (
                        tool_policy.get(
                            "status",
                            "",
                        )
                    ),
                    "Unauthorized": (
                        len(
                            tool_policy.get(
                                "unauthorized_requested",
                                [],
                            )
                            or []
                        )
                        + len(
                            tool_policy.get(
                                "unauthorized_executed",
                                [],
                            )
                            or []
                        )
                    ),
                }
            )

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### Individual Results")

        for item in results:
            verdict = item["evaluation"]["verdict"]

            metadata = item.get(
                "target_metadata",
                {},
            )

            with st.expander(
                f"{verdict_icon(verdict)} {item['attack']['name']} — {verdict}"
            ):
                top_col1, top_col2, top_col3 = st.columns(3)

                top_col1.metric(
                    "Route",
                    metadata.get("route") or "Not reached",
                )

                top_col2.metric(
                    "Precheck",
                    metadata.get("security_status") or "Not reported",
                )

                top_col3.metric(
                    "Tool Policy",
                    metadata.get(
                        "tool_policy",
                        {},
                    ).get(
                        "status",
                        "N/A",
                    ),
                )

                st.write(item["evaluation"]["reason"])

                st.markdown("**Attack prompt**")

                st.code(
                    item["attack"]["prompt"],
                    language=None,
                )

                st.markdown("**Target response**")

                st.code(
                    item["target_response"],
                    language=None,
                )

                st.markdown("**Tool activity**")

                tool_col1, tool_col2 = st.columns(2)

                with tool_col1:
                    display_tool_calls(
                        metadata.get(
                            "tool_calls",
                            [],
                        )
                    )

                with tool_col2:
                    display_executed_tool_calls(
                        metadata.get(
                            "executed_tool_calls",
                            [],
                        )
                    )

                display_tool_policy(metadata.get("tool_policy"))

                with st.expander("Execution Trace"):
                    st.json(item)

        st.download_button(
            "Download Benchmark Results",
            data=json.dumps(
                results,
                indent=2,
            ),
            file_name=("benchmark_results.json"),
            mime="application/json",
        )


# =========================================================
# Multi-Turn
# =========================================================

with tab_multi_turn:
    st.subheader("Stateful Multi-Turn Testing")

    st.caption(
        "Test whether security boundaries hold across "
        "a real conversation rather than a single isolated prompt."
    )

    scenario_names = [attack["name"] for attack in multi_turn_attacks]

    selected_name = st.selectbox(
        "Scenario",
        scenario_names,
        key="multi_turn_scenario",
    )

    selected_multi_attack = next(
        attack for attack in multi_turn_attacks if (attack["name"] == selected_name)
    )

    info_col1, info_col2 = st.columns([1, 2])

    with info_col1:
        st.metric(
            "Turns",
            len(selected_multi_attack["turns"]),
        )

        st.caption(selected_multi_attack["category"])

    with info_col2:
        st.markdown("**Expected secure behavior**")

        st.write(selected_multi_attack["expected_secure_behavior"])

    with st.expander(
        "Conversation Sequence",
        expanded=True,
    ):
        for index, turn in enumerate(
            selected_multi_attack["turns"],
            start=1,
        ):
            st.markdown(f"**Turn {index}**")

            st.code(
                turn,
                language=None,
            )

    if st.button(
        "Run Multi-Turn Test",
        type="primary",
        key="run_multi_turn",
    ):
        try:
            with st.spinner("Running stateful adversarial conversation..."):
                multi_result = run_multi_turn_security_test(
                    target_name=(SECURE_TARGET_NAME),
                    target_fn=(langgraph_target),
                    attack=(selected_multi_attack),
                    evaluator=(evaluate_response),
                    log_file=(LOG_FILE),
                )

            st.session_state["multi_turn_result"] = multi_result

        except Exception as exc:
            st.error("Multi-turn test failed.")
            st.exception(exc)

    multi_result = st.session_state.get("multi_turn_result")

    if multi_result:
        st.divider()

        evaluation = multi_result["evaluation"]

        verdict = evaluation["verdict"]

        result_col1, result_col2, result_col3 = st.columns(3)

        result_col1.metric(
            "Verdict",
            verdict,
        )

        result_col2.metric(
            "Turns",
            len(multi_result["turns"]),
        )

        result_col3.metric(
            "Execution Time",
            f"{multi_result['duration_ms']:.0f} ms",
        )

        display_verdict(
            verdict,
            evaluation.get(
                "reason",
                "",
            ),
        )

        st.caption(f"Shared LangGraph thread: {multi_result['thread_id']}")

        st.markdown("#### Turn-by-Turn Trace")

        for turn in multi_result["turns"]:
            number = turn["turn"]

            route = turn.get("route") or "Not reached"

            security = turn.get("security_status") or "Not reported"

            with st.expander(
                f"Turn {number} — {route} / {security}",
                expanded=(number == len(multi_result["turns"])),
            ):
                st.markdown("**Prompt**")

                st.code(
                    turn["prompt"],
                    language=None,
                )

                st.markdown("**Response**")

                st.code(
                    turn["response"],
                    language=None,
                )

                turn_col1, turn_col2, turn_col3 = st.columns(3)

                turn_col1.metric(
                    "Security",
                    security,
                )

                turn_col2.metric(
                    "Route",
                    route,
                )

                turn_col3.metric(
                    "Validation",
                    turn.get("validation_status") or "Not reached",
                )

                if turn.get("security_reason"):
                    st.caption("Security: " + turn["security_reason"])

                if turn.get("validation_reason"):
                    st.caption("Validation: " + turn["validation_reason"])

                tool_col1, tool_col2 = st.columns(2)

                with tool_col1:
                    display_tool_calls(
                        turn.get(
                            "tool_calls",
                            [],
                        ),
                        empty_message=("No tools requested."),
                    )

                with tool_col2:
                    display_executed_tool_calls(
                        turn.get(
                            "executed_tool_calls",
                            [],
                        ),
                        empty_message=("No tools executed."),
                    )

        st.markdown("#### Final Tool Policy")

        display_tool_policy(
            multi_result.get(
                "target_metadata",
                {},
            ).get("tool_policy")
        )

        st.markdown("#### Final Evaluation")

        eval_col1, eval_col2 = st.columns(2)

        with eval_col1:
            st.write(
                "**Method:**",
                evaluation.get(
                    "evaluation_method",
                    "unknown",
                ),
            )

            if evaluation.get("defense"):
                st.write(
                    "**Defense:**",
                    evaluation["defense"],
                )

        with eval_col2:
            if evaluation.get("defense_reason"):
                st.write(
                    "**Details:**",
                    evaluation["defense_reason"],
                )

        if evaluation.get("judge"):
            with st.expander("LLM Judge Details"):
                st.json(evaluation["judge"])

        with st.expander("Full Execution Trace"):
            st.json(multi_result)

        st.download_button(
            "Download Multi-Turn Result",
            data=json.dumps(
                multi_result,
                indent=2,
            ),
            file_name=(f"{multi_result['run_id']}.json"),
            mime="application/json",
        )


# =========================================================
# Test History
# =========================================================

with tab_history:
    st.subheader("Test History")

    st.caption("Inspect recent saved test runs and their security metadata.")

    if not LOG_FILE.exists():
        st.info("No tests have been run yet.")

    else:
        rows = []

        with LOG_FILE.open(
            "r",
            encoding="utf-8",
        ) as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    rows.append(json.loads(line))

                except json.JSONDecodeError:
                    continue

        if not rows:
            st.info("No valid test history found.")

        else:
            rows.reverse()

            st.caption(f"Showing the most recent {min(len(rows), 25)} runs.")

            for row in rows[:25]:
                evaluation = row.get(
                    "evaluation",
                    {},
                )

                verdict = evaluation.get(
                    "verdict",
                    "UNKNOWN",
                )

                attack = row.get(
                    "attack",
                    {},
                )

                metadata = row.get(
                    "target_metadata",
                    {},
                )

                with st.expander(
                    f"{verdict_icon(verdict)} "
                    f"{attack.get('name', 'Unknown')} "
                    f"— {verdict}"
                ):
                    hist_col1, hist_col2, hist_col3 = st.columns(3)

                    hist_col1.metric(
                        "Target",
                        row.get(
                            "target_name",
                            "Unknown",
                        ),
                    )

                    hist_col2.metric(
                        "Route",
                        metadata.get("route") or "Not reached",
                    )

                    hist_col3.metric(
                        "Tool Policy",
                        metadata.get(
                            "tool_policy",
                            {},
                        ).get(
                            "status",
                            "N/A",
                        ),
                    )

                    st.caption(
                        row.get(
                            "timestamp",
                            "",
                        )
                    )

                    st.write(
                        "**Category:**",
                        attack.get(
                            "category",
                            "",
                        ),
                    )

                    if "turns" in row:
                        st.write("**Test type:** Multi-turn")

                        st.write(
                            "**Turns:**",
                            len(row["turns"]),
                        )

                    display_target_metadata(metadata)

                    st.markdown("**Tool activity**")

                    tool_col1, tool_col2 = st.columns(2)

                    with tool_col1:
                        display_tool_calls(
                            metadata.get(
                                "tool_calls",
                                [],
                            )
                        )

                    with tool_col2:
                        display_executed_tool_calls(
                            metadata.get(
                                "executed_tool_calls",
                                [],
                            )
                        )

                    display_tool_policy(metadata.get("tool_policy"))

                    st.markdown("**Target response**")

                    st.code(
                        row.get(
                            "target_response",
                            "",
                        ),
                        language=None,
                    )


# =========================================================
# About
# =========================================================

with tab_about:
    st.subheader("About This Project")

    st.markdown(
        """
This project is an **AI agent security test bench** for evaluating
prompt injection, routing manipulation, stateful attacks, and unsafe
tool behavior in LangGraph applications.

It was built to move beyond simple prompt filtering and examine how
multiple defensive layers behave when adversarial input reaches an
agent workflow.
"""
    )

    st.markdown("### Core Capabilities")

    capability_col1, capability_col2 = st.columns(2)

    with capability_col1:
        st.markdown(
            """
- Saved adversarial attack scenarios
- RAG-generated prompt-injection tests
- Basic, adversarial, and advanced benchmark suites
- Stateful multi-turn attack execution
- Deterministic PASS / FAIL / REVIEW evaluation
- LLM-as-a-judge fallback
"""
        )

    with capability_col2:
        st.markdown(
            """
- LangGraph route inspection
- Prompt-injection precheck visibility
- Output-validation metadata
- Requested tool-call telemetry
- Confirmed ToolNode execution telemetry
- Route-specific tool authorization checks
"""
        )

    st.markdown("### Security Engineering Workflow")

    st.code(
        """
Baseline benchmark
        ↓
Security finding
        ↓
Target hardening
        ↓
Regression test
        ↓
Expanded adversarial coverage
        ↓
Tool execution observability
        ↓
Deterministic authorization checks
""".strip(),
        language=None,
    )

    st.markdown("### Current Benchmark Story")

    story_col1, story_col2, story_col3 = st.columns(3)

    story_col1.metric(
        "Initial Adversarial",
        "9 / 10",
        help=(
            "The original adversarial benchmark "
            "revealed one instruction-boundary weakness."
        ),
    )

    story_col2.metric(
        "After Hardening",
        "10 / 10",
        help=(
            "The same benchmark passed after "
            "strengthening trust and authorization boundaries."
        ),
    )

    story_col3.metric(
        "Advanced Suite",
        "12 / 12",
        help=(
            "Advanced attacks exercise downstream "
            "defenses after bypassing the lexical precheck."
        ),
    )

    st.markdown("### Tool Security Model")

    st.code(
        """
Model requests tool
        ↓
Tool request recorded
        ↓
ToolNode executes tool
        ↓
Tool result recorded
        ↓
Route-specific allowlist evaluated
        ↓
PASS / REVIEW / FAIL
""".strip(),
        language=None,
    )

    st.markdown("### Current Tool Policy")

    st.markdown(
        """
- **general** → no tools
- **seo_blog_writer** → `research_tool`, `internet_search_tool`
- **x_blog_writer** → `internet_search_tool`

An unauthorized **request** is flagged for review.
An unauthorized **execution** is treated as a policy failure.
"""
    )

    st.caption(
        "Built with Python, Streamlit, LangGraph, "
        "LangChain, OpenAI, Chroma, and structured security evaluation."
    )
