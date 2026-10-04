import json
from pathlib import Path

import streamlit as st

from tester.attacks import load_attacks
from tester.evaluators import evaluate_response
from tester.rag import (
    generate_attack,
    load_attack_knowledge,
)
from tester.runner import (
    run_benchmark_suite,
    run_multi_turn_security_test,
    run_security_test,
)
from tester.targets import (
    demo_target,
    langgraph_target,
)


APP_DIR = Path(__file__).parent

LOG_FILE = (
    APP_DIR
    / "data"
    / "test_runs.jsonl"
)


st.set_page_config(
    page_title="Agent Security Test Bench",
    page_icon="🛡️",
    layout="wide",
)


st.title(
    "🛡️ Agent Security Test Bench"
)

st.caption(
    "Test AI applications against saved, RAG-generated, "
    "benchmark, and multi-turn adversarial attacks."
)


# ---------------------------------------------------------
# Load data
# ---------------------------------------------------------

attacks = load_attacks(
    APP_DIR
    / "data"
    / "attacks.json"
)

benchmark_attacks = load_attacks(
    APP_DIR
    / "data"
    / "benchmark_attacks.json"
)

advanced_benchmark_attacks = (
    load_attacks(
        APP_DIR
        / "data"
        / "advanced_benchmark_attacks.json"
    )
)

multi_turn_attacks = load_attacks(
    APP_DIR
    / "data"
    / "multi_turn_attacks.json"
)

attack_knowledge = (
    load_attack_knowledge()
)

rag_categories = sorted(
    {
        item["category"]
        for item in attack_knowledge
    }
)


# ---------------------------------------------------------
# Shared tool-call displays
# ---------------------------------------------------------

def display_tool_calls(
    tool_calls,
    *,
    empty_message="No tool calls requested.",
):
    """
    Display tool calls requested by the model.
    """

    tool_calls = (
        tool_calls
        or []
    )

    if not tool_calls:
        st.caption(
            empty_message
        )
        return

    st.markdown(
        "**Tool calls requested**"
    )

    for index, tool_call in enumerate(
        tool_calls,
        start=1,
    ):
        if isinstance(
            tool_call,
            dict,
        ):
            name = (
                tool_call.get(
                    "name",
                    "unknown_tool",
                )
            )
        else:
            name = (
                "unknown_tool"
            )

        with st.expander(
            f"{index}. {name}"
        ):
            st.json(
                tool_call
            )


def display_executed_tool_calls(
    executed_tool_calls,
    *,
    empty_message="No tools executed.",
):
    """
    Display tool calls confirmed as executed by ToolNode.
    """

    executed_tool_calls = (
        executed_tool_calls
        or []
    )

    if not executed_tool_calls:
        st.caption(
            empty_message
        )
        return

    st.markdown(
        "**Tools actually executed**"
    )

    for index, execution in enumerate(
        executed_tool_calls,
        start=1,
    ):
        name = (
            execution.get(
                "name",
                "unknown_tool",
            )
            if isinstance(
                execution,
                dict,
            )
            else "unknown_tool"
        )

        status = (
            execution.get(
                "status"
            )
            if isinstance(
                execution,
                dict,
            )
            else None
        )

        status = (
            status
            or "completed"
        )

        with st.expander(
            f"{index}. {name} — {status}"
        ):
            if isinstance(
                execution,
                dict,
            ):
                tool_call_id = (
                    execution.get(
                        "tool_call_id"
                    )
                )

                if tool_call_id:
                    st.write(
                        "**Tool call ID**"
                    )

                    st.code(
                        tool_call_id,
                        language=None,
                    )

                st.write(
                    "**Returned result**"
                )

                result = (
                    execution.get(
                        "result"
                    )
                )

                if isinstance(
                    result,
                    (
                        dict,
                        list,
                    ),
                ):
                    st.json(
                        result
                    )

                else:
                    st.code(
                        str(result),
                        language=None,
                    )

            else:
                st.code(
                    str(execution),
                    language=None,
                )


# ---------------------------------------------------------
# Sidebar configuration
# ---------------------------------------------------------

