import json
import os
import re
from pathlib import Path

from google import genai
from google.genai import types


DEFAULT_MODEL = "gemini-3.8-flash"

# Google retires model names for new API keys ("no longer available to new
# users", HTTP 404) and temporarily sheds load (HTTP 503, "high demand"). Both
# look like "the briefing is broken" from here, and pinning one hardcoded name
# is exactly what broke before, so the call walks this list - strongest first -
# until a model answers.
FALLBACK_MODELS = (
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
)

# Statuses another model can plausibly fix. A 400/401/403 is about the key or
# the request itself, so it is reported immediately rather than retried against
# every model in the list.
RETRYABLE_STATUS = frozenset({404, 429, 500, 502, 503, 504})

# The SDK retries a 503 up to five times, which turned a fast failure into a
# 21-second wait before we could try anything else. We run our own fallback, so
# one attempt per model and a bounded timeout keeps each miss cheap: a model
# that cannot answer a race overview in half a minute is not going to answer
# it, and holding the page for a full minute per miss is what made a three-plan
# overview feel broken.
REQUEST_TIMEOUT_MS = 30_000

# Remembered for the life of the process: only the first briefing pays the cost
# of discovering which model is serving right now.
_last_good_model = None

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILES = (
    PROJECT_ROOT / ".env",
    Path(__file__).resolve().parent / ".env",
)
KEY_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")

# A placeholder is shipped in .env so there is an obvious place to paste a
# real key. It is treated as "not configured" rather than being sent to
# Google, which would fail with a confusing 400 instead of telling you to
# replace it.
PLACEHOLDER_KEYS = {
    "your-key-here",
    "your-key",
    "your_api_key_here",
    "replace-me",
}

ENV_FILE_PATH = PROJECT_ROOT / ".env"

SETUP_HELP = (
    "Gemini needs an API key and none was found. Put GEMINI_API_KEY=your-key "
    f"in {ENV_FILE_PATH} (a placeholder is already there), in "
    ".streamlit/secrets.toml, or in your shell environment, then reload the "
    "app. Create a key at https://aistudio.google.com/apikey"
)


class BriefingSetupError(RuntimeError):
    """The briefing cannot run until the app is configured."""


def _read_env_file(path):
    """Read KEY=value lines, so no extra dependency is needed."""
    values = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return values

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        values[key] = value.strip().strip('"').strip("'")
    return values


def _streamlit_secret(name):
    try:
        import streamlit as st
    except ImportError:
        return None

    try:
        value = st.secrets[name]
    except Exception:
        # No secrets file, no such key, or outside a Streamlit runtime.
        return None
    return value or None


def _is_placeholder(value):
    return value.strip().strip('"').strip("'").lower() in PLACEHOLDER_KEYS


def _key_sources():
    """Candidate keys in precedence order, each labelled with its origin.

    Every source is collected rather than only the winner, because a stale
    exported key is a real and confusing failure: the app would otherwise keep
    using a rejected environment variable while a perfectly good key sat in
    .env, and nothing would say why.
    """
    sources = []

    def add(value, label):
        text = str(value or "").strip()
        if text and not _is_placeholder(text):
            sources.append((text, label))

    for name in KEY_NAMES:
        add(os.getenv(name), f"the {name} environment variable")

    for name in KEY_NAMES:
        add(_streamlit_secret(name), f"{name} in .streamlit/secrets.toml")

    placeholder_path = None
    for path in ENV_FILES:
        values = _read_env_file(path)
        for name in KEY_NAMES:
            value = values.get(name)
            if not value:
                continue
            if _is_placeholder(value):
                placeholder_path = path
                continue
            add(value, f"{name} in {path}")

    # The same key can be configured in several places; keep the first label.
    seen = set()
    unique = []
    for value, label in sources:
        if value not in seen:
            seen.add(value)
            unique.append((value, label))
    return unique, placeholder_path


