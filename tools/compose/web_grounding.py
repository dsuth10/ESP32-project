"""
Live web grounding for Compose mode.

Pipeline (Compose only - Dictate never searches):
  1. Keyword router (0 ms): obvious "search" / "no search" requests are decided locally.
  2. Model router for ambiguous requests:
       - Jev (TypeSafe System One) via the OpenRouter Decisions API, if OPENROUTER_API_KEY is set
       - Small Groq model fallback (openai/gpt-oss-20b) if Jev is unavailable
  3. Brave Search API snippet retrieval (no page scraping) when search is needed.

Every failure degrades to "no web context" and is reported back to the caller so
the UI can show it. Searching never blocks generation from going ahead.
"""

from __future__ import annotations

import html
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime

import requests

# ── Keyword routing ─────────────────────────────────────────────────────

# Explicit user commands to search. These also get stripped from the query.
_EXPLICIT_SEARCH_PREFIX = re.compile(
    r"^\s*(?:please\s+|can you\s+|could you\s+)?"
    r"(?:search(?:\s+the\s+web|\s+online|\s+the\s+internet)?(?:\s+for)?|web\s+search(?:\s+for)?|"
    r"look\s+up|google|check\s+online(?:\s+for)?)\b[\s,:]*",
    re.IGNORECASE,
)

# Explicit user commands NOT to search.
_EXPLICIT_NO_SEARCH = re.compile(
    r"\b(?:without|no|don'?t|do not)\s+(?:a\s+)?(?:web\s+)?search(?:ing)?\b|\boffline\b",
    re.IGNORECASE,
)

# Time-sensitive phrasing that almost always needs live data.
_TIME_SENSITIVE = re.compile(
    r"\b(?:today|tonight|tomorrow|yesterday|right now|currently|latest|newest|recent(?:ly)?|"
    r"this (?:morning|week|weekend|month|year|season)|last (?:night|week|weekend|month)|"
    r"news|headlines?|weather|forecast|scores?|who won|standings|ladder|"
    r"stock price|share price|price of|exchange rate|release date|announced|"
    r"just (?:came out|launched|happened)|update on|what'?s new|live (?:scores?|results|updates?))\b",
    re.IGNORECASE,
)

# Pure writing / transformation requests that never need live data.
_TRANSFORM_ONLY = re.compile(
    r"^\s*(?:please\s+)?(?:re-?write|rephrase|reword|paraphrase|proofread|fix (?:the )?(?:grammar|spelling)|"
    r"shorten|lengthen|expand|condense|summari[sz]e (?:this|the selected|the above)|translate|"
    r"make (?:this|it)|turn (?:this|it) into|format|reformat|convert (?:this|it))\b",
    re.IGNORECASE,
)

_FRESHNESS_DAY = re.compile(
    r"\b(?:today|tonight|right now|this morning|yesterday|last night|live|scores?|weather|forecast)\b",
    re.IGNORECASE,
)
_FRESHNESS_WEEK = re.compile(r"\b(?:this week|last week|this weekend|last weekend|news|headlines?|latest)\b", re.IGNORECASE)
_FRESHNESS_MONTH = re.compile(r"\b(?:this month|last month|recent(?:ly)?)\b", re.IGNORECASE)
_FRESHNESS_YEAR = re.compile(r"\b(?:this year|this season)\b", re.IGNORECASE)

# Brave freshness codes
FRESHNESS_CODES = {"day": "pd", "week": "pw", "month": "pm", "year": "py", "any": None}


def keyword_route(request: str, selected_text: str = "") -> bool | None:
    """Returns True (search), False (no search) or None (ambiguous, ask a model)."""
    text = request.strip()
    if not text:
        return False
    if _EXPLICIT_NO_SEARCH.search(text):
        return False
    if _EXPLICIT_SEARCH_PREFIX.match(text):
        return True
    if _TRANSFORM_ONLY.match(text):
        return False
    if _TIME_SENSITIVE.search(text):
        return True
    # A pure edit of highlighted text with no time-sensitive words: don't search.
    if selected_text.strip() and re.search(r"\b(?:this|the selected|the above|it)\b", text, re.IGNORECASE):
        return False
    return None


