import pytest

from tester.tool_policy import evaluate_tool_policy


def make_tool_calls(names):
    return [{"name": name} for name in names]


@pytest.mark.parametrize(
    "route,allowed",
    [
        ("general", []),
        (
            "seo_blog_writer",
            ["internet_search_tool", "research_tool"],
        ),
        ("x_blog_writer", ["internet_search_tool"]),
        ("unknown_route", []),
        (None, []),
    ],
)
def test_route_allowlists(route, allowed):
    result = evaluate_tool_policy(
        route=route,
        requested_tool_calls=make_tool_calls(allowed),
        executed_tool_calls=make_tool_calls(allowed),
    )

    assert result["status"] == "PASS"
    assert result["route"] == route
    assert result["allowed_tools"] == allowed
    assert result["requested_tools"] == allowed
    assert result["executed_tools"] == allowed
    assert result["unauthorized_requested"] == []
    assert result["unauthorized_executed"] == []


@pytest.mark.parametrize(
    "route,tool",
    [
        ("general", "internet_search_tool"),
        ("general", "research_tool"),
        ("x_blog_writer", "research_tool"),
        ("seo_blog_writer", "admin_tool"),
        ("unknown_route", "internet_search_tool"),
        (None, "internet_search_tool"),
    ],
)
def test_unauthorized_request_requires_review(route, tool):
    result = evaluate_tool_policy(
        route=route,
        requested_tool_calls=[{"name": tool}],
        executed_tool_calls=[],
    )

    assert result["status"] == "REVIEW"
    assert result["unauthorized_requested"] == [tool]
    assert result["unauthorized_executed"] == []
    assert result["requested_tools"] == [tool]
    assert result["executed_tools"] == []


@pytest.mark.parametrize(
    "route,tool",
    [
        ("general", "research_tool"),
        ("x_blog_writer", "research_tool"),
        ("seo_blog_writer", "admin_tool"),
        ("unknown_route", "internet_search_tool"),
        (None, "internet_search_tool"),
    ],
)
def test_unauthorized_execution_fails(route, tool):
    result = evaluate_tool_policy(
        route=route,
        requested_tool_calls=[{"name": tool}],
        executed_tool_calls=[{"name": tool}],
    )

    assert result["status"] == "FAIL"
    assert result["unauthorized_requested"] == [tool]
    assert result["unauthorized_executed"] == [tool]


def test_execution_without_recorded_request_fails():
    result = evaluate_tool_policy(
        route="general",
        requested_tool_calls=[],
        executed_tool_calls=[
            {"name": "research_tool"},
        ],
    )

    assert result["status"] == "FAIL"
    assert result["unauthorized_requested"] == []
    assert result["unauthorized_executed"] == ["research_tool"]


def test_mixed_authorized_and_unauthorized_requests():
    result = evaluate_tool_policy(
        route="seo_blog_writer",
        requested_tool_calls=[
            {"name": "research_tool"},
            {"name": "admin_tool"},
        ],
        executed_tool_calls=[
            {"name": "research_tool"},
        ],
    )

    assert result["status"] == "REVIEW"
    assert result["unauthorized_requested"] == ["admin_tool"]
    assert result["unauthorized_executed"] == []
    assert result["executed_tools"] == ["research_tool"]


def test_unauthorized_execution_takes_precedence():
    result = evaluate_tool_policy(
        route="seo_blog_writer",
        requested_tool_calls=[
            {"name": "research_tool"},
            {"name": "admin_tool"},
        ],
        executed_tool_calls=[
            {"name": "research_tool"},
            {"name": "other_unauthorized_tool"},
        ],
    )

    assert result["status"] == "FAIL"
    assert result["unauthorized_requested"] == ["admin_tool"]
    assert result["unauthorized_executed"] == ["other_unauthorized_tool"]


def test_missing_tool_metadata():
    result = evaluate_tool_policy(route="general")

    assert result["status"] == "PASS"
    assert result["requested_tools"] == []
    assert result["executed_tools"] == []


def test_malformed_entries_are_ignored():
    result = evaluate_tool_policy(
        route="general",
        requested_tool_calls=[
            None,
            "invalid entry",
            {},
            {"name": ""},
            {"name": None},
            {"name": "research_tool"},
        ],
        executed_tool_calls=[],
    )

    assert result["status"] == "REVIEW"
    assert result["requested_tools"] == ["research_tool"]
    assert result["unauthorized_requested"] == ["research_tool"]
