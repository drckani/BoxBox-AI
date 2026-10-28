# Data Methodology

## Overview

BoxBox AI is a deterministic Formula 1 strategy recommendation engine.

It does not use machine learning, live telemetry, or real-time APIs.

Instead, all recommendations are generated using static datasets and rule-based heuristics.

The objective is to demonstrate software engineering, algorithm design, and clean architecture rather than predictive accuracy.

---

# Data Sources

The project uses publicly available Formula 1 information including:

- FIA circuit specifications
- Formula 1 circuit characteristics
- Pirelli tyre compound documentation
- Historical Safety Car and VSC statistics
- Historical overtaking statistics
- Historical pit lane loss data
- Publicly available driver and team statistics

All datasets are converted into simplified engineering ratings suitable for deterministic decision making.

---

# Data Files

All datasets live in the repository root next to `data_loader.py`, which
resolves the path from its own location, so the app runs from any directory.

## tracks.json

Contains circuit-specific characteristics. The measured inputs are:

- Race distance and lap count
- Track temperature
- Energy demand
- Abrasiveness
- Tyre degradation
- Pit lane loss
- Safety Car probability
- VSC probability
- Overtaking difficulty
- Average overtakes

Two of these fields, `vscProbability` and `averageOvertakes`, are carried for
future work and are **not** read by the scoring engine today: virtual safety
cars and historical overtaking counts are not modelled.

The engine also needs seven derived parameters. Rather than inventing a second
dataset, they are generated from the measured inputs above using the formulas
below, so every circuit stays internally consistent. `severity` is
`(energyDemand + abrasiveness + tyreDegradation) / 3`, and `clamp(v, lo, hi)`
bounds a value to a range.

| Field | Derivation |
|---|---|
| `tyre_loss_seconds_per_percent` | `clamp(0.090 + (severity - 5) × 0.008, 0.060, 0.140)` |
| `starting_position_penalty_seconds` | `clamp(0.060 + overtakingDifficulty × 0.008, 0.060, 0.140)` |
| `oneStopDifficulty` | `clamp(0.20 + (severity - 5) × 0.020, 0.10, 0.40)` |
| `twoStopDifficulty` | `clamp(0.45 + (severity - 5) × 0.040, 0.25, 0.80)` |
| `threeStopDifficulty` | `clamp(0.75 + (severity - 5) × 0.050, 0.50, 1.15)` |
| `sc_pit_saving_seconds` | `pitLaneLoss × 0.55` |
| `pitWindowSize` | `4` if abrasiveness ≤ 4, `3` if ≤ 7, else `2` |

`tests/test_strategy_engine.py` asserts that every one of these fields is
present on every circuit, so the engine can never silently fall back to a
default value again.

## compounds.json

Contains the five Pirelli slick compounds (C1–C5) plus the wet-weather
compounds (Intermediate and Wet). Wet compounds carry `"wet": true`, which
is what lets the engine build wet strategies from the data instead of a
hardcoded list.

Each compound stores:

- Grip
- Durability
- Warm-up
- Wear rate
- Ideal track severity

These values are simplified engineering ratings on a scale of 1–10.

## drivers.json

Contains predefined Formula 1 driver profiles, each with a `team` id, season
points and wins. Users may also create custom drivers by entering their own
ratings.

## teams.json

Contains team-specific operational data, measured as pit lane time lost from
pit entry to exit:

- Median pit lane loss
- Best pit lane loss
- Pit stop ranking

The engine uses the median to compute each team's delta against the field
median, which is added to every stop. A slower pit crew therefore makes an
extra stop slightly more expensive for that driver.

## weather.json

Contains simplified weather profiles.

Supported conditions:

- Dry
- Wet

Dry races use the selected Pirelli compounds.

Wet races generate Intermediate and Wet tyre strategies.

`paceModifier` scales lap-time sensitivity and `wearModifier` scales the
wear rate, so both values are used by the tyre model.

---

# Rating System

Most engineering values use a simplified **1–10** scale.

Driver ratings are measured against a neutral driver rather than against
zero. The 2026 dataset spans roughly 6–10 in every attribute, so the engine
treats **8** as an average driver, making a lower rating a real weakness and
a higher one a real strength. That threshold is the `NEUTRAL_RATING`
constant in `strategy_engine.py`, and it is also the fallback for any rating a
driver profile omits. `MIN_STINT_LAPS` in the same file is the shortest stint
the engine will recommend, so it never suggests pitting again after a couple
of laps.

Examples include:

- Energy Demand
- Abrasiveness
- Tyre Degradation
- Grip
- Durability
- Warm-up

The simplified scale keeps the strategy engine easy to understand while remaining realistic enough for demonstration purposes.

---

# Strategy Generation

The engine generates every legal tyre strategy for the selected race conditions.

Each strategy gets a fixed lap allocation from a memoised dynamic program that
maximises total tyre performance across the stints, subject to a minimum stint
length and each compound's usable life.

It is then evaluated using weighted heuristics based on:

- Tyre characteristics
- Track characteristics
- Driver profile
- Starting position
- Team pit performance
- Safety Car probability

Scores are expressed in **seconds of race time**; `SCORING.md` documents every
term and its weight. The three resulting plans are:

- Plan A — the fastest plan in clean air
- Plan B — the same race with a different stop count
- Plan C — the most aggressive shape available

---

# Project Philosophy

This project prioritizes:

- Clean software architecture
- Maintainability
- Deterministic algorithms
- Explainable decision making

over simulation accuracy.

The goal is to showcase software engineering principles rather than replicate Formula 1 race strategy with complete real-world fidelity.