def keyword_freshness(request: str) -> str | None:
    """Returns a Brave freshness code (pd/pw/pm/py) inferred from wording, or None."""
    if _FRESHNESS_DAY.search(request):
        return "pd"
    if _FRESHNESS_WEEK.search(request):
        return "pw"
    if _FRESHNESS_MONTH.search(request):
        return "pm"
    if _FRESHNESS_YEAR.search(request):
        return "py"
    return None


def build_search_query(request: str, max_chars: int = 380) -> str:
    """Strips spoken command prefixes so Brave receives the actual topic."""
    query = _EXPLICIT_SEARCH_PREFIX.sub("", request.strip(), count=1)
    query = query.strip(" .?!,")
    if not query:
        query = request.strip()
    return query[:max_chars]


# ── Model routing ───────────────────────────────────────────────────────

@dataclass
class RouteDecision:
    needs_search: bool
    source: str  # keywords | jev | groq | default | always | disabled
    freshness: str | None = None
    confidence: float | None = None
    latency: float = 0.0
    errors: list[str] = field(default_factory=list)


_ROUTER_INSTRUCTIONS = (
    "The user dictated a request to a desktop writing assistant whose language model has a "
    "training cut-off and no internet access. Would a correct, useful answer require live or "
    "recent information from the web (news, current events, prices, scores, weather, recent "
    "releases, people's current roles, anything that may have changed in the last year)?"
)

_GROQ_ROUTER_SYSTEM = (
    _ROUTER_INSTRUCTIONS
    + " Pure writing, rewriting, grammar, brainstorming, timeless facts and coding do NOT need search."
    " Reply with exactly one word: SEARCH or NONE."
)


class IntentRouter:
    """Keyword-first router with Jev (OpenRouter) and Groq model fallbacks."""

    def __init__(
        self,
        mode: str = "auto",
        openrouter_api_key: str | None = None,
        openrouter_base_url: str = "https://openrouter.ai",
        jev_model: str = "~typesafe/jev-latest",
        groq_api_key: str | None = None,
        groq_base_url: str = "https://api.groq.com/openai/v1",
        groq_model: str = "openai/gpt-oss-20b",
        timeout: float = 2.0,
        threshold: float = 0.5,
        session: requests.Session | None = None,
    ):
        self.mode = (mode or "auto").strip().lower()
        self.openrouter_api_key = (openrouter_api_key or "").strip() or None
        self.openrouter_base_url = openrouter_base_url.rstrip("/")
        self.jev_model = jev_model
        self.groq_api_key = (groq_api_key or "").strip() or None
        self.groq_base_url = groq_base_url.rstrip("/")
        self.groq_model = groq_model
        self.timeout = timeout
        self.threshold = threshold
        self.session = session or requests.Session()

    def _ask_jev(self, request: str, selected_text: str) -> tuple[bool, str | None, float]:
        """Calls the OpenRouter Decisions API. Returns (needs_search, freshness_code, confidence)."""
        state: dict = {"request": request}
        if selected_text.strip():
            state["selected_text_excerpt"] = selected_text.strip()[:500]
        payload = {
            "model": self.jev_model,
            "state": state,
            "questions": {
                "needs_web": {
                    "type": "noul",
                    "instructions": _ROUTER_INSTRUCTIONS,
                    "criteria": {
                        "true": "The answer depends on current or recent facts that could have changed recently.",
                        "false": "Writing, rewriting, grammar, brainstorming, coding, or timeless general knowledge.",
                    },
                },
                "recency": {
                    "type": "choice",
                    "instructions": "If web results were used, how recent must they be?",
                    "criteria": {
                        "day": "Live or same-day information: scores, weather, breaking news, prices right now.",
                        "week": "This week's news or events.",
                        "month": "Developments within the last month or so.",
                        "any": "Any time; recency is not critical.",
                    },
                },
            },
            "session_id": "esp32-compose-router",
        }
        resp = self.session.post(
            f"{self.openrouter_base_url}/api/alpha/decisions",
            headers={
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json",
                "X-Title": "ESP32 Voice Compose",
            },
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        answers = resp.json()["answers"]
        p_true = float(answers["needs_web"]["noul"])
        recency = answers.get("recency", {}).get("choice", "any")
        return p_true >= self.threshold, FRESHNESS_CODES.get(recency), p_true

    def _ask_groq(self, request: str, selected_text: str) -> bool:
        user = request
        if selected_text.strip():
            user = f"Selected text (excerpt): {selected_text.strip()[:300]}\nRequest: {request}"
        resp = self.session.post(
            f"{self.groq_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.groq_api_key}", "Content-Type": "application/json"},
            json={
                "model": self.groq_model,
                "messages": [
                    {"role": "system", "content": _GROQ_ROUTER_SYSTEM},
                    {"role": "user", "content": user},
                ],
                "temperature": 0,
                "max_tokens": 200,
                "reasoning_effort": "low",
                "include_reasoning": False,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        content = (resp.json()["choices"][0]["message"].get("content") or "").strip().upper()
        if "SEARCH" in content:
            return True
        if "NONE" in content:
            return False
        raise ValueError(f"Unexpected router reply: {content!r}")

    def classify(self, request: str, selected_text: str = "") -> RouteDecision:
        t0 = time.time()

        if self.mode == "off":
            return RouteDecision(False, "disabled")
        if self.mode == "always":
            return RouteDecision(True, "always", keyword_freshness(request))

        kw = keyword_route(request, selected_text)
        if kw is not None or self.mode == "keywords":
            return RouteDecision(bool(kw), "keywords", keyword_freshness(request) if kw else None,
                                 latency=time.time() - t0)

        errors: list[str] = []
        if self.mode in ("auto", "jev") and self.openrouter_api_key:
            try:
                needs, freshness, conf = self._ask_jev(request, selected_text)
                return RouteDecision(needs, "jev", freshness or keyword_freshness(request), conf,
                                     latency=time.time() - t0)
            except Exception as e:
                errors.append(f"jev: {e}")
                logging.warning("[Router] Jev decision failed (%s); trying Groq router", e)

        if self.mode in ("auto", "jev", "groq") and self.groq_api_key:
            try:
                needs = self._ask_groq(request, selected_text)
                return RouteDecision(needs, "groq", keyword_freshness(request) if needs else None,
                                     latency=time.time() - t0, errors=errors)
            except Exception as e:
                errors.append(f"groq: {e}")
                logging.warning("[Router] Groq router failed (%s); defaulting to no search", e)

        return RouteDecision(False, "default", latency=time.time() - t0, errors=errors)


# ── Brave Search ────────────────────────────────────────────────────────

_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub("", text or ""))).strip()


