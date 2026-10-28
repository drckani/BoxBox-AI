from data_loader import get_compound, get_compounds, get_weather_type
from functools import lru_cache
from itertools import product


# =====================================================
# TUNING CONSTANTS
# =====================================================
# Scores are expressed as approximate seconds of race time, so every
# constant below is measured in seconds of race time.

# The rating that means "an average driver". The 2026 dataset spans roughly
# 6-10 in every attribute, so 5 would model every real driver as at least
# average and the differences between them would compress to nothing.
NEUTRAL_RATING = 8

# A strategy engine will not recommend pitting again after fewer laps than
# this; without a floor the allocator happily grabs two peak-grip laps and
# calls that a stint.
MIN_STINT_LAPS = 8

# Traffic cost per extra stop, per level of circuit overtaking difficulty.
# A car that pits again rejoins behind cars it had already passed.
TRAFFIC_SECONDS_PER_LEVEL = 1.4

# How strongly driver tyre management stretches usable tyre life, and the
# slowest wear the model will assume for an extremely hard driver.
TYRE_MANAGEMENT_LIFE_PER_RATING = 0.12
TYRE_MANAGEMENT_LIFE_FLOOR = 0.60

# How much of a tyre's ideal life a circuit takes away. Severity removes a
# *fraction* of the ideal life rather than a flat lap count, which is what
# keeps a 16-lap soft usable instead of wiping it out on a hard circuit.
SEVERITY_PER_DEGRADATION = 0.025
SEVERITY_PER_ABRASION = 0.012
MAX_TRACK_SEVERITY = 0.40

# Track temperature scales usable life as a fraction.
TEMPERATURE_LIFE_FACTOR = {
    "Cold": 1.07,
    "Mild": 1.03,
    "Warm": 1.00,
    "Hot": 0.93,
}

# How strongly driver tyre management changes the cost of a worn tyre.
TYRE_MANAGEMENT_COST_PER_RATING = 0.13
TYRE_MANAGEMENT_COST_FLOOR = 0.30

# Fresh-tyre value per rating point away from NEUTRAL_RATING, per extra stop.
# Tyre management is the strongest single lever: a driver who cannot look
# after a tyre has to buy fresh rubber, one who can, does not.
APPETITE_TYRE_MANAGEMENT = 2.60
APPETITE_AGGRESSION = 1.20
APPETITE_CONSISTENCY = 1.10
APPETITE_QUALIFYING = 1.40

# Share of the traffic penalty a driver avoids, per rating point above 5.
TRAFFIC_RELIEF_PER_OVERTAKING = 0.08
TRAFFIC_RELIEF_PER_PACE = 0.04
TRAFFIC_RELIEF_CAP = 0.40

# Fresh-tyre value a wet-weather specialist extracts, per extra stop.
WET_SKILL_PER_RATING = 1.50


