import streamlit as st

from data_loader import get_drivers, get_tracks
from gemini_engine import (
    SETUP_HELP as BRIEFING_SETUP_HELP,
    BriefingSetupError,
    generate_plan_overviews,
    has_api_key,
    last_model_used,
)
from strategy_engine import StrategyEngine


st.set_page_config(
    page_title="BoxBox AI",
    page_icon="🏎️",
    layout="wide",
)

st.title("🏎️ BoxBox AI")
st.subheader("Formula 1 Strategy Recommendation Engine")

if not has_api_key():
    st.info(
        "Strategy generation works right now. AI overviews stay off "
        "until a Gemini API key is configured."
    )
    with st.expander("How to enable AI overviews"):
        st.markdown(BRIEFING_SETUP_HELP)

drivers = get_drivers()
tracks = get_tracks()

if not drivers:
    st.error("No drivers found. Check drivers.json.")
    st.stop()

if not tracks:
    st.error("No tracks found. Check tracks.json.")
    st.stop()

# Driver selection
driver_option = st.radio(
    "Driver Selection",
    ["Choose 2026 Driver", "Create Custom Driver"],
)

if driver_option == "Choose 2026 Driver":
    driver_names = [driver.get("name", "Unknown") for driver in drivers]
    selected_driver = st.selectbox("Select Driver", driver_names)
    driver = next(
        item for item in drivers
        if item.get("name", "Unknown") == selected_driver
    )
else:
    st.subheader("Custom Driver")
    name = st.text_input("Driver Name")

    col1, col2 = st.columns(2)
    with col1:
        # Defaults match the engine's NEUTRAL_RATING, so an untouched custom
        # driver is an average driver rather than a hopeless one.
        qualifying = st.slider("Qualifying", 1, 10, 8)
        race_pace = st.slider("Race Pace", 1, 10, 8)
        tyre_management = st.slider("Tyre Management", 1, 10, 8)
        overtaking = st.slider("Overtaking", 1, 10, 8)
    with col2:
        wet_weather = st.slider("Wet Weather", 1, 10, 8)
        consistency = st.slider("Consistency", 1, 10, 8)
        aggression = st.slider("Aggression", 1, 10, 8)

    driver = {
        "id": "custom",
        "name": name or "Custom Driver",
        "ratings": {
            "qualifying": qualifying,
            "race_pace": race_pace,
            "tyre_management": tyre_management,
            "overtaking": overtaking,
            "wet_weather": wet_weather,
            "consistency": consistency,
            "aggression": aggression,
        },
    }

# Track and race conditions
track_names = [track.get("name", "Unknown") for track in tracks]
selected_track = st.selectbox("Track", track_names)
track = next(
    item for item in tracks
    if item.get("name", "Unknown") == selected_track
)

weather = st.radio("Weather", ["Dry", "Wet"])

if weather == "Dry":
    st.subheader("Weekend Tyre Allocation")
    col1, col2, col3 = st.columns(3)

    with col1:
        hard = st.selectbox("Hard Compound", ["C1", "C2", "C3"], index=2)

    if hard == "C1":
        medium_options = ["C2", "C3", "C4"]
    elif hard == "C2":
        medium_options = ["C3", "C4"]
    else:
        medium_options = ["C4"]

    with col2:
        medium = st.selectbox("Medium Compound", medium_options)

    if medium == "C2":
        soft_options = ["C3", "C4", "C5"]
    elif medium == "C3":
        soft_options = ["C4", "C5"]
    else:
        soft_options = ["C5"]

    with col3:
        soft = st.selectbox("Soft Compound", soft_options)
else:
    st.info("Wet strategies use Intermediate and Wet tyres.")
    soft, medium, hard = "Intermediate", "Wet", "Wet"

# Generate and display strategies
starting_position = st.number_input(
    "Starting Position",
    min_value=1,
    max_value=22,
    value=10,
    step=1,
)

def render_plan(plan, index, overviews):
    """One plan, explained exactly the same way whether it is A, B or C."""
    name = plan.get("plan_name", f"Plan {chr(65 + index)}")
    role = plan.get("role") or {}

    container = st.container() if index == 0 else st.container(border=True)
    with container:
        st.subheader(f"🏁 {name}")
        if role.get("label"):
            st.caption(role["label"])
        if role.get("scenario"):
            st.write(role["scenario"])

        metrics = st.columns(2)
        metrics[0].metric("Stops", plan.get("stops", "—"))
        tyres = plan.get("tyres", [])
        metrics[1].metric("Tyres", " → ".join(tyres) if tyres else "—")

        overview = overviews.get(name)
        if overview:
            st.markdown("#### 🤖 AI Overview")
            st.write(overview)

        st.markdown("**Stints and pit plan**")
        stints = plan.get("stints", [])
        if stints:
            st.table(stints)
        else:
            st.info("No stint breakdown was included.")

        pit_laps = plan.get("pit_laps", [])
        pit_windows = plan.get("pit_windows", [])

        if pit_laps:
            st.write("**Pit laps:**", ", ".join(map(str, pit_laps)))
        elif pit_windows:
            if isinstance(pit_windows, str):
                st.write("**Pit windows:**", pit_windows)
            else:
                st.write("**Pit windows:**", ", ".join(map(str, pit_windows)))
        else:
            st.write("**Pit plan:** None specified")


if st.button("Generate Strategy"):
    engine = StrategyEngine()

    try:
        result = engine.generate_strategy(
            driver,
            track,
            weather,
            starting_position,
            soft,
            medium,
            hard,
        )
    except Exception as exc:
        st.error(f"Strategy generation failed: {type(exc).__name__}: {exc}")
        st.stop()

    if isinstance(result, dict):
        strategies = [result]
    elif isinstance(result, list):
        strategies = [item for item in result if isinstance(item, dict)]
    else:
        strategies = []

    if not strategies:
        st.error("No valid strategies were returned.")
        st.stop()

    plans = strategies[:3]

    st.success("Strategy generated")

    overviews = {}
    overview_failure = None
    try:
        # Explanation only: every plan above was chosen by the engine.
        overviews = generate_plan_overviews(
            plans=plans,
            driver=driver,
            track=track,
            weather=weather,
        )
    except BriefingSetupError as exc:
        overview_failure = ("info", f"AI overviews skipped. {exc}")
    except Exception as exc:
        overview_failure = (
            "warning",
            f"Gemini overviews unavailable "
            f"({type(exc).__name__}): {exc}",
        )

    if overview_failure:
        kind, message = overview_failure
        if kind == "info":
            st.info(message)
        else:
            st.warning(message)

    for index, plan in enumerate(plans):
        render_plan(plan, index, overviews)

    if overviews and last_model_used():
        st.caption(f"AI overviews generated by {last_model_used()}")