"""Tests for the BoxBox AI strategy engine.

Dependency-free: run with ``python3 tests/test_strategy_engine.py`` or with
pytest. They cover the model invariants the docs claim, so a regression in the
tyre model or the scoring terms fails loudly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_loader import get_compounds, get_drivers, get_tracks  # noqa: E402
from strategy_engine import NEUTRAL_RATING, StrategyEngine  # noqa: E402

ENGINE = StrategyEngine()
DRIVERS = {driver["id"]: driver for driver in get_drivers()}
TRACKS = {track["id"]: track for track in get_tracks()}


def test_datasets_load():
    assert len(DRIVERS) > 0
    assert len(TRACKS) > 0
    assert len(get_compounds()) > 0


def test_track_fields_the_engine_reads_are_present():
    """Every key the engine reads from tracks.json must exist in every track."""
    required = (
        "tyre_loss_seconds_per_percent",
        "starting_position_penalty_seconds",
        "oneStopDifficulty",
        "twoStopDifficulty",
        "threeStopDifficulty",
        "sc_pit_saving_seconds",
        "pitWindowSize",
        "pitLaneLoss",
        "safetyCarProbability",
    )
    for track_id, track in TRACKS.items():
        missing = [key for key in required if key not in track]
        assert not missing, f"{track_id} is missing {missing}"


def test_softer_compounds_have_shorter_life():
    track, driver = TRACKS["japan"], DRIVERS["hamilton"]
    hard = ENGINE.calculate_tyre_life("C1", track, "Dry", driver)
    medium = ENGINE.calculate_tyre_life("C3", track, "Dry", driver)
    soft = ENGINE.calculate_tyre_life("C5", track, "Dry", driver)
    assert hard > medium > soft


def test_better_tyre_management_lengthens_life():
    track = TRACKS["japan"]
    good = ENGINE.calculate_tyre_life("C3", track, "Dry", DRIVERS["hamilton"])
    poor = ENGINE.calculate_tyre_life("C3", track, "Dry", DRIVERS["stroll"])
    assert good > poor


def test_more_stops_cost_more_pit_time():
    track, driver = TRACKS["japan"], DRIVERS["hamilton"]
    one = ENGINE.calculate_pit_score({"stops": 1}, track, driver)
    three = ENGINE.calculate_pit_score({"stops": 3}, track, driver)
    assert three > one


def test_team_pit_crew_changes_the_cost_of_a_stop():
    track = TRACKS["japan"]
    fast = ENGINE.calculate_pit_score({"stops": 1}, track, DRIVERS["leclerc"])
    slow = ENGINE.calculate_pit_score({"stops": 1}, track, DRIVERS["perez"])
    assert fast < slow


def test_starting_position_changes_the_recommendation():
    """The exposed Starting Position input must actually move the answer."""
    driver, track = DRIVERS["hamilton"], TRACKS["japan"]
    strategy = {
        "tyres": ["C3", "C4", "C3"],
        "stops": 2,
        "stints": ENGINE.build_stints(
            {"tyres": ["C3", "C4", "C3"]}, track, "Dry", driver
        ),
    }
    front = ENGINE.evaluate_strategy(strategy, driver, track, "Dry", 1)
    back = ENGINE.evaluate_strategy(strategy, driver, track, "Dry", 20)
    assert front != back, "grid position must affect the score"

    def shape(circuit, position):
        return [
            (plan["stops"], tuple(plan["tyres"]))
            for plan in ENGINE.generate_strategy(
                driver, circuit, "Dry", position, "C3", "C4", "C2"
            )
        ]

    changed = [
        track_id
        for track_id, circuit in TRACKS.items()
        if shape(circuit, 1) != shape(circuit, 20)
    ]
    assert changed, "grid position never changes a recommendation on any circuit"


def test_safety_car_probability_reduces_pit_penalty():
    track = dict(TRACKS["japan"])
    track["sc_pit_saving_seconds"] = 12.0
    track["safetyCarProbability"] = 1.0
    calm = dict(track, safetyCarProbability=0.0)
    one_stop = {"stops": 1}
    assert ENGINE.calculate_race_score(one_stop, track, 10) < ENGINE.calculate_race_score(
        one_stop, calm, 10
    )


def test_generate_strategy_contract():
    plans = ENGINE.generate_strategy(
        DRIVERS["hamilton"], TRACKS["japan"], "Dry", 5, "C3", "C4", "C2"
    )
    assert [p["plan_name"] for p in plans] == ["Plan A", "Plan B", "Plan C"]
    assert len({tuple(p["tyres"]) for p in plans}) == 3, "plans must differ"
    for plan in plans:
        assert plan["stops"] == len(plan["tyres"]) - 1
        assert sum(s["laps"] for s in plan["stints"]) == TRACKS["japan"]["laps"]
        assert all(s["laps"] >= 8 for s in plan["stints"])
        assert plan["role"]["label"]


def test_wet_races_use_wet_compounds():
    plans = ENGINE.generate_strategy(
        DRIVERS["hamilton"], TRACKS["japan"], "Wet", 5, None, None, None
    )
    wet_ids = {"Intermediate", "Wet"}
    for plan in plans:
        assert set(plan["tyres"]) <= wet_ids


def test_unrated_driver_falls_back_to_neutral():
    """A driver with no ratings must be modelled as average, not as hopeless."""
    track = TRACKS["japan"]
    rated = ENGINE.calculate_tyre_life(
        "C3", track, "Dry", {"ratings": {"tyre_management": NEUTRAL_RATING}}
    )
    unrated = ENGINE.calculate_tyre_life("C3", track, "Dry", {"ratings": {}})
    assert rated == unrated


if __name__ == "__main__":
    failures = 0
    for name, case in sorted(globals().items()):
        if not name.startswith("test_") or not callable(case):
            continue
        try:
            case()
            print(f"PASS  {name}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {name}: {exc}")
    print(f"\n{'all tests passed' if not failures else f'{failures} failing'}")
    sys.exit(1 if failures else 0)