def _configuration_error(placeholder_path):
    if placeholder_path is not None:
        return BriefingSetupError(
            "Still holding the placeholder key. Open "
            f"{placeholder_path} and replace it with your real Gemini API key, "
            "then reload the app. Create a key at "
            "https://aistudio.google.com/apikey"
        )
    return BriefingSetupError(SETUP_HELP)


def resolve_api_key():
    """The key that wins, in precedence order: environment, secrets, then .env.

    A real environment variable always beats a checked-in file.
    """
    sources, placeholder_path = _key_sources()
    if not sources:
        raise _configuration_error(placeholder_path)
    return sources[0][0]


def _classify(exc):
    """Decide whether another key or another model could plausibly fix this."""
    code = getattr(exc, "code", None)
    text = str(exc).lower()
    if not isinstance(code, int):
        # A slow model surfaces as a transport timeout with no HTTP status.
        # That is the same problem as a 504 - try the next model - so it must
        # not be treated as a fatal request error.
        name = type(exc).__name__.lower()
        if (
            isinstance(exc, (TimeoutError, ConnectionError))
            or "timeout" in name
            or "connect" in name
            or "timed out" in text
            or "deadline exceeded" in text
        ):
            return "model"
        return "fatal"
    if code in (401, 403) or (code == 400 and ("api key" in text or "api_key" in text)):
        return "auth"
    if code in RETRYABLE_STATUS:
        return "model"
    return "fatal"


def resolve_model():
    return os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_MODEL


def _build_client(api_key):
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=REQUEST_TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def model_candidates():
    """Models to try, best first, but starting with one already known to work.

    Pinning the preferred model in front of a remembered one would make every
    briefing re-discover an overloaded model, so the known-good name leads.
    """
    candidates = [resolve_model()]
    if _last_good_model and _last_good_model not in candidates:
        candidates.insert(0, _last_good_model)
    candidates.extend(m for m in FALLBACK_MODELS if m not in candidates)
    return candidates


def _remember_model(model):
    global _last_good_model
    _last_good_model = model


def last_model_used():
    """Which model answered most recently (None until a briefing succeeds)."""
    return _last_good_model


def has_api_key():
    """Whether a briefing could be generated right now."""
    try:
        resolve_api_key()
    except BriefingSetupError:
        return False
    return True


# The engine, not the model, decides the strategy. This prompt is written so
# the overview can only explain the plans it is given: every plan arrives
# already chosen, with the race it is meant for, and every instruction that
# could turn the model into a strategist is spelled out here rather than left
# to chance.
OVERVIEW_INSTRUCTIONS = """You are a Formula 1 race engineer. Three plans below have ALREADY \
been chosen by the team's strategy engine, and each one carries a role: the race \
conditions it is meant for. Your only job is to explain each plan on its own terms.

Hard rules - follow every one:
- Every plan is final. Do not propose, recommend, hint at, evaluate, or invent
  any other strategy, stop count, or compound order.
- Do not rank the plans or say one is worse than another. Plan A is the
  baseline, Plan B and Plan C are the shapes the race takes when Plan A's
  assumptions break, so explain each against its own role instead.
- Do not change any detail of a plan: no extra stops, no different tyres, no
  new pit laps or pit windows.
- Do not repeat a plan back as a table, bullet list, or stint-by-stint
  breakdown. The interface already displays that.
- Use only the supplied data. Do not invent lap times, gaps, forecasts,
  rival behaviour, or statistics that are not given.

What to write:
- For each plan, 2 to 3 short paragraphs of plain prose. No title, no
  headings, no bullets inside the paragraphs.
- Explain why that plan suits this driver at this circuit in those conditions,
  tying each reason to the supplied driver ratings, tyre characteristics, and
  track/weather data.
- Say what the plan protects against and what has to go right for it to work.

Output format - use exactly these three marker lines, each on a line of its own,
with the paragraphs directly beneath it and nothing else in the reply:
PLAN A
<paragraphs>
PLAN B
<paragraphs>
PLAN C
<paragraphs>
"""