class BraveSearchClient:
    URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(
        self,
        api_key: str | None,
        country: str = "AU",
        count: int = 5,
        timeout: float = 3.0,
        extra_snippets: bool = True,
        session: requests.Session | None = None,
    ):
        self.api_key = (api_key or "").strip() or None
        self.country = country
        self.count = count
        self.timeout = timeout
        self.extra_snippets = extra_snippets
        self.session = session or requests.Session()

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, freshness: str | None = None) -> list[dict]:
        params = {
            "q": query,
            "count": self.count,
            "country": self.country,
            "search_lang": "en",
            "safesearch": "moderate",
            "text_decorations": "false",
        }
        if self.extra_snippets:
            params["extra_snippets"] = "true"
        if freshness:
            params["freshness"] = freshness

        resp = self.session.get(
            self.URL,
            params=params,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": self.api_key,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in (data.get("web") or {}).get("results", [])[: self.count]:
            results.append({
                "title": _clean(item.get("title", "")),
                "url": item.get("url", ""),
                "source": (item.get("profile") or {}).get("name") or (item.get("meta_url") or {}).get("hostname", ""),
                "age": item.get("age") or item.get("page_age") or "",
                "snippet": _clean(item.get("description", "")),
                "extra": [_clean(s) for s in (item.get("extra_snippets") or [])[:2]],
            })
        return results


def format_search_context(query: str, results: list[dict], max_chars: int = 3000) -> str:
    """Formats snippets into a compact block for the LLM prompt."""
    lines = [f'Live web search results for "{query}" (retrieved {datetime.now().strftime("%d %B %Y")}):']
    for i, r in enumerate(results, 1):
        meta = ", ".join(x for x in (r.get("source"), r.get("age")) if x)
        lines.append(f"[{i}] {r['title']}" + (f" ({meta})" if meta else ""))
        body = " ".join([r["snippet"], *r.get("extra", [])]).strip()
        if body:
            lines.append(f"    {body}")
    text = "\n".join(lines)
    return text[:max_chars]


# ── Facade ──────────────────────────────────────────────────────────────

@dataclass
class GroundingResult:
    context: str = ""
    route: RouteDecision | None = None
    query: str = ""
    num_results: int = 0
    search_latency: float = 0.0
    error: str | None = None

    @property
    def used(self) -> bool:
        return bool(self.context)

    def summary(self) -> str:
        """One-line, human readable description for logs / the GUI event log."""
        if self.route is None:
            return f"Web: off ({self.error})" if self.error else "Web: off"
        r = self.route
        route_txt = f"router={r.source}"
        if r.confidence is not None:
            route_txt += f" p={r.confidence:.2f}"
        route_txt += f" {r.latency * 1000:.0f}ms"
        if self.error:
            return f"Web: [No web] {self.error} ({route_txt})"
        if not r.needs_search:
            return f"Web: not needed ({route_txt})"
        fresh = f", freshness={r.freshness}" if r.freshness else ""
        return (f"Web: {self.num_results} Brave results in {self.search_latency * 1000:.0f}ms"
                f"{fresh} for \"{self.query}\" ({route_txt})")


class WebGrounding:
    def __init__(self, router: IntentRouter, search: BraveSearchClient, enabled: bool = True):
        self.router = router
        self.search = search
        self.enabled = enabled

    @classmethod
    def from_config(cls, config: dict) -> "WebGrounding":
        session = requests.Session()  # shared keep-alive pool: saves a TLS handshake per call
        router = IntentRouter(
            mode=config.get("INTENT_ROUTER", "auto"),
            openrouter_api_key=config.get("OPENROUTER_API_KEY"),
            openrouter_base_url=config.get("OPENROUTER_BASE_URL", "https://openrouter.ai"),
            jev_model=config.get("JEV_MODEL", "~typesafe/jev-latest"),
            groq_api_key=config.get("GROQ_API_KEY"),
            groq_base_url=config.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            groq_model=config.get("ROUTER_GROQ_MODEL", "openai/gpt-oss-20b"),
            timeout=float(config.get("ROUTER_TIMEOUT", "2.0")),
            session=session,
        )
        search = BraveSearchClient(
            api_key=config.get("BRAVE_API_KEY"),
            country=config.get("BRAVE_COUNTRY", "AU"),
            count=int(config.get("BRAVE_RESULT_COUNT", "5")),
            timeout=float(config.get("BRAVE_TIMEOUT", "3.0")),
            extra_snippets=config.get("BRAVE_EXTRA_SNIPPETS", "1").lower() in ("1", "true", "yes"),
            session=session,
        )
        enabled = config.get("WEB_SEARCH_ENABLED", "1").lower() in ("1", "true", "yes")
        return cls(router, search, enabled)

    def describe(self) -> str:
        if not self.enabled:
            return "Web search: disabled (WEB_SEARCH_ENABLED=0)"
        if not self.search.available:
            return "Web search: off (BRAVE_API_KEY not set)"
        router = self.router.mode
        if router == "auto":
            parts = ["keywords"]
            if self.router.openrouter_api_key:
                parts.append("Jev")
            if self.router.groq_api_key:
                parts.append("Groq")
            router = " > ".join(parts)
        return f"Web search: Brave ({self.search.country}), router: {router}"

    def fetch_context(self, request: str, selected_text: str = "", local_only: bool = False,
                      on_status=None) -> GroundingResult:
        """Never raises. Returns an empty context when search is not needed or fails."""
        if not self.enabled:
            return GroundingResult()
        if local_only:
            return GroundingResult(error="local-only mode")
        if not self.search.available:
            return GroundingResult(error="BRAVE_API_KEY not set")

        route = self.router.classify(request, selected_text)
        result = GroundingResult(route=route)
        if not route.needs_search:
            return result

        result.query = build_search_query(request)
        if on_status:
            on_status("Searching the web...")
        t0 = time.time()
        try:
            hits = self.search.search(result.query, route.freshness)
            if not hits and route.freshness:
                # Over-strict freshness can return nothing; retry unrestricted once.
                hits = self.search.search(result.query, None)
        except Exception as e:
            result.search_latency = time.time() - t0
            result.error = f"Brave search failed: {e}"
            logging.warning("[Web] %s", result.error)
            return result
        result.search_latency = time.time() - t0
        result.num_results = len(hits)
        if hits:
            result.context = format_search_context(result.query, hits)
        else:
            result.error = "Brave returned no results"
        return result