class StrategyEngine:

    def generate_strategy(
        self,
        driver,
        track,
        weather,
        starting_position,
        soft_compound,
        medium_compound,
        hard_compound,
    ):
        if weather == "Wet":
            wet_compounds = [c for c in get_compounds() if c.get("wet")]
            if not wet_compounds:
                raise ValueError(
                    "No wet-weather compounds are defined in compounds.json."
                )
            compounds = [compound["id"] for compound in wet_compounds]
            # The most aggressive wet tyre is the one that gives up its life
            # soonest, which is what the chaos plan looks for.
            soft_tyre = min(
                wet_compounds, key=lambda compound: compound["baseLife"]
            )["id"]
        else:
            compounds = list(dict.fromkeys(
                compound
                for compound in (
                    soft_compound,
                    medium_compound,
                    hard_compound,
                )
                if compound
            ))
            if not compounds:
                raise ValueError("Select at least one dry tyre compound.")

            soft_tyre = soft_compound

        sequences = [
            sequence
            for stint_count in (2, 3, 4)
            for sequence in product(compounds, repeat=stint_count)
            if all(
                previous != current
                for previous, current in zip(sequence, sequence[1:])
            )
        ]

        candidates = []
        errors = []

        for sequence in sequences:
            strategy = {
                "tyres": list(sequence),
                "stops": len(sequence) - 1,
            }
            try:
                strategy["stints"] = self.build_stints(
                    strategy, track, weather, driver
                )
                strategy["_score"] = self.evaluate_strategy(
                    strategy, driver, track, weather, starting_position
                )
            except (ValueError, KeyError) as exc:
                errors.append(str(exc))
                continue

            candidates.append(strategy)

        if not candidates:
            detail = errors[0] if errors else "No candidate strategies were generated."
            raise ValueError(f"No viable strategies: {detail}")

        candidates.sort(key=lambda item: item["_score"], reverse=True)
        selected = [candidates[0]]

        # Alternate: strongest plan with a different number of stops, if possible.
        alternate_pool = [
            item for item in candidates
            if item["stops"] != selected[0]["stops"]
        ] or candidates[1:]
        if alternate_pool:
            selected.append(alternate_pool[0])

        # Plan C: favor more stops and soft tyres, while keeping it score-aware.
        chaos_pool = [
            item for item in candidates
            if all(item["tyres"] != chosen["tyres"] for chosen in selected)
        ]
        if chaos_pool:
            selected.append(max(
                chaos_pool,
                key=lambda item: (
                    item["stops"],
                    item["tyres"].count(soft_tyre),
                    item["_score"],
                ),
            ))

        names = [
            "Plan A",
            "Plan B",
            "Plan C",
        ]
        for index, strategy in enumerate(selected):
            strategy["plan_name"] = names[index]
            strategy.pop("_score", None)

        # Each plan is a different answer to a different race, not a ranked
        # shortlist. The role states which race that is, so the interface and
        # the AI overview both explain the plan on its own terms.
        baseline = selected[0]
        for index, strategy in enumerate(selected):
            strategy["role"] = self.describe_plan_role(
                strategy, baseline, weather, index
            )

        return selected

    def describe_plan_role(self, plan, baseline, weather, index):
        """The job a plan does, stated against the race it is built for.

        Plan A is the engine's fastest clean-air plan. Plan B changes the stop
        count, and Plan C is the most aggressive shape available, so both are
        described by the condition that would select them rather than by how
        far they trail Plan A.
        """
        stops = plan.get("stops", 0)
        tyres = plan.get("tyres") or []
        sequence = " → ".join(tyres)
        baseline_stops = baseline.get("stops", 0)
        extra = stops - baseline_stops
        first_tyre = tyres[0] if tyres else "the starting tyre"
        wet = str(weather).lower() == "wet"
        plural = "stop" if stops == 1 else "stops"

        if index == 0:
            if wet:
                tail = (
                    "the rain holds at its forecast intensity and the track "
                    "does not dry enough to force a change"
                )
            else:
                tail = (
                    "you hold your starting slot, the safety car falls on a "
                    "sensible lap, and tyre life matches the forecast"
                )
            return {
                "label": "Baseline — the race runs to form",
                "scenario": (
                    f"The engine's fastest plan in clean air: {stops} {plural} "
                    f"off {first_tyre} ({sequence}). Run it when {tail}."
                ),
            }

        if index == 1:
            if extra > 0:
                added = "stop" if extra == 1 else "stops"
                if wet:
                    detail = (
                        "It also covers rain arriving harder than forecast, "
                        "which shortens the life of every wet tyre."
                    )
                else:
                    detail = (
                        f"It also covers a track running hotter than forecast, "
                        f"where {first_tyre} gives up its life sooner than "
                        f"modelled."
                    )
                return {
                    "label": "Recovery — you lose track position early",
                    "scenario": (
                        f"{extra} more {added} than Plan A ({stops} vs "
                        f"{baseline_stops}), buying fresh rubber with pit-lane "
                        f"time. Switch to it if you drop places at the start, "
                        f"get stuck behind a car you cannot pass, or an early "
                        f"safety car makes another stop cheap. {detail}"
                    ),
                }

            if extra < 0:
                saved = abs(extra)
                added = "stop" if saved == 1 else "stops"
                if wet:
                    detail = (
                        "Best when the track dries faster than forecast and "
                        "the extra wet-tyre changes would be thrown away."
                    )
                else:
                    detail = (
                        "Best when the race settles into a train and passing "
                        "is expensive on this circuit."
                    )
                return {
                    "label": "Track position — you are ahead and cannot pass",
                    "scenario": (
                        f"{saved} fewer {added} than Plan A ({stops} vs "
                        f"{baseline_stops}): less time in the pit lane and the "
                        f"clean air you need to defend. {detail}"
                    ),
                }

            baseline_tyre = (baseline.get("tyres") or ["the planned tyre"])[0]
            return {
                "label": "Alternative — same stop count, different rubber",
                "scenario": (
                    f"A second shape with {stops} {plural} ({sequence}), opening "
                    f"on {first_tyre} instead of Plan A's {baseline_tyre}. Use "
                    f"it when the planned starting tyre is not behaving as "
                    f"expected, or when the first stint has to be cut short."
                ),
            }

        if wet:
            detail = (
                "rain arriving harder than forecast, or a track that dries "
                "enough to make the wet tyres unusable early"
            )
        else:
            detail = (
                "wear running far hotter than forecast, a safety car that "
                "arrives too late to help, or a need to push flat out to the "
                "end"
            )
        if extra > 0:
            shape = f"{stops} {plural} ({sequence}), {extra} more than Plan A"
        else:
            shape = (
                f"{stops} {plural} ({sequence}), the same stop count as Plan A "
                f"but on the most aggressive rubber available"
            )
        return {
            "label": "Fallback — the race goes against you",
            "scenario": (
                f"The most aggressive shape the model holds: {shape}. Keep it "
                f"for the race breaking its script — {detail}. It carries the "
                f"most pit-lane time and traffic risk, so it is an answer to "
                f"a problem, not a default."
            ),
        }

    # =====================================================
    # PLAN GENERATION
    # =====================================================

    def generate_one_stop(self, starting_tyre, finish_tyre, track):
        laps = track["laps"]
        return {
            "stops": 1,
            "tyres": [starting_tyre, finish_tyre],
            "pit_windows": [f"Lap {laps // 2}"],
        }

    def generate_two_stop(self, start_tyre, middle_tyre, finish_tyre, track):
        laps = track["laps"]
        return {
            "stops": 2,
            "tyres": [start_tyre, middle_tyre, finish_tyre],
            "pit_windows": [f"Lap {laps // 3}", f"Lap {(2 * laps) // 3}"],
        }

    def generate_three_stop(self, tyre1, tyre2, tyre3, tyre4, track):
        laps = track["laps"]
        return {
            "stops": 3,
            "tyres": [tyre1, tyre2, tyre3, tyre4],
            "pit_windows": [
                f"Lap {laps // 4}",
                f"Lap {laps // 2}",
                f"Lap {(3 * laps) // 4}",
            ],
        }

    def generate_candidate_strategies(
        self,
        driver,
        track,
        weather,
        starting_position,
        soft_compound,
        medium_compound,
        hard_compound,
    ):
        if weather == "Wet":
            sequences = [
                ("Intermediate", "Wet"),
                ("Wet", "Intermediate"),
            ]
        else:
            compounds = [soft_compound, medium_compound, hard_compound]
            candidates = []

            for start_tyre in compounds:
                for finish_tyre in compounds:
                    if start_tyre == finish_tyre:
                        continue
                    candidates.append(
                        self.generate_one_stop(start_tyre, finish_tyre, track)
                    )

            for start_tyre in compounds:
                for middle_tyre in compounds:
                    for finish_tyre in compounds:
                        if len({start_tyre, middle_tyre, finish_tyre}) < 3:
                            continue
                        candidates.append(
                            self.generate_two_stop(
                                start_tyre, middle_tyre, finish_tyre, track
                            )
                        )

            for tyre1 in compounds:
                for tyre2 in compounds:
                    for tyre3 in compounds:
                        for tyre4 in compounds:
                            tyres = [tyre1, tyre2, tyre3, tyre4]
                            if any(a == b for a, b in zip(tyres, tyres[1:])):
                                continue
                            candidates.append(
                                self.generate_three_stop(*tyres, track)
                            )

            return candidates

    def score_strategy(
        self,
        strategy,
        driver,
        track,
        weather,
        starting_position,
    ):
        return self.evaluate_strategy(
            strategy,
            driver,
            track,
            weather,
            starting_position,
        )

    def pick_best_three(
        self,
        strategies,
        driver,
        track,
        weather,
        starting_position,
    ):
        return sorted(
            strategies,
            key=lambda strategy: self.score_strategy(
                strategy, driver, track, weather, starting_position
            ),
            reverse=True,
        )[:3]

    # =====================================================
    # TYRE LIFE MODEL
    # =====================================================

    def _get_compound_data(self, compound):
        compound_data = get_compound(compound)
        if compound_data is None:
            raise ValueError(f"Unknown compound: {compound}")
        return compound_data

    def _weather_profile(self, weather):
        profile = get_weather_type(weather)
        if profile is None:
            raise ValueError(f"Unknown weather type: {weather}")
        return profile

    def calculate_tyre_life(self, compound, track, weather, driver):
        compound_data = self._get_compound_data(compound)
        life = compound_data["baseLife"]

        severity = min(
            MAX_TRACK_SEVERITY,
            track.get("tyreDegradation", 0) * SEVERITY_PER_DEGRADATION
            + track.get("abrasiveness", 0) * SEVERITY_PER_ABRASION,
        )
        life *= 1 - severity

        life *= TEMPERATURE_LIFE_FACTOR.get(
            track.get("trackTemperature"), 1.0
        )

        # weather.json's wearModifier is a wear *rate*: 0.85 means the tyre
        # wears 15% more slowly, so it lives proportionally longer.
        wear_modifier = self._weather_profile(weather).get("wearModifier", 1.0)
        if wear_modifier > 0:
            life /= wear_modifier

        rating = driver.get("ratings", {}).get("tyre_management", 5)
        life *= max(
            TYRE_MANAGEMENT_LIFE_FLOOR,
            1 + (rating - NEUTRAL_RATING) * TYRE_MANAGEMENT_LIFE_PER_RATING,
        )
        return max(1, round(life))

    def calculate_tyre_performance(
        self, stint_lap, compound, tyre_life, compound_data=None
    ):
        if compound_data is None:
            compound_data = self._get_compound_data(compound)

        curve = compound_data["performanceCurve"]
        warmup_laps = compound_data["warmupLaps"]
        grip_multiplier = compound_data["baseGrip"]

        # Accept grip as either a multiplier (1.05) or percentage (105).
        grip_multiplier = grip_multiplier / 100 if grip_multiplier > 10 else grip_multiplier

        position = (stint_lap - 1) * (len(curve) - 1) / max(1, tyre_life - 1)
        position = min(max(position, 0), len(curve) - 1)
        lower = int(position)
        upper = min(lower + 1, len(curve) - 1)
        fraction = position - lower

        curve_performance = curve[lower] + (
            curve[upper] - curve[lower]
        ) * fraction

        warmup_factor = (
            min(1.0, stint_lap / warmup_laps)
            if warmup_laps > 0
            else 1.0
        )

        return curve_performance * grip_multiplier * warmup_factor

    # =====================================================
    # SCORING SYSTEM
    # =====================================================

    def evaluate_strategy(
        self,
        strategy,
        driver,
        track,
        weather,
        starting_position,
    ):
        total_penalty = (
            self.calculate_tyre_score(strategy, track, weather, driver)
            + self.calculate_track_score(strategy, track)
            + self.calculate_race_score(strategy, track, starting_position)
            + self.calculate_pit_score(strategy, track)
        )

        return -total_penalty + self.calculate_driver_adjustment(
            strategy, driver, track, weather, starting_position
        )

    def calculate_driver_adjustment(
        self, strategy, driver, track, weather, starting_position
    ):
        """How much this driver values another stop, in seconds.

        Positive values make an extra stop attractive, negative values favour
        staying out. Every driver rating has one clearly defined job:

        tyre_management  weak managers gain more from fresh rubber
        aggression       willing to trade track position for pace
        consistency      dislikes the extra risk of another stop
        qualifying       defends track position when starting near the front
        overtaking,pace  each extra stop costs less traffic on hard circuits
        wet_weather      wet specialists extract more from fresh wet rubber

        Every term scales with the number of extra stops, so a one-stop plan
        is decided by the tyre model alone, which is also driver-specific.
        Ratings are measured against NEUTRAL_RATING, not against zero.
        """
        ratings = driver.get("ratings", {})
        extra_stops = max(0, strategy["stops"] - 1)

        tyre_management = ratings.get("tyre_management", 5)
        aggression = ratings.get("aggression", 5)
        consistency = ratings.get("consistency", 5)
        qualifying = ratings.get("qualifying", 5)
        overtaking = ratings.get("overtaking", 5)
        pace = ratings.get("race_pace", 5)

        # Starting near the front makes track position worth defending.
        front_grid_factor = max(0.0, min(1.0, (11 - starting_position) / 10))

        appetite = (
            (NEUTRAL_RATING - tyre_management) * APPETITE_TYRE_MANAGEMENT
            + (aggression - NEUTRAL_RATING) * APPETITE_AGGRESSION
            - (consistency - NEUTRAL_RATING) * APPETITE_CONSISTENCY
            - front_grid_factor
            * (qualifying - NEUTRAL_RATING)
            * APPETITE_QUALIFYING
        )
        adjustment = extra_stops * appetite

        # A driver who clears traffic quickly loses less by stopping again;
        # one who gets stuck behind a slower car pays more.
        relief = (
            (overtaking - NEUTRAL_RATING) * TRAFFIC_RELIEF_PER_OVERTAKING
            + (pace - NEUTRAL_RATING) * TRAFFIC_RELIEF_PER_PACE
        )
        relief = max(-TRAFFIC_RELIEF_CAP, min(TRAFFIC_RELIEF_CAP, relief))
        adjustment += (
            extra_stops
            * track.get("overtakingDifficulty", 5)
            * TRAFFIC_SECONDS_PER_LEVEL
            * relief
        )

        if str(weather).lower() == "wet":
            adjustment += (
                (ratings.get("wet_weather", 5) - NEUTRAL_RATING)
                * WET_SKILL_PER_RATING
                * extra_stops
            )

        return adjustment

    def calculate_tyre_score(self, strategy, track, weather, driver):
        seconds_per_percent = track.get(
            "tyre_loss_seconds_per_percent", 0.1
        )
        # A slower wet lap makes each percentage point of lost performance
        # cost more absolute time.
        pace_modifier = self._weather_profile(weather).get("paceModifier", 1.0)
        if pace_modifier:
            seconds_per_percent /= pace_modifier

        # Energy-hungry, abrasive, high-degradation circuits punish a worn
        # tyre hardest, so drivers separate most on those circuits.
        severity = (
            track.get("energyDemand", 5)
            + track.get("abrasiveness", 5)
            + track.get("tyreDegradation", 5)
        ) / 3
        severity_factor = 1 + (severity - 5) * 0.06

        rating = max(
            1,
            min(10, driver.get("ratings", {}).get("tyre_management", 5)),
        )
        driver_factor = max(
            TYRE_MANAGEMENT_COST_FLOOR,
            1 + (NEUTRAL_RATING - rating) * TYRE_MANAGEMENT_COST_PER_RATING,
        )
        penalty = 0.0

        for stint in strategy["stints"]:
            compound_data = self._get_compound_data(stint["compound"])
            tyre_life = self.calculate_tyre_life(
                stint["compound"], track, weather, driver
            )
            for lap in range(1, stint["laps"] + 1):
                performance = self.calculate_tyre_performance(
                    lap,
                    stint["compound"],
                    tyre_life,
                    compound_data,
                )
                penalty += (
                    (100 - performance)
                    * seconds_per_percent
                    * driver_factor
                    * severity_factor
                )

        return penalty

    def calculate_track_score(self, strategy, track):
        """Traffic cost for the race, in seconds.

        Every extra stop rejoins the car in traffic on a circuit where
        passing is hard, so the penalty scales with the number of stops and
        with the circuit's overtaking difficulty.
        """
        extra_stops = max(0, strategy["stops"] - 1)
        return (
            extra_stops
            * track.get("overtakingDifficulty", 5)
            * TRAFFIC_SECONDS_PER_LEVEL
        )

    def calculate_race_score(self, strategy, track, starting_position):
        position_penalty = max(0, starting_position - 1) * track.get(
            "starting_position_penalty_seconds", 0.0
        )

        difficulty_key = {
            1: "oneStopDifficulty",
            2: "twoStopDifficulty",
            3: "threeStopDifficulty",
        }.get(strategy["stops"])
        stop_penalty = (
            track.get(difficulty_key, 0.0) * 8
            if difficulty_key
            else 0.0
        )

        sc_probability = min(
            1.0, max(0.0, track.get("safetyCarProbability", 0.0))
        )
        sc_saving = (
            sc_probability
            * strategy["stops"]
            * track.get("sc_pit_saving_seconds", 0.0)
        )

        return position_penalty + stop_penalty - sc_saving

    def calculate_pit_score(self, strategy, track):
        return strategy["stops"] * track.get("pitLaneLoss", 20.0)

    def build_stints(self, strategy, track, weather, driver):
        compounds = strategy["tyres"]
        race_laps = track["laps"]

        if not compounds:
            raise ValueError("Strategy must include at least one tyre compound.")
        if race_laps < len(compounds):
            raise ValueError("Race distance must allow at least one lap per stint.")

        tyre_lives = [
            self.calculate_tyre_life(compound, track, weather, driver)
            for compound in compounds
        ]
        compound_data = [
            self._get_compound_data(compound) for compound in compounds
        ]

        @lru_cache(maxsize=None)
        def best_allocation(index, remaining_laps):
            if index == len(compounds):
                return (0, ()) if remaining_laps == 0 else (float("-inf"), ())

            stints_left = len(compounds) - index - 1
            # Hold back enough laps for every later stint to clear the floor.
            reserve = stints_left * MIN_STINT_LAPS
            max_laps = min(tyre_lives[index], remaining_laps - reserve)
            # The final stint simply runs whatever is left.
            min_laps = MIN_STINT_LAPS if stints_left else remaining_laps - reserve
            if min_laps < 1 or max_laps < min_laps:
                return (float("-inf"), ())
            best_score = float("-inf")
            best_lengths = ()

            for stint_laps in range(min_laps, max_laps + 1):
                stint_score = sum(
                    self.calculate_tyre_performance(
                        lap, compounds[index], tyre_lives[index], compound_data[index]
                    )
                    for lap in range(1, stint_laps + 1)
                )
                rest_score, rest_lengths = best_allocation(
                    index + 1, remaining_laps - stint_laps
                )
                total_score = stint_score + rest_score

                if total_score > best_score:
                    best_score = total_score
                    best_lengths = (stint_laps,) + rest_lengths

            return best_score, best_lengths

        _, stint_lengths = best_allocation(0, race_laps)
        if not stint_lengths:
            raise ValueError("Tyre life is insufficient to cover the race distance.")

        stints = [
            {"compound": compound, "laps": laps}
            for compound, laps in zip(compounds, stint_lengths)
        ]

        strategy["pit_windows"] = []
        cumulative_laps = 0
        window_size = max(1, int(track.get("pitWindowSize", 3)))

        for stint in stints[:-1]:
            cumulative_laps += stint["laps"]
            window_start = max(1, cumulative_laps - window_size + 1)
            strategy["pit_windows"].append(
                f"Lap {window_start}-{cumulative_laps}"
            )

        return stints

    def calculate_driver_score(self, driver, weather, track):
        ratings = driver.get("ratings", {})
        return (
            ratings.get("race_pace", 5) * 8
            + ratings.get("tyre_management", 5) * 4
            + ratings.get("consistency", 5) * 2
        )