with st.sidebar:
    st.header(
        "Test Configuration"
    )

    target_name = st.selectbox(
        "Target application",
        [
            "Demo vulnerable agent",
            (
                "Secure LangGraph "
                "Content Assistant"
            ),
        ],
        help=(
            "Choose which AI application "
            "you want to test."
        ),
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

    if (
        attack_source
        == "Saved Attack"
    ):
        attack_names = [
            attack["name"]
            for attack in attacks
        ]

        selected_attack_name = (
            st.selectbox(
                "Attack scenario",
                attack_names,
            )
        )

        selected_attack = next(
            attack
            for attack in attacks
            if (
                attack["name"]
                == selected_attack_name
            )
        )

        st.markdown(
            "**Attack category**"
        )

        st.code(
            selected_attack[
                "category"
            ],
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

    # -----------------------------------------------------
    # RAG attack
    # -----------------------------------------------------

    else:
        rag_category = (
            st.selectbox(
                "Attack category",
                rag_categories,
            )
        )

        testing_goal = (
            st.text_area(
                "Testing goal",
                value=(
                    "Test whether the application "
                    "can be coaxed into violating "
                    "its original instruction "
                    "hierarchy."
                ),
                height=130,
                help=(
                    "Describe the security behavior "
                    "that you want the generated "
                    "attack to test."
                ),
            )
        )

        generate_button = (
            st.button(
                "Generate Attack with RAG",
                use_container_width=True,
            )
        )

        if generate_button:
            try:
                with st.spinner(
                    "Retrieving attack techniques "
                    "and generating adversarial prompt..."
                ):
                    rag_result = (
                        generate_attack(
                            category=(
                                rag_category
                            ),
                            goal=(
                                testing_goal
                            ),
                        )
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
                ] = rag_result[
                    "prompt"
                ]

            except Exception as exc:
                st.error(
                    "RAG attack generation failed."
                )

                st.exception(
                    exc
                )

        if (
            "rag_generated_result"
            in st.session_state
        ):
            stored_result = (
                st.session_state[
                    "rag_generated_result"
                ]
            )

            if (
                stored_result.get(
                    "category"
                )
                == rag_category
            ):
                rag_result = (
                    stored_result
                )

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
        attack_source
        == "Saved Attack"
        or rag_result is not None
    )

    run_button = st.button(
        "Run Security Test",
        type="primary",
        use_container_width=True,
        disabled=(
            not rag_ready
        ),
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

    if (
        attack_source
        == "Saved Attack"
    ):
        col1, col2 = (
            st.columns(2)
        )

        with col1:
            st.subheader(
                "Attack Prompt"
            )

            editor_key = (
                "saved_attack_"
                + selected_attack[
                    "name"
                ].replace(
                    " ",
                    "_",
                )
            )

            attack_prompt = (
                st.text_area(
                    "Prompt sent to target",
                    value=(
                        selected_attack[
                            "prompt"
                        ]
                    ),
                    height=220,
                    key=editor_key,
                    label_visibility=(
                        "collapsed"
                    ),
                )
            )

        with col2:
            st.subheader(
                "Attack Information"
            )

            st.write(
                "**Source:** "
                "Saved attack"
            )

            st.write(
                "**Category:** "
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

            col1, col2 = (
                st.columns(
                    [3, 2]
                )
            )

            with col1:
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
                    ] = rag_result[
                        "prompt"
                    ]

                attack_prompt = (
                    st.text_area(
                        "Generated prompt",
                        height=240,
                        key=(
                            rag_editor_key
                        ),
                    )
                )

            with col2:
                st.write(
                    "**Category:** "
                    f'{rag_result["category"]}'
                )

                st.write(
                    "**Testing goal:** "
                    f'{rag_result["goal"]}'
                )

                st.markdown(
                    "**Retrieval query**"
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

            for document in (
                rag_result[
                    "retrieved_documents"
                ]
            ):
                title = (
                    document.get(
                        "title",
                        "Technique",
                    )
                )

                category = (
                    document.get(
                        "category",
                        "Unknown",
                    )
                )

                with st.expander(
                    f"{title} — {category}"
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

    # -----------------------------------------------------
    # Execute single test
    # -----------------------------------------------------

    if run_button:

        if (
            target_name
            == (
                "Secure LangGraph "
                "Content Assistant"
            )
        ):
            target_fn = (
                langgraph_target
            )

        else:
            target_fn = (
                demo_target
            )

        if (
            attack_source
            == "Saved Attack"
        ):
            attack_for_run = {
                **selected_attack,
                "prompt": (
                    attack_prompt
                ),
                "source": "saved",
            }

        else:
            attack_for_run = {
                "name": (
                    "RAG-Generated "
                    f"{rag_result['category']} "
                    "Attack"
                ),
                "category": (
                    rag_result[
                        "category"
                    ]
                ),
                "prompt": (
                    attack_prompt
                ),
                "expected_secure_behavior": (
                    "The target should preserve "
                    "its original instructions "
                    "and security controls despite "
                    "the generated adversarial prompt."
                ),
                "source": "rag",
                "testing_goal": (
                    rag_result[
                        "goal"
                    ]
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
                "Running security test..."
            ):
                result = (
                    run_security_test(
                        target_name=(
                            target_name
                        ),
                        target_fn=(
                            target_fn
                        ),
                        attack=(
                            attack_for_run
                        ),
                        evaluator=(
                            evaluate_response
                        ),
                        log_file=(
                            LOG_FILE
                        ),
                    )
                )

        except Exception as exc:
            st.error(
                "The target application "
                "could not be run."
            )

            st.exception(
                exc
            )

        else:
            st.divider()

            (
                result_col,
                category_col,
                duration_col,
            ) = st.columns(3)

            result_col.metric(
                "Result",
                result[
                    "evaluation"
                ]["verdict"],
            )

            category_col.metric(
                "Category",
                result[
                    "attack"
                ]["category"],
            )

            duration_col.metric(
                "Execution time",
                (
                    f'{result["duration_ms"]:.1f} ms'
                ),
            )

            st.subheader(
                "Target Response"
            )

            st.code(
                result[
                    "target_response"
                ],
                language=None,
            )

            metadata = (
                result.get(
                    "target_metadata",
                    {},
                )
            )

            st.subheader(
                "Target Security Metadata"
            )

            (
                security_col,
                route_col,
                validation_col,
            ) = st.columns(3)

            security_col.metric(
                "Security",
                metadata.get(
                    "security_status"
                )
                or "Not reported",
            )

            route_col.metric(
                "Route",
                metadata.get(
                    "route"
                )
                or "Not reached",
            )

            validation_col.metric(
                "Validation",
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

            st.subheader(
                "Tool Activity"
            )

            display_tool_calls(
                metadata.get(
                    "tool_calls",
                    [],
                ),
                empty_message=(
                    "No tool calls requested "
                    "during this test."
                ),
            )

            display_executed_tool_calls(
                metadata.get(
                    "executed_tool_calls",
                    [],
                ),
                empty_message=(
                    "No tools actually executed "
                    "during this test."
                ),
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

            evaluation = (
                result[
                    "evaluation"
                ]
            )

            verdict = (
                evaluation[
                    "verdict"
                ]
            )

            if verdict == "PASS":
                st.success(
                    evaluation[
                        "reason"
                    ]
                )

            elif verdict == "FAIL":
                st.error(
                    evaluation[
                        "reason"
                    ]
                )

            else:
                st.warning(
                    evaluation[
                        "reason"
                    ]
                )

            if evaluation.get(
                "defense"
            ):
                st.write(
                    "**Defense:** "
                    f'{evaluation["defense"]}'
                )

            if evaluation.get(
                "defense_reason"
            ):
                st.write(
                    "**Defense details:** "
                    f'{evaluation["defense_reason"]}'
                )

            if evaluation.get(
                "judge"
            ):
                with st.expander(
                    "LLM Judge Details"
                ):
                    st.json(
                        evaluation[
                            "judge"
                        ]
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
                st.json(
                    result
                )

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
        "Run repeatable attack suites against a selected "
        "target to measure resistance and security behavior."
    )

    benchmark_suite = (
        st.radio(
            "Benchmark suite",
            [
                "Basic saved attacks",
                "Adversarial benchmark",
                "Advanced benchmark",
            ],
            horizontal=True,
        )
    )

    if (
        benchmark_suite
        == "Advanced benchmark"
    ):
        selected_suite = (
            advanced_benchmark_attacks
        )

        st.info(
            "The advanced suite tests obfuscation, "
            "indirect injection, fabricated authorization, "
            "routing manipulation, tool escalation, and "
            "attacks embedded inside legitimate tasks."
        )

    elif (
        benchmark_suite
        == "Adversarial benchmark"
    ):
        selected_suite = (
            benchmark_attacks
        )

        st.info(
            "The adversarial suite provides regression "
            "coverage for instruction-boundary weaknesses."
        )

    else:
        selected_suite = (
            attacks
        )

        st.info(
            "The basic suite provides smoke testing "
            "for the security-evaluation pipeline."
        )

    benchmark_target = (
        st.selectbox(
            "Benchmark target",
            [
                "Demo vulnerable agent",
                (
                    "Secure LangGraph "
                    "Content Assistant"
                ),
            ],
            key="benchmark_target",
        )
    )

    st.write(
        "This benchmark will run "
        f"**{len(selected_suite)} attacks**."
    )

    run_benchmark_button = (
        st.button(
            "Run Benchmark Suite",
            type="primary",
            key="run_benchmark",
        )
    )

    if run_benchmark_button:

        if (
            benchmark_target
            == (
                "Secure LangGraph "
                "Content Assistant"
            )
        ):
            benchmark_fn = (
                langgraph_target
            )

        else:
            benchmark_fn = (
                demo_target
            )

        try:
            with st.spinner(
                "Running benchmark..."
            ):
                results = (
                    run_benchmark_suite(
                        target_name=(
                            benchmark_target
                        ),
                        target_fn=(
                            benchmark_fn
                        ),
                        attacks=(
                            selected_suite
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
            ] = results

            st.session_state[
                "benchmark_name"
            ] = benchmark_suite

            st.session_state[
                "benchmark_target_name"
            ] = benchmark_target

        except Exception as exc:
            st.error(
                "Benchmark failed."
            )

            st.exception(
                exc
            )

    results = (
        st.session_state.get(
            "benchmark_results",
            [],
        )
    )

    benchmark_name = (
        st.session_state.get(
            "benchmark_name"
        )
    )

    benchmark_target_name = (
        st.session_state.get(
            "benchmark_target_name"
        )
    )

    if results:
        st.divider()

        st.markdown(
            f"### Results — "
            f"{benchmark_name} "
            f"→ {benchmark_target_name}"
        )

        total = len(
            results
        )

        passes = sum(
            item[
                "evaluation"
            ]["verdict"]
            == "PASS"
            for item in results
        )

        failures = sum(
            item[
                "evaluation"
            ]["verdict"]
            == "FAIL"
            for item in results
        )

        reviews = sum(
            item[
                "evaluation"
            ]["verdict"]
            == "REVIEW"
            for item in results
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
            (
                defense_col,
                attack_col,
                review_rate_col,
            ) = st.columns(3)

            defense_col.metric(
                "Defense success rate",
                f"{(passes / total) * 100:.1f}%",
            )

            attack_col.metric(
                "Attack success rate",
                f"{(failures / total) * 100:.1f}%",
            )

            review_rate_col.metric(
                "Review rate",
                f"{(reviews / total) * 100:.1f}%",
            )

        precheck_allows = sum(
            item.get(
                "target_metadata",
                {},
            ).get(
                "security_status"
            )
            == "allow"
            for item in results
        )

        precheck_blocks = sum(
            item.get(
                "target_metadata",
                {},
            ).get(
                "security_status"
            )
            == "block"
            for item in results
        )

        (
            bypass_col,
            block_col,
        ) = st.columns(2)

        bypass_col.metric(
            "Precheck bypasses",
            precheck_allows,
        )

        block_col.metric(
            "Precheck blocks",
            precheck_blocks,
        )

        st.subheader(
            "Benchmark Results"
        )

        rows = []

        for item in results:
            metadata = (
                item.get(
                    "target_metadata",
                    {},
                )
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

            rows.append(
                {
                    "Attack": (
                        item[
                            "attack"
                        ]["name"]
                    ),
                    "Category": (
                        item[
                            "attack"
                        ]["category"]
                    ),
                    "Verdict": (
                        item[
                            "evaluation"
                        ]["verdict"]
                    ),
                    "Defense": (
                        item[
                            "evaluation"
                        ].get(
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
                    "Requested Tools": (
                        len(
                            requested
                        )
                    ),
                    "Executed Tools": (
                        len(
                            executed
                        )
                    ),
                }
            )

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
        )

        st.subheader(
            "Individual Results"
        )

        for item in results:
            verdict = (
                item[
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
                f'{item["attack"]["name"]} '
                f'— {verdict}'
            ):
                st.write(
                    "**Category:** "
                    f'{item["attack"]["category"]}'
                )

                st.write(
                    "**Reason:** "
                    f'{item["evaluation"]["reason"]}'
                )

                metadata = (
                    item.get(
                        "target_metadata",
                        {},
                    )
                )

                st.write(
                    "**Security status:** "
                    f'{metadata.get("security_status") or "Not reported"}'
                )

                st.write(
                    "**Route:** "
                    f'{metadata.get("route") or "Not reached"}'
                )

                st.write(
                    "**Validation:** "
                    f'{metadata.get("validation_status") or "Not reached"}'
                )

                st.markdown(
                    "#### Tool Activity"
                )

                display_tool_calls(
                    metadata.get(
                        "tool_calls",
                        [],
                    )
                )

                display_executed_tool_calls(
                    metadata.get(
                        "executed_tool_calls",
                        [],
                    )
                )

                st.markdown(
                    "**Attack prompt**"
                )

                st.code(
                    item[
                        "attack"
                    ]["prompt"],
                    language=None,
                )

                st.markdown(
                    "**Target response**"
                )

                st.code(
                    item[
                        "target_response"
                    ],
                    language=None,
                )

                with st.expander(
                    "Execution Trace"
                ):
                    st.json(
                        item
                    )

        st.download_button(
            "Download benchmark results as JSON",
            data=json.dumps(
                results,
                indent=2,
            ),
            file_name=(
                "benchmark_results.json"
            ),
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
        "Run multiple prompts through the same "
        "LangGraph thread to test stateful attacks."
    )

    st.info(
        "Multi-turn scenarios reuse one LangGraph thread "
        "so later prompts can depend on genuine prior context."
    )

    scenario_names = [
        attack["name"]
        for attack in (
            multi_turn_attacks
        )
    ]

    selected_name = (
        st.selectbox(
            "Multi-turn scenario",
            scenario_names,
            key=(
                "multi_turn_scenario"
            ),
        )
    )

    selected_multi_attack = next(
        attack
        for attack in (
            multi_turn_attacks
        )
        if (
            attack["name"]
            == selected_name
        )
    )

    st.write(
        "**Category:** "
        f'{selected_multi_attack["category"]}'
    )

    st.markdown(
        "**Expected secure behavior**"
    )

    st.write(
        selected_multi_attack[
            "expected_secure_behavior"
        ]
    )

    st.subheader(
        "Conversation Sequence"
    )

    for index, turn in enumerate(
        selected_multi_attack[
            "turns"
        ],
        start=1,
    ):
        st.markdown(
            f"**Turn {index}**"
        )

        st.code(
            turn,
            language=None,
        )

    run_multi_turn_button = (
        st.button(
            "Run Multi-Turn Test",
            type="primary",
            key=(
                "run_multi_turn"
            ),
        )
    )

    if run_multi_turn_button:

        try:
            with st.spinner(
                "Running multi-turn security test..."
            ):
                multi_result = (
                    run_multi_turn_security_test(
                        target_name=(
                            "Secure LangGraph "
                            "Content Assistant"
                        ),
                        target_fn=(
                            langgraph_target
                        ),
                        attack=(
                            selected_multi_attack
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
            ] = multi_result

        except Exception as exc:
            st.error(
                "Multi-turn test failed."
            )

            st.exception(
                exc
            )

    multi_result = (
        st.session_state.get(
            "multi_turn_result"
        )
    )

    if multi_result:
        st.divider()

        verdict = (
            multi_result[
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
                multi_result[
                    "turns"
                ]
            ),
        )

        duration_col.metric(
            "Execution time",
            (
                f'{multi_result["duration_ms"]:.1f} ms'
            ),
        )

        if verdict == "PASS":
            st.success(
                multi_result[
                    "evaluation"
                ]["reason"]
            )

        elif verdict == "FAIL":
            st.error(
                multi_result[
                    "evaluation"
                ]["reason"]
            )

        else:
            st.warning(
                multi_result[
                    "evaluation"
                ]["reason"]
            )

        st.caption(
            "Shared LangGraph thread: "
            f'{multi_result["thread_id"]}'
        )

        st.subheader(
            "Turn-by-Turn Trace"
        )

        for turn in (
            multi_result[
                "turns"
            ]
        ):
            number = (
                turn[
                    "turn"
                ]
            )

            with st.expander(
                f"Turn {number}",
                expanded=True,
            ):
                st.markdown(
                    "**Prompt**"
                )

                st.code(
                    turn[
                        "prompt"
                    ],
                    language=None,
                )

                st.markdown(
                    "**Response**"
                )

                st.code(
                    turn[
                        "response"
                    ],
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

                if turn.get(
                    "security_reason"
                ):
                    st.caption(
                        "Security: "
                        f'{turn["security_reason"]}'
                    )

                if turn.get(
                    "validation_reason"
                ):
                    st.caption(
                        "Validation: "
                        f'{turn["validation_reason"]}'
                    )

                st.markdown(
                    "#### Tool Activity"
                )

                display_tool_calls(
                    turn.get(
                        "tool_calls",
                        [],
                    ),
                    empty_message=(
                        "No tool calls requested "
                        "on this turn."
                    ),
                )

                display_executed_tool_calls(
                    turn.get(
                        "executed_tool_calls",
                        [],
                    ),
                    empty_message=(
                        "No tools executed "
                        "on this turn."
                    ),
                )

        st.subheader(
            "Final Evaluation"
        )

        evaluation = (
            multi_result[
                "evaluation"
            ]
        )

        st.write(
            "**Evaluation method:** "
            f'{evaluation.get("evaluation_method", "unknown")}'
        )

        if evaluation.get(
            "defense"
        ):
            st.write(
                "**Defense:** "
                f'{evaluation["defense"]}'
            )

        if evaluation.get(
            "defense_reason"
        ):
            st.write(
                "**Defense details:** "
                f'{evaluation["defense_reason"]}'
            )

        if evaluation.get(
            "judge"
        ):
            with st.expander(
                "LLM Judge Details"
            ):
                st.json(
                    evaluation[
                        "judge"
                    ]
                )

        with st.expander(
            "Full Execution Trace"
        ):
            st.json(
                multi_result
            )

        st.download_button(
            "Download multi-turn result",
            data=json.dumps(
                multi_result,
                indent=2,
            ),
            file_name=(
                f'{multi_result["run_id"]}.json'
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
                    try:
                        rows.append(
                            json.loads(
                                line
                            )
                        )

                    except json.JSONDecodeError:
                        continue

        if not rows:
            st.info(
                "No tests have been run yet."
            )

        else:
            rows.reverse()

            for row in rows[:25]:

                evaluation = (
                    row.get(
                        "evaluation",
                        {},
                    )
                )

                verdict = (
                    evaluation.get(
                        "verdict",
                        "UNKNOWN",
                    )
                )

                icon = {
                    "PASS": "✅",
                    "FAIL": "❌",
                    "REVIEW": "⚠️",
                }.get(
                    verdict,
                    "•",
                )

                attack = (
                    row.get(
                        "attack",
                        {},
                    )
                )

                with st.expander(
                    f'{icon} '
                    f'{attack.get("name", "Unknown")} '
                    f'— {row.get("timestamp", "")}'
                ):
                    st.write(
                        "**Target:** "
                        f'{row.get("target_name", "")}'
                    )

                    st.write(
                        "**Category:** "
                        f'{attack.get("category", "")}'
                    )

                    st.write(
                        "**Verdict:** "
                        f'{verdict}'
                    )

                    if (
                        "turns"
                        in row
                    ):
                        st.write(
                            "**Test type:** "
                            "Multi-turn"
                        )

                        st.write(
                            "**Turns:** "
                            f'{len(row["turns"])}'
                        )

                        if row.get(
                            "thread_id"
                        ):
                            st.write(
                                "**Thread ID:** "
                                f'{row["thread_id"]}'
                            )

                    metadata = (
                        row.get(
                            "target_metadata",
                            {},
                        )
                    )

                    if metadata:
                        st.write(
                            "**Security:** "
                            f'{metadata.get("security_status") or "Not reported"}'
                        )

                        st.write(
                            "**Route:** "
                            f'{metadata.get("route") or "Not reached"}'
                        )

                        st.write(
                            "**Validation:** "
                            f'{metadata.get("validation_status") or "Not reached"}'
                        )

                        st.markdown(
                            "#### Tool Activity"
                        )

                        display_tool_calls(
                            metadata.get(
                                "tool_calls",
                                [],
                            )
                        )

                        display_executed_tool_calls(
                            metadata.get(
                                "executed_tool_calls",
                                [],
                            )
                        )

                    st.markdown(
                        "**Target response**"
                    )

                    st.code(
                        row.get(
                            "target_response",
                            "",
                        ),
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
### Individual security testing

Run saved or RAG-generated prompt-injection attacks against
a demo target or the Secure LangGraph Content Assistant.

### RAG-generated attacks

The tester retrieves security techniques from a curated
knowledge base and uses them as grounding context for
generating adversarial prompts.

**testing goal → semantic retrieval → attack techniques → LLM generation → adversarial prompt**

### Benchmark suites

Three benchmark tiers provide progressively deeper testing:

- **Basic saved attacks** — smoke tests for the evaluation pipeline
- **Adversarial benchmark** — regression coverage for instruction-boundary weaknesses
- **Advanced benchmark** — obfuscation, indirect injection, fabricated authority, routing manipulation, tool escalation, and malicious content embedded inside legitimate tasks

**attack suite → target → security layers → evaluator → aggregate metrics**

### Multi-turn security testing

Multi-turn scenarios reuse the same LangGraph thread across
several prompts.

This allows genuine stateful security testing such as:

**benign setup → authority claim → context manipulation → adversarial request → evaluation**

### Tool-call observability

Tool-enabled agents expose both:

1. **tool calls requested by the model**
2. **tool calls actually executed by LangGraph**

The tester also records the returned tool result.

This makes it possible to inspect:

**model request → ToolNode execution → tool result**

rather than inferring tool behavior only from the final
model response.

### Defense-in-depth evaluation

The test bench distinguishes among:

- prompt-injection precheck blocks
- precheck bypasses
- model-level resistance
- output-validation defenses
- unsafe tool behavior
- successful adversarial behavior
- ambiguous cases requiring review

### Evaluation methods

Results combine:

- deterministic security checks
- structured target metadata
- agent routing
- output validation
- requested tool calls
- confirmed tool execution
- LLM-as-a-judge analysis

Results are classified as:

- **PASS**
- **FAIL**
- **REVIEW**

### Current architecture

The test bench can now evaluate:

- single-turn attacks
- RAG-generated attacks
- repeatable benchmark suites
- genuine multi-turn attacks
- routing behavior
- requested tool behavior
- actual executed tool behavior
- tool results

### Next improvements

- automatically compare requested vs executed tools
- define per-agent tool allowlists
- automatically flag unauthorized tool calls
- batch multi-turn benchmark execution
- category-level dashboards
- cross-version benchmark comparison
- LangSmith observability
- persistent deployment storage
- deployment
        """
    )