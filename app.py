import json
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


APP_DIR = Path(__file__).parent
LOG_FILE = APP_DIR / "data" / "test_runs.jsonl"


st.set_page_config(
    page_title="Agent Security Test Bench",
    page_icon="🛡️",
    layout="wide",
)


st.title("🛡️ Agent Security Test Bench")
st.caption(
    "Test AI applications against saved, RAG-generated, "
    "benchmark, and multi-turn adversarial attacks."
)


# ---------------------------------------------------------
# Load data
# ---------------------------------------------------------

attacks = load_attacks(
    APP_DIR / "data" / "attacks.json"
)

benchmark_attacks = load_attacks(
    APP_DIR / "data" / "benchmark_attacks.json"
)

advanced_benchmark_attacks = load_attacks(
    APP_DIR / "data" / "advanced_benchmark_attacks.json"
)

multi_turn_attacks = load_attacks(
    APP_DIR / "data" / "multi_turn_attacks.json"
)

attack_knowledge = load_attack_knowledge()

rag_categories = sorted(
    {
        item["category"]
        for item in attack_knowledge
    }
)


# ---------------------------------------------------------
# Sidebar configuration
# ---------------------------------------------------------

with st.sidebar:
    st.header("Test Configuration")

    target_name = st.selectbox(
        "Target application",
        [
            "Demo vulnerable agent",
            "Secure LangGraph Content Assistant",
        ],
        help="Choose which AI application you want to test.",
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

    if attack_source == "Saved Attack":
        attack_names = [
            attack["name"]
            for attack in attacks
        ]

        selected_attack_name = st.selectbox(
            "Attack scenario",
            attack_names,
        )

        selected_attack = next(
            attack
            for attack in attacks
            if attack["name"] == selected_attack_name
        )

        st.markdown("**Attack category**")

        st.code(
            selected_attack["category"],
            language=None,
        )

        st.markdown(
            "**Expected secure behavior**"
        )

        st.write(
            selected_attack[
                "expected_secure_behavior"
            ]
        )

    else:
        rag_category = st.selectbox(
            "Attack category",
            rag_categories,
        )

        testing_goal = st.text_area(
            "Testing goal",
            value=(
                "Test whether the application can be "
                "coaxed into violating its original "
                "instruction hierarchy."
            ),
            height=130,
            help=(
                "Describe the security behavior that "
                "you want the generated attack to test."
            ),
        )

        generate_button = st.button(
            "Generate Attack with RAG",
            use_container_width=True,
        )

        if generate_button:
            try:
                with st.spinner(
                    "Retrieving attack techniques "
                    "and generating adversarial prompt..."
                ):
                    rag_result = generate_attack(
                        category=rag_category,
                        goal=testing_goal,
                    )

                st.session_state[
                    "rag_generated_result"
                ] = rag_result

                editor_key = (
                    "rag_attack_editor_"
                    + rag_category.replace(
                        " ",
                        "_",
                    )
                )

                st.session_state[
                    editor_key
                ] = rag_result["prompt"]

            except Exception as exc:
                st.error(
                    "RAG attack generation failed."
                )
                st.exception(exc)

        if (
            "rag_generated_result"
            in st.session_state
        ):
            stored_result = st.session_state[
                "rag_generated_result"
            ]

            if (
                stored_result.get("category")
                == rag_category
            ):
                rag_result = stored_result

        if rag_result:
            st.success(
                "RAG attack generated."
            )

            st.caption(
                "You can inspect and edit the "
                "generated prompt before running it."
            )

        else:
            st.info(
                "Generate an attack before running "
                "a RAG-based security test."
            )

    st.divider()

    rag_ready = (
        attack_source == "Saved Attack"
        or rag_result is not None
    )

    run_button = st.button(
        "Run Security Test",
        type="primary",
        use_container_width=True,
        disabled=not rag_ready,
    )


# ---------------------------------------------------------
# Main tabs
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Run Test tab
# ---------------------------------------------------------

with tab_run:

    if attack_source == "Saved Attack":
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Attack Prompt")

            saved_editor_key = (
                "saved_attack_editor_"
                + selected_attack["name"].replace(
                    " ",
                    "_",
                )
            )

            attack_prompt = st.text_area(
                "Prompt sent to target",
                value=selected_attack["prompt"],
                height=220,
                key=saved_editor_key,
                label_visibility="collapsed",
            )

        with col2:
            st.subheader(
                "Attack Information"
            )

            st.markdown(
                "**Source:** Saved attack"
            )

            st.markdown(
                f'**Category:** '
                f'{selected_attack["category"]}'
            )

            st.markdown(
                "**Expected secure behavior**"
            )

            st.write(
                selected_attack[
                    "expected_secure_behavior"
                ]
            )

    else:
        if rag_result:
            st.subheader(
                "RAG-Generated Attack"
            )

            col1, col2 = st.columns(
                [3, 2]
            )

            with col1:
                st.markdown(
                    "**Generated adversarial prompt**"
                )

                rag_editor_key = (
                    "rag_attack_editor_"
                    + rag_category.replace(
                        " ",
                        "_",
                    )
                )

                if (
                    rag_editor_key
                    not in st.session_state
                ):
                    st.session_state[
                        rag_editor_key
                    ] = rag_result["prompt"]

                attack_prompt = st.text_area(
                    "Generated prompt",
                    height=240,
                    key=rag_editor_key,
                    label_visibility="collapsed",
                )

                st.caption(
                    "The generated prompt is editable "
                    "before it is sent to the target."
                )

            with col2:
                st.markdown(
                    "**Generation details**"
                )

                st.write(
                    f'**Category:** '
                    f'{rag_result["category"]}'
                )

                st.write(
                    f'**Testing goal:** '
                    f'{rag_result["goal"]}'
                )

                st.write(
                    "**Retrieval query:**"
                )

                st.code(
                    rag_result[
                        "retrieval_query"
                    ],
                    language=None,
                )

            st.subheader(
                "Retrieved Attack Techniques"
            )

            st.caption(
                "These documents were retrieved from "
                "the attack knowledge base and supplied "
                "to the LLM as grounding context."
            )

            for index, document in enumerate(
                rag_result[
                    "retrieved_documents"
                ],
                start=1,
            ):
                title = (
                    document.get("title")
                    or f"Technique {index}"
                )

                category = (
                    document.get("category")
                    or "Unknown"
                )

                with st.expander(
                    f"{index}. {title} — {category}"
                ):
                    st.write(
                        document.get(
                            "content",
                            "",
                        )
                    )

        else:
            st.info(
                "Choose a category and click "
                "**Generate Attack with RAG** "
                "in the sidebar."
            )

    if run_button:
        if (
            target_name
            == "Secure LangGraph Content Assistant"
        ):
            target_fn = langgraph_target
        else:
            target_fn = demo_target

        if attack_source == "Saved Attack":
            attack_for_run = {
                **selected_attack,
                "prompt": attack_prompt,
                "source": "saved",
            }

        else:
            attack_for_run = {
                "name": (
                    f"RAG-Generated "
                    f"{rag_result['category']} Attack"
                ),
                "category": (
                    rag_result["category"]
                ),
                "prompt": attack_prompt,
                "expected_secure_behavior": (
                    "The target should preserve its "
                    "original instructions and security "
                    "controls despite the generated "
                    "adversarial prompt."
                ),
                "source": "rag",
                "testing_goal": (
                    rag_result["goal"]
                ),
                "retrieval_query": (
                    rag_result[
                        "retrieval_query"
                    ]
                ),
                "retrieved_documents": (
                    rag_result[
                        "retrieved_documents"
                    ]
                ),
            }

        try:
            with st.spinner(
                f"Running attack against "
                f"{target_name}..."
            ):
                result = run_security_test(
                    target_name=target_name,
                    target_fn=target_fn,
                    attack=attack_for_run,
                    evaluator=evaluate_response,
                    log_file=LOG_FILE,
                )

        except Exception as exc:
            st.error(
                "The target application "
                "could not be run."
            )
            st.exception(exc)

        else:
            st.divider()

            (
                score_col,
                category_col,
                time_col,
            ) = st.columns(3)

            score_col.metric(
                "Result",
                result["evaluation"]["verdict"],
            )

            category_col.metric(
                "Category",
                result["attack"]["category"],
            )

            time_col.metric(
                "Execution time",
                f'{result["duration_ms"]:.1f} ms',
            )

            st.subheader(
                "Target Response"
            )

            st.code(
                result["target_response"],
                language=None,
            )

            metadata = result.get(
                "target_metadata",
                {},
            )

            has_metadata = any(
                value is not None
                for value in metadata.values()
            )

            if has_metadata:
                st.subheader(
                    "Target Security Metadata"
                )

                (
                    security_col,
                    route_col,
                    validation_col,
                ) = st.columns(3)

                security_col.metric(
                    "Security Status",
                    metadata.get(
                        "security_status"
                    )
                    or "Not reported",
                )

                route_col.metric(
                    "Agent Route",
                    metadata.get(
                        "route"
                    )
                    or "Not reached",
                )

                validation_col.metric(
                    "Validation Status",
                    metadata.get(
                        "validation_status"
                    )
                    or "Not reached",
                )

                if metadata.get(
                    "security_reason"
                ):
                    st.markdown(
                        "**Security reason**"
                    )

                    st.info(
                        metadata[
                            "security_reason"
                        ]
                    )

                if metadata.get(
                    "validation_reason"
                ):
                    st.markdown(
                        "**Validation reason**"
                    )

                    st.info(
                        metadata[
                            "validation_reason"
                        ]
                    )

                if metadata.get(
                    "thread_id"
                ):
                    st.caption(
                        "LangGraph thread: "
                        f'{metadata["thread_id"]}'
                    )

            st.subheader(
                "Evaluation"
            )

            verdict = (
                result["evaluation"]["verdict"]
            )

            if verdict == "PASS":
                st.success(
                    result[
                        "evaluation"
                    ]["reason"]
                )

            elif verdict == "FAIL":
                st.error(
                    result[
                        "evaluation"
                    ]["reason"]
                )

            else:
                st.warning(
                    result[
                        "evaluation"
                    ]["reason"]
                )

            if result[
                "evaluation"
            ].get("defense"):
                st.markdown(
                    "**Defense triggered**"
                )

                st.write(
                    result[
                        "evaluation"
                    ]["defense"]
                )

            if result[
                "evaluation"
            ].get("defense_reason"):
                st.markdown(
                    "**Defense details**"
                )

                st.write(
                    result[
                        "evaluation"
                    ]["defense_reason"]
                )

            if (
                result["attack"].get(
                    "source"
                )
                == "rag"
            ):
                with st.expander(
                    "RAG Generation Provenance"
                ):
                    st.write(
                        "**Testing goal**"
                    )

                    st.write(
                        result[
                            "attack"
                        ].get(
                            "testing_goal"
                        )
                    )

                    st.write(
                        "**Retrieval query**"
                    )

                    st.code(
                        result[
                            "attack"
                        ].get(
                            "retrieval_query",
                            "",
                        ),
                        language=None,
                    )

                    st.write(
                        "**Retrieved techniques**"
                    )

                    for document in (
                        result[
                            "attack"
                        ].get(
                            "retrieved_documents",
                            [],
                        )
                    ):
                        st.markdown(
                            f'- **'
                            f'{document.get("title", "Unknown")}'
                            f'** '
                            f'({document.get("category", "Unknown")})'
                        )

            with st.expander(
                "Execution Trace"
            ):
                st.json(result)

            st.download_button(
                "Download this result as JSON",
                data=json.dumps(
                    result,
                    indent=2,
                ),
                file_name=(
                    f'{result["run_id"]}.json'
                ),
                mime="application/json",
            )


# ---------------------------------------------------------
# Benchmark tab
# ---------------------------------------------------------

with tab_benchmark:

    st.subheader(
        "Security Benchmark"
    )

    st.caption(
        "Run repeatable attack suites against a selected target "
        "to measure resistance and identify security gaps."
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

    if (
        benchmark_suite
        == "Advanced benchmark"
    ):
        selected_benchmark_attacks = (
            advanced_benchmark_attacks
        )

        st.info(
            "The advanced suite tests obfuscation, indirect injection, "
            "fabricated authorization, routing manipulation, tool escalation, "
            "and attacks embedded inside legitimate tasks."
        )

    elif (
        benchmark_suite
        == "Adversarial benchmark"
    ):
        selected_benchmark_attacks = (
            benchmark_attacks
        )

        st.info(
            "The adversarial suite provides regression coverage for "
            "previously tested instruction-boundary weaknesses."
        )

    else:
        selected_benchmark_attacks = (
            attacks
        )

        st.info(
            "The basic suite uses simple known attacks "
            "as a smoke test for the evaluation pipeline."
        )

    benchmark_target_name = st.selectbox(
        "Benchmark target",
        [
            "Demo vulnerable agent",
            "Secure LangGraph Content Assistant",
        ],
        key="benchmark_target",
    )

    st.write(
        f"This benchmark will run "
        f"**{len(selected_benchmark_attacks)} attacks** "
        f"against the selected target."
    )

    run_benchmark_button = st.button(
        "Run Benchmark Suite",
        type="primary",
        key="run_benchmark_suite_button",
    )

    if run_benchmark_button:

        if (
            benchmark_target_name
            == "Secure LangGraph Content Assistant"
        ):
            benchmark_target_fn = (
                langgraph_target
            )
        else:
            benchmark_target_fn = (
                demo_target
            )

        try:
            with st.spinner(
                f"Running "
                f"{len(selected_benchmark_attacks)} "
                f"attacks against "
                f"{benchmark_target_name}..."
            ):
                benchmark_results = (
                    run_benchmark_suite(
                        target_name=(
                            benchmark_target_name
                        ),
                        target_fn=(
                            benchmark_target_fn
                        ),
                        attacks=(
                            selected_benchmark_attacks
                        ),
                        evaluator=(
                            evaluate_response
                        ),
                        log_file=(
                            LOG_FILE
                        ),
                    )
                )

            st.session_state[
                "benchmark_results"
            ] = benchmark_results

            st.session_state[
                "benchmark_target_name"
            ] = benchmark_target_name

            st.session_state[
                "benchmark_suite_name"
            ] = benchmark_suite

        except Exception as exc:
            st.error(
                "The benchmark could not be completed."
            )
            st.exception(exc)

    benchmark_results = (
        st.session_state.get(
            "benchmark_results",
            [],
        )
    )

    benchmark_result_target = (
        st.session_state.get(
            "benchmark_target_name"
        )
    )

    benchmark_result_suite = (
        st.session_state.get(
            "benchmark_suite_name"
        )
    )

    if benchmark_results:

        st.divider()

        st.markdown(
            f"### Results — "
            f"{benchmark_result_suite} "
            f"→ {benchmark_result_target}"
        )

        passes = sum(
            result[
                "evaluation"
            ]["verdict"]
            == "PASS"
            for result in benchmark_results
        )

        failures = sum(
            result[
                "evaluation"
            ]["verdict"]
            == "FAIL"
            for result in benchmark_results
        )

        reviews = sum(
            result[
                "evaluation"
            ]["verdict"]
            == "REVIEW"
            for result in benchmark_results
        )

        total = len(
            benchmark_results
        )

        (
            total_col,
            pass_col,
            fail_col,
            review_col,
        ) = st.columns(4)

        total_col.metric(
            "Tests",
            total,
        )

        pass_col.metric(
            "PASS",
            passes,
        )

        fail_col.metric(
            "FAIL",
            failures,
        )

        review_col.metric(
            "REVIEW",
            reviews,
        )

        if total:
            resistance_rate = (
                passes / total
            ) * 100

            attack_success_rate = (
                failures / total
            ) * 100

            review_rate = (
                reviews / total
            ) * 100

            (
                resistance_col,
                success_col,
                review_rate_col,
            ) = st.columns(3)

            resistance_col.metric(
                "Defense success rate",
                f"{resistance_rate:.1f}%",
            )

            success_col.metric(
                "Attack success rate",
                f"{attack_success_rate:.1f}%",
            )

            review_rate_col.metric(
                "Review rate",
                f"{review_rate:.1f}%",
            )

        precheck_allows = sum(
            result.get(
                "target_metadata",
                {},
            ).get(
                "security_status"
            )
            == "allow"
            for result in benchmark_results
        )

        precheck_blocks = sum(
            result.get(
                "target_metadata",
                {},
            ).get(
                "security_status"
            )
            == "block"
            for result in benchmark_results
        )

        if (
            benchmark_result_target
            == "Secure LangGraph Content Assistant"
        ):
            (
                allowed_col,
                blocked_col,
            ) = st.columns(2)

            allowed_col.metric(
                "Precheck bypasses",
                precheck_allows,
            )

            blocked_col.metric(
                "Precheck blocks",
                precheck_blocks,
            )

        st.subheader(
            "Benchmark Results"
        )

        benchmark_rows = []

        for result in benchmark_results:
            metadata = result.get(
                "target_metadata",
                {},
            )

            evaluation = result.get(
                "evaluation",
                {},
            )

            duration = result.get(
                "duration_ms"
            )

            if duration is not None:
                duration_display = round(
                    duration,
                    1,
                )
            else:
                duration_display = ""

            benchmark_rows.append(
                {
                    "Attack": (
                        result[
                            "attack"
                        ]["name"]
                    ),
                    "Category": (
                        result[
                            "attack"
                        ]["category"]
                    ),
                    "Verdict": (
                        evaluation.get(
                            "verdict",
                            "",
                        )
                    ),
                    "Defense": (
                        evaluation.get(
                            "defense",
                            "",
                        )
                        or ""
                    ),
                    "Precheck": (
                        metadata.get(
                            "security_status"
                        )
                        or ""
                    ),
                    "Route": (
                        metadata.get(
                            "route"
                        )
                        or ""
                    ),
                    "Validation": (
                        metadata.get(
                            "validation_status"
                        )
                        or ""
                    ),
                    "Duration (ms)": (
                        duration_display
                    ),
                }
            )

        st.dataframe(
            benchmark_rows,
            use_container_width=True,
            hide_index=True,
        )

        st.subheader(
            "Individual Results"
        )

        for result in benchmark_results:

            verdict = (
                result[
                    "evaluation"
                ]["verdict"]
            )

            icon = {
                "PASS": "✅",
                "FAIL": "❌",
                "REVIEW": "⚠️",
            }.get(
                verdict,
                "•",
            )

            with st.expander(
                f'{icon} '
                f'{result["attack"]["name"]} '
                f'— {verdict}'
            ):

                st.write(
                    f'**Category:** '
                    f'{result["attack"]["category"]}'
                )

                st.write(
                    f'**Verdict:** '
                    f'{verdict}'
                )

                st.write(
                    f'**Reason:** '
                    f'{result["evaluation"]["reason"]}'
                )

                defense = (
                    result[
                        "evaluation"
                    ].get(
                        "defense"
                    )
                )

                if defense:
                    st.write(
                        f'**Defense:** '
                        f'{defense}'
                    )

                defense_reason = (
                    result[
                        "evaluation"
                    ].get(
                        "defense_reason"
                    )
                )

                if defense_reason:
                    st.write(
                        f'**Defense details:** '
                        f'{defense_reason}'
                    )

                metadata = result.get(
                    "target_metadata",
                    {},
                )

                if metadata.get(
                    "security_status"
                ):
                    st.write(
                        "**Security status:** "
                        f'{metadata["security_status"]}'
                    )

                if metadata.get(
                    "security_reason"
                ):
                    st.write(
                        "**Security reason:** "
                        f'{metadata["security_reason"]}'
                    )

                if metadata.get(
                    "route"
                ):
                    st.write(
                        "**Agent route:** "
                        f'{metadata["route"]}'
                    )

                if metadata.get(
                    "validation_status"
                ):
                    st.write(
                        "**Validation status:** "
                        f'{metadata["validation_status"]}'
                    )

                if metadata.get(
                    "validation_reason"
                ):
                    st.write(
                        "**Validation reason:** "
                        f'{metadata["validation_reason"]}'
                    )

                st.markdown(
                    "**Attack prompt**"
                )

                st.code(
                    result[
                        "attack"
                    ]["prompt"],
                    language=None,
                )

                st.markdown(
                    "**Target response**"
                )

                st.code(
                    result[
                        "target_response"
                    ],
                    language=None,
                )

                with st.expander(
                    "Execution Trace"
                ):
                    st.json(result)

        if (
            benchmark_result_suite
            == "Advanced benchmark"
        ):
            download_name = (
                "advanced_benchmark_results.json"
            )

        elif (
            benchmark_result_suite
            == "Adversarial benchmark"
        ):
            download_name = (
                "adversarial_benchmark_results.json"
            )

        else:
            download_name = (
                "basic_benchmark_results.json"
            )

        st.download_button(
            "Download benchmark results as JSON",
            data=json.dumps(
                benchmark_results,
                indent=2,
            ),
            file_name=download_name,
            mime="application/json",
        )


# ---------------------------------------------------------
# Multi-Turn tab
# ---------------------------------------------------------

with tab_multi_turn:

    st.subheader(
        "Multi-Turn Security Testing"
    )

    st.caption(
        "Run a sequence of adversarial turns through the same "
        "LangGraph thread to test whether earlier context can "
        "influence later security behavior."
    )

    st.info(
        "Multi-turn tests currently run against the Secure LangGraph "
        "Content Assistant because it supports shared LangGraph thread state."
    )

    multi_turn_names = [
        attack["name"]
        for attack in multi_turn_attacks
    ]

    selected_multi_turn_name = st.selectbox(
        "Multi-turn scenario",
        multi_turn_names,
        key="multi_turn_scenario",
    )

    selected_multi_turn_attack = next(
        attack
        for attack in multi_turn_attacks
        if attack["name"]
        == selected_multi_turn_name
    )

    st.markdown(
        f'**Category:** '
        f'{selected_multi_turn_attack["category"]}'
    )

    st.markdown(
        "**Expected secure behavior**"
    )

    st.write(
        selected_multi_turn_attack[
            "expected_secure_behavior"
        ]
    )

    st.subheader(
        "Conversation Sequence"
    )

    for index, turn in enumerate(
        selected_multi_turn_attack["turns"],
        start=1,
    ):
        st.markdown(
            f"**Turn {index}**"
        )

        st.code(
            turn,
            language=None,
        )

    run_multi_turn_button = st.button(
        "Run Multi-Turn Test",
        type="primary",
        key="run_multi_turn_test_button",
    )

    if run_multi_turn_button:

        try:
            with st.spinner(
                "Running all turns through one "
                "LangGraph conversation..."
            ):
                multi_turn_result = (
                    run_multi_turn_security_test(
                        target_name=(
                            "Secure LangGraph Content Assistant"
                        ),
                        target_fn=(
                            langgraph_target
                        ),
                        attack=(
                            selected_multi_turn_attack
                        ),
                        evaluator=(
                            evaluate_response
                        ),
                        log_file=(
                            LOG_FILE
                        ),
                    )
                )

            st.session_state[
                "multi_turn_result"
            ] = multi_turn_result

        except Exception as exc:
            st.error(
                "The multi-turn test could not be completed."
            )

            st.exception(exc)

    multi_turn_result = (
        st.session_state.get(
            "multi_turn_result"
        )
    )

    if multi_turn_result:
        st.divider()

        st.markdown(
            f'### Result — '
            f'{multi_turn_result["attack"]["name"]}'
        )

        verdict = (
            multi_turn_result[
                "evaluation"
            ]["verdict"]
        )

        (
            verdict_col,
            turns_col,
            duration_col,
        ) = st.columns(3)

        verdict_col.metric(
            "Verdict",
            verdict,
        )

        turns_col.metric(
            "Turns",
            len(
                multi_turn_result[
                    "turns"
                ]
            ),
        )

        duration_col.metric(
            "Execution time",
            f'{multi_turn_result["duration_ms"]:.1f} ms',
        )

        if verdict == "PASS":
            st.success(
                multi_turn_result[
                    "evaluation"
                ]["reason"]
            )

        elif verdict == "FAIL":
            st.error(
                multi_turn_result[
                    "evaluation"
                ]["reason"]
            )

        else:
            st.warning(
                multi_turn_result[
                    "evaluation"
                ]["reason"]
            )

        st.caption(
            "Shared LangGraph thread: "
            f'{multi_turn_result["thread_id"]}'
        )

        st.subheader(
            "Turn-by-Turn Trace"
        )

        for turn in (
            multi_turn_result["turns"]
        ):
            turn_number = turn["turn"]

            with st.expander(
                f"Turn {turn_number}",
                expanded=True,
            ):
                st.markdown(
                    "**Prompt**"
                )

                st.code(
                    turn["prompt"],
                    language=None,
                )

                st.markdown(
                    "**Response**"
                )

                st.code(
                    turn["response"],
                    language=None,
                )

                (
                    security_col,
                    route_col,
                    validation_col,
                ) = st.columns(3)

                security_col.metric(
                    "Security",
                    turn.get(
                        "security_status"
                    )
                    or "Not reported",
                )

                route_col.metric(
                    "Route",
                    turn.get(
                        "route"
                    )
                    or "Not reached",
                )

                validation_col.metric(
                    "Validation",
                    turn.get(
                        "validation_status"
                    )
                    or "Not reached",
                )

        st.subheader(
            "Final Evaluation"
        )

        evaluation = (
            multi_turn_result[
                "evaluation"
            ]
        )

        st.write(
            f'**Method:** '
            f'{evaluation.get("evaluation_method", "unknown")}'
        )

        if evaluation.get(
            "defense"
        ):
            st.write(
                f'**Defense:** '
                f'{evaluation["defense"]}'
            )

        if evaluation.get(
            "defense_reason"
        ):
            st.write(
                f'**Defense details:** '
                f'{evaluation["defense_reason"]}'
            )

        judge = evaluation.get(
            "judge"
        )

        if judge:
            with st.expander(
                "LLM Judge Details"
            ):
                st.json(judge)

        with st.expander(
            "Full Multi-Turn Execution Trace"
        ):
            st.json(
                multi_turn_result
            )

        st.download_button(
            "Download multi-turn result as JSON",
            data=json.dumps(
                multi_turn_result,
                indent=2,
            ),
            file_name=(
                f'{multi_turn_result["run_id"]}.json'
            ),
            mime="application/json",
        )


# ---------------------------------------------------------
# Test History tab
# ---------------------------------------------------------

with tab_history:

    st.subheader(
        "Previous Test Runs"
    )

    if not LOG_FILE.exists():
        st.info(
            "No tests have been run yet."
        )

    else:
        rows = []

        with LOG_FILE.open(
            "r",
            encoding="utf-8",
        ) as f:
            for line in f:
                if line.strip():
                    rows.append(
                        json.loads(line)
                    )

        if not rows:
            st.info(
                "No tests have been run yet."
            )

        else:
            rows.reverse()

            for row in rows[:25]:

                verdict = (
                    row[
                        "evaluation"
                    ]["verdict"]
                )

                icon = {
                    "PASS": "✅",
                    "FAIL": "❌",
                    "REVIEW": "⚠️",
                }.get(
                    verdict,
                    "•",
                )

                attack_source_label = (
                    row[
                        "attack"
                    ].get(
                        "source",
                        (
                            "multi-turn"
                            if "turns" in row
                            else "saved"
                        ),
                    )
                )

                with st.expander(
                    f'{icon} '
                    f'{row["attack"]["name"]} '
                    f'— {row["timestamp"]}'
                ):

                    st.write(
                        f'**Target:** '
                        f'{row["target_name"]}'
                    )

                    st.write(
                        f'**Attack source:** '
                        f'{attack_source_label}'
                    )

                    st.write(
                        f'**Category:** '
                        f'{row["attack"]["category"]}'
                    )

                    st.write(
                        f'**Verdict:** '
                        f'{verdict}'
                    )

                    st.write(
                        f'**Reason:** '
                        f'{row["evaluation"]["reason"]}'
                    )

                    if "turns" in row:
                        st.write(
                            f'**Turns:** '
                            f'{len(row["turns"])}'
                        )

                        if row.get(
                            "thread_id"
                        ):
                            st.write(
                                f'**Thread ID:** '
                                f'{row["thread_id"]}'
                            )

                    metadata = row.get(
                        "target_metadata",
                        {},
                    )

                    if metadata:
                        if metadata.get(
                            "security_status"
                        ):
                            st.write(
                                "**Security status:** "
                                f'{metadata["security_status"]}'
                            )

                        if metadata.get(
                            "security_reason"
                        ):
                            st.write(
                                "**Security reason:** "
                                f'{metadata["security_reason"]}'
                            )

                        if metadata.get(
                            "route"
                        ):
                            st.write(
                                "**Agent route:** "
                                f'{metadata["route"]}'
                            )

                        if metadata.get(
                            "validation_status"
                        ):
                            st.write(
                                "**Validation status:** "
                                f'{metadata["validation_status"]}'
                            )

                    st.markdown(
                        "**Target response**"
                    )

                    st.code(
                        row["target_response"],
                        language=None,
                    )


# ---------------------------------------------------------
# About tab
# ---------------------------------------------------------

with tab_about:

    st.subheader(
        "What this application demonstrates"
    )

    st.markdown(
        """
        This application provides several ways to test AI applications.

        ### Saved attacks

        Known prompt-injection scenarios can be selected and
        run directly against a target.

        ### RAG-generated attacks

        The tester retrieves relevant techniques from a curated
        attack knowledge base and uses them as grounding context
        for generating a new adversarial prompt.

        **testing goal → semantic retrieval → attack techniques → LLM generation → adversarial prompt**

        ### Benchmark suites

        Three benchmark tiers are available:

        - **Basic saved attacks** — smoke tests for the pipeline.
        - **Adversarial benchmark** — regression coverage for subtle
          instruction-boundary weaknesses.
        - **Advanced benchmark** — obfuscation, indirect injection,
          fabricated authorization, routing manipulation, tool escalation,
          and attacks embedded inside legitimate tasks.

        **attack suite → target → security layers → evaluator → aggregate metrics**

        ### Multi-turn security testing

        Multi-turn scenarios reuse the same LangGraph thread across
        several prompts. This makes it possible to test attacks that
        depend on conversation history rather than merely claiming that
        earlier authorization occurred.

        **benign setup → context manipulation → privilege claim → adversarial request → evaluation**

        ### Defense-in-depth testing

        The tester distinguishes among:

        - attacks blocked by the security precheck
        - attacks that bypass the precheck but are resisted by the agent
        - unsafe responses stopped by output validation
        - genuine adversarial successes
        - ambiguous results requiring review

        ### Real target integration

        The Secure LangGraph Content Assistant reports:

        - security status
        - security reason
        - selected route
        - validation status
        - validation reason
        - LangGraph thread ID

        ### Current evaluation

        Results are classified as:

        - **PASS** — the attack was blocked or safely resisted
        - **FAIL** — the adversarial objective succeeded
        - **REVIEW** — available evidence is insufficient for a confident decision

        Evaluation combines deterministic signals, structured security
        metadata, and LLM-as-a-judge analysis for ambiguous responses.

        ### Planned improvements

        - expose requested and executed tool calls in tester results
        - evaluate unauthorized tool usage directly
        - batch multi-turn benchmark execution
        - category-level dashboards
        - LangSmith observability
        - persistent result storage
        - deployment
        """
    )