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
    page_title=(
        "Agent Security Test Bench"
    ),
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
# Shared tool-call display
# ---------------------------------------------------------

def display_tool_calls(
    tool_calls,
    *,
    empty_message=(
        "No tool calls requested."
    ),
):
    """
    Display model-requested tool calls.
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
        name = (
            tool_call.get(
                "name",
                "unknown_tool",
            )
            if isinstance(
                tool_call,
                dict,
            )
            else "unknown_tool"
        )

        with st.expander(
            f"{index}. {name}"
        ):
            st.json(
                tool_call
            )


# ---------------------------------------------------------
# Sidebar
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
                    "Test whether the "
                    "application can be "
                    "coaxed into violating "
                    "its original instruction "
                    "hierarchy."
                ),
                height=130,
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
                    "Generating "
                    "adversarial prompt..."
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
                    "RAG attack "
                    "generation failed."
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

        else:
            st.info(
                "Generate an attack "
                "before running a "
                "RAG-based security test."
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
# Tabs
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
# Run Test
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
                    "Prompt",
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

    elif rag_result:
        st.subheader(
            "RAG-Generated Attack"
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
            ] = rag_result[
                "prompt"
            ]

        attack_prompt = (
            st.text_area(
                "Generated prompt",
                height=240,
                key=rag_editor_key,
            )
        )

        st.write(
            "**Category:** "
            f'{rag_result["category"]}'
        )

        st.write(
            "**Testing goal:** "
            f'{rag_result["goal"]}'
        )

        st.markdown(
            "**Retrieved techniques**"
        )

        for document in (
            rag_result[
                "retrieved_documents"
            ]
        ):
            with st.expander(
                document.get(
                    "title",
                    "Technique",
                )
            ):
                st.write(
                    document.get(
                        "content",
                        "",
                    )
                )

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
                    "The target should "
                    "preserve its original "
                    "instructions and "
                    "security controls."
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
                "The target could "
                "not be run."
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

            metadata = result.get(
                "target_metadata",
                {},
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

            display_tool_calls(
                metadata.get(
                    "tool_calls",
                    [],
                ),
                empty_message=(
                    "No tool calls "
                    "requested during "
                    "this test."
                ),
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

            with st.expander(
                "Execution Trace"
            ):
                st.json(
                    result
                )


# ---------------------------------------------------------
# Benchmark
# ---------------------------------------------------------

with tab_benchmark:

    st.subheader(
        "Security Benchmark"
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
        selected_suite = (
            advanced_benchmark_attacks
        )

    elif (
        benchmark_suite
        == "Adversarial benchmark"
    ):
        selected_suite = (
            benchmark_attacks
        )

    else:
        selected_suite = (
            attacks
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
            key=(
                "benchmark_target"
            ),
        )
    )

    st.write(
        "This benchmark will run "
        f"**{len(selected_suite)} attacks**."
    )

    if st.button(
        "Run Benchmark Suite",
        type="primary",
        key=(
            "run_benchmark"
        ),
    ):
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

    if results:
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

        reviews = (
            total
            - passes
            - failures
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

        rows = []

        for item in results:
            metadata = item.get(
                "target_metadata",
                {},
            )

            tool_calls = (
                metadata.get(
                    "tool_calls",
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
                    "Tool Calls": (
                        len(
                            tool_calls
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
                    "**Route:** "
                    f'{metadata.get("route") or "Not reached"}'
                )

                display_tool_calls(
                    metadata.get(
                        "tool_calls",
                        [],
                    )
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


# ---------------------------------------------------------
# Multi-Turn
# ---------------------------------------------------------

with tab_multi_turn:

    st.subheader(
        "Multi-Turn Security Testing"
    )

    st.caption(
        "Run multiple prompts through one shared "
        "LangGraph thread to test stateful attacks."
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

    if st.button(
        "Run Multi-Turn Test",
        type="primary",
        key=(
            "run_multi_turn"
        ),
    ):
        try:
            with st.spinner(
                "Running multi-turn "
                "security test..."
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

                display_tool_calls(
                    turn.get(
                        "tool_calls",
                        [],
                    ),
                    empty_message=(
                        "No tool calls "
                        "requested on this turn."
                    ),
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
# Test History
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
                        json.loads(
                            line
                        )
                    )

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

            attack = row.get(
                "attack",
                {},
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

                metadata = (
                    row.get(
                        "target_metadata",
                        {},
                    )
                )

                display_tool_calls(
                    metadata.get(
                        "tool_calls",
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
# About
# ---------------------------------------------------------

with tab_about:

    st.subheader(
        "What this application demonstrates"
    )

    st.markdown(
        """
        ### Individual security testing

        Run saved or RAG-generated prompt-injection attacks
        against a demo target or the Secure LangGraph Content
        Assistant.

        ### Benchmarking

        Three benchmark tiers provide smoke testing,
        adversarial regression coverage, and advanced
        security testing.

        ### Multi-turn testing

        Multi-turn scenarios reuse the same LangGraph thread,
        allowing security behavior to be tested across genuine
        conversation history.

        ### Tool-call observability

        Tool-enabled agents expose the tool calls requested by
        the model, including tool name and arguments.

        This allows the test harness to distinguish between:

        - no tool request
        - expected tool request
        - suspicious tool request
        - potential authorization-boundary violations

        Current tool instrumentation records model-requested
        tool calls. Explicit confirmation that a ToolNode
        executed the request is a planned next step.

        ### Evaluation

        Results use:

        - deterministic security signals
        - structured target metadata
        - model routing
        - output validation
        - requested tool calls
        - LLM-as-a-judge evaluation

        Results are classified as PASS, FAIL, or REVIEW.

        ### Next improvements

        - instrument actual ToolNode execution
        - compare requested vs executed tools
        - automatically detect unauthorized tool calls
        - batch multi-turn benchmark execution
        - category-level dashboards
        - persistent deployment storage
        - LangSmith observability
        - deployment
        """
    )