# "PLAN A" / "PLAN B" / "PLAN C" on its own line, tolerating markdown bold and
# a trailing colon, is what separates the three answers.
SECTION_MARKER = re.compile(
    r"^[ \t]*\*{0,2}[ \t]*PLAN[ \t]+([ABC])[ \t]*[::\-—]?[ \t]*\*{0,2}[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


def _split_sections(text):
    """Map "Plan A" / "Plan B" / "Plan C" to the prose beneath each marker."""
    matches = list(SECTION_MARKER.finditer(text))
    sections = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():end].strip()
        if body:
            sections[f"Plan {match.group(1).upper()}"] = body
    return sections


def generate_plan_overviews(plans, driver, track, weather):
    """Explain the engine's plans; the model chooses and ranks nothing.

    All three plans go out in a single request because they are one coherent
    race picture, and three separate calls would triple the wait on a model
    that is already slow to reach.
    """
    sources, placeholder_path = _key_sources()
    if not sources:
        raise _configuration_error(placeholder_path)

    context = {
        "driver": driver,
        "track": track,
        "weather": weather,
        "plans": [
            {
                "name": plan.get("plan_name"),
                "role": plan.get("role"),
                "stops": plan.get("stops"),
                "tyres": plan.get("tyres"),
                "pit_windows": plan.get("pit_windows"),
                "stints": plan.get("stints"),
            }
            for plan in plans
        ],
    }

    prompt = OVERVIEW_INSTRUCTIONS + "\nData:\n" + json.dumps(
        context, default=str, indent=2
    )

    text = _request(prompt, sources)
    sections = _split_sections(text)
    if sections:
        return sections

    # No readable markers: keep the answer rather than lose it, but attach it
    # only to Plan A so nothing is presented as belonging to the wrong plan.
    print("[gemini] reply had no PLAN A/B/C markers; showing it under Plan A only")
    return {plans[0].get("plan_name") or "Plan A": text}


def _request(prompt, sources):
    """Ask Gemini, walking keys and models until one answers."""
    rejected = []
    exhausted = []

    for api_key, label in sources:
        client = _build_client(api_key)
        skipped = []

        for candidate in model_candidates():
            try:
                response = client.models.generate_content(
                    model=candidate, contents=prompt
                )
            except Exception as exc:
                kind = _classify(exc)
                if kind == "model":
                    # Retired or briefly overloaded - try the next model.
                    skipped.append(f"{candidate} ({getattr(exc, 'code', '?')})")
                    continue
                if kind == "auth":
                    # A key can be wrong regardless of the model, so hold the
                    # error and give the next configured key a turn.
                    rejected.append((label, exc))
                    break
                # Malformed request or a permission problem we cannot fix here.
                raise RuntimeError(
                    f"Gemini rejected the request for model '{candidate}': {exc}"
                ) from exc

            if not response.text:
                skipped.append(f"{candidate} (empty response)")
                continue

            _remember_model(candidate)
            if skipped:
                # Visible in the Streamlit terminal, so a substitution is not silent.
                print(
                    f"[gemini] answered with '{candidate}'; "
                    f"skipped {', '.join(skipped)}"
                )
            if rejected:
                print(
                    f"[gemini] the key from {rejected[0][0]} was rejected; "
                    f"using the key from {label} instead"
                )
            return response.text.strip()

        exhausted.append((label, tuple(skipped)))

    if rejected:
        label, exc = rejected[0]
        if len(sources) > 1:
            advice = (
                f" All {len(sources)} configured keys were tried. Replace the "
                f"stale key, or remove it so the working one is used."
            )
        else:
            advice = (
                " Replace it with a valid key from "
                "https://aistudio.google.com/apikey"
            )
        raise RuntimeError(
            f"Gemini rejected the key from {label}: {exc}.{advice}"
        ) from exc

    tried = exhausted[0][1] if exhausted else ()
    raise RuntimeError(
        "Gemini did not answer with any available model. Tried: "
        + ", ".join(tried)
        + ". This is usually temporary; check "
        "https://ai.google.dev/gemini-api/docs/models for current names, or set "
        "GEMINI_MODEL to one that is available to your key."
    )
