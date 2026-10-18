"""Unit tests for web_grounding (keyword router, Jev/Groq model router, Brave client, prompt engine integration)."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from web_grounding import (
    keyword_route,
    keyword_freshness,
    build_search_query,
    format_search_context,
    IntentRouter,
    BraveSearchClient,
    WebGrounding,
    RouteDecision,
)
from prompt_engine import build_compose_messages


def test_keyword_route_explicit_search():
    assert keyword_route("search the web for AFL grand final winner") is True
    assert keyword_route("Google the exchange rate of AUD to USD") is True
    assert keyword_route("Look up what happened in Sydney today") is True


def test_keyword_route_explicit_no_search():
    assert keyword_route("Don't search online, just brainstorm 3 ideas") is False
    assert keyword_route("Without searching the web, summarize this") is False


def test_keyword_route_transform_only():
    assert keyword_route("Rewrite this email to be more polite") is False
    assert keyword_route("Proofread this paragraph and fix spelling") is False
    assert keyword_route("Make this shorter") is False


def test_keyword_route_time_sensitive():
    assert keyword_route("Who won the game last night?") is True
    assert keyword_route("What is the weather forecast for Melbourne tomorrow?") is True
    assert keyword_route("What is the latest release date for Python 3.14?") is True


def test_keyword_route_ambiguous():
    # Timeless general questions defer to model router
    assert keyword_route("Explain the difference between TCP and UDP") is None
    assert keyword_route("Write a Python script to sort a list of dictionaries") is None


def test_keyword_freshness():
    assert keyword_freshness("What is the weather today?") == "pd"
    assert keyword_freshness("Latest news this week") == "pw"
    assert keyword_freshness("Explain photosynthesis") is None


def test_build_search_query_strips_command_prefix():
    assert build_search_query("Please search the web for AFL scores today") == "AFL scores today"
    assert build_search_query("Google python 3.13 release notes") == "python 3.13 release notes"


def test_format_search_context():
    results = [
        {
            "title": "AFL 2026 Grand Final",
            "url": "https://afl.com.au/news",
            "source": "AFL.com.au",
            "age": "2 hours ago",
            "snippet": "Brisbane Lions defeated Sydney Swans in thrilling contest.",
            "extra": ["Final score 120 to 95."],
        }
    ]
    formatted = format_search_context("AFL grand final", results)
    assert "AFL 2026 Grand Final" in formatted
    assert "Brisbane Lions" in formatted
    assert "Final score 120" in formatted


def test_intent_router_jev_success():
    router = IntentRouter(
        mode="auto",
        openrouter_api_key="sk-or-v1-fake",
        jev_model="~typesafe/jev-latest",
    )
    mock_resp = Mock()
    mock_resp.json.return_value = {
        "answers": {
            "needs_web": {"noul": 0.94, "type": "noul"},
            "recency": {"choice": "day", "confidence": 0.88, "type": "choice"},
        }
    }
    mock_resp.raise_for_status = Mock()

    with patch.object(router.session, "post", return_value=mock_resp) as post:
        decision = router.classify("Who is the prime minister of the UK right now?")
        assert decision.needs_search is True
        assert decision.source == "keywords" or decision.source == "jev"


def test_intent_router_jev_ambiguous_triggers_api():
    router = IntentRouter(
        mode="auto",
        openrouter_api_key="sk-or-v1-fake",
        jev_model="~typesafe/jev-latest",
    )
    mock_resp = Mock()
    mock_resp.json.return_value = {
        "answers": {
            "needs_web": {"noul": 0.88, "type": "noul"},
            "recency": {"choice": "week", "confidence": 0.80, "type": "choice"},
        }
    }
    mock_resp.raise_for_status = Mock()

    with patch.object(router.session, "post", return_value=mock_resp) as post:
        # Ambiguous query that returns None from keyword_route
        decision = router.classify("Tell me about the new CEO of Boeing")
        assert decision.source == "jev"
        assert decision.needs_search is True
        assert decision.freshness == "pw"
        assert decision.confidence == 0.88


def test_intent_router_jev_failure_falls_back_to_groq():
    router = IntentRouter(
        mode="auto",
        openrouter_api_key="sk-or-v1-fake",
        groq_api_key="gsk-fake",
    )
    # Jev fails with network timeout
    with patch.object(router, "_ask_jev", side_effect=TimeoutError("Network timeout")), \
         patch.object(router, "_ask_groq", return_value=True):
        decision = router.classify("Tell me about the new CEO of Boeing")
        assert decision.source == "groq"
        assert decision.needs_search is True
        assert len(decision.errors) == 1


def test_intent_router_total_failure_degrades_gracefully():
    router = IntentRouter(
        mode="auto",
        openrouter_api_key="sk-or-v1-fake",
        groq_api_key="gsk-fake",
    )
    with patch.object(router, "_ask_jev", side_effect=TimeoutError("Jev timeout")), \
         patch.object(router, "_ask_groq", side_effect=RuntimeError("Groq failed")):
        decision = router.classify("Tell me about the new CEO of Boeing")
        assert decision.source == "default"
        assert decision.needs_search is False
        assert len(decision.errors) == 2


def test_brave_search_client_parses_results():
    client = BraveSearchClient(api_key="fake-brave-key", country="AU")
    mock_resp = Mock()
    mock_resp.json.return_value = {
        "web": {
            "results": [
                {
                    "title": "Australian News <b>Live</b>",
                    "url": "https://abc.net.au",
                    "description": "Top stories &amp; breaking news.",
                    "profile": {"name": "ABC News"},
                    "age": "1 hour ago",
                    "extra_snippets": ["Key updates inside."],
                }
            ]
        }
    }
    mock_resp.raise_for_status = Mock()

    with patch.object(client.session, "get", return_value=mock_resp):
        results = client.search("news today")
        assert len(results) == 1
        assert results[0]["title"] == "Australian News Live"
        assert results[0]["source"] == "ABC News"
        assert "Top stories & breaking news." in results[0]["snippet"]


def test_web_grounding_disabled_or_local_only():
    grounding = WebGrounding.from_config({"WEB_SEARCH_ENABLED": "0"})
    res = grounding.fetch_context("AFL scores today")
    assert res.used is False

    grounding_live = WebGrounding.from_config({"WEB_SEARCH_ENABLED": "1", "BRAVE_API_KEY": "fake"})
    res_local = grounding_live.fetch_context("AFL scores today", local_only=True)
    assert res_local.used is False
    assert res_local.error == "local-only mode"


def test_prompt_engine_build_compose_messages_with_web_context():
    # Without web context
    msg1 = build_compose_messages("Write a note")
    assert "LIVE WEB CONTEXT" not in msg1[0]["content"]

    # With web context
    msg2 = build_compose_messages("Write a note", web_context="[1] AFL score: 100 to 90")
    assert "LIVE WEB CONTEXT" in msg2[0]["content"]
    assert "[1] AFL score: 100 to 90" in msg2[1]["content"]
