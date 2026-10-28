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

## tracks.json

Contains circuit-specific characteristics including:

- Track temperature
- Energy demand
- Abrasiveness
- Tyre degradation
- Pit lane loss
- Safety Car probability
- VSC probability
- Overtaking difficulty
- Average overtakes

---

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

---

## drivers.json

Contains predefined Formula 1 driver profiles.

Users may also create custom drivers by entering their own ratings.

---

## teams.json

Contains team-specific operational data including:

- Average pit stop time
- Best pit stop
- Pit stop ranking

---

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
constant in `strategy_engine.py`. `MIN_STINT_LAPS` in the same file is the
shortest stint the engine will recommend, so it never suggests pitting again
after a couple of laps.

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

Each strategy is evaluated using weighted heuristics based on:

- Tyre characteristics
- Track characteristics
- Driver profile
- Starting position
- Team pit performance
- Safety Car probability
- VSC probability

The highest scoring strategies become:

- Plan A
- Plan B
- Plan C

---

# Project Philosophy

This project prioritizes:

- Clean software architecture
- Maintainability
- Deterministic algorithms
- Explainable decision making

over simulation accuracy.

The goal is to showcase software engineering principles rather than replicate Formula 1 race strategy with complete real-world fidelity.
