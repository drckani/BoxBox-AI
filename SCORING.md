# BoxBox AI — Strategy Scoring

## How a score is expressed

Every candidate strategy is scored in **seconds of race time**. A strategy's
final score is:

```
score = -total_penalty + driver_adjustment
```

- `total_penalty` is the time the plan is expected to lose.
- `driver_adjustment` is how much *this* driver values an extra stop, which
  can be positive or negative.
- **Higher is better.** The score is never normalised to a 0–100 scale — the
  numbers are seconds, and a difference of 1.0 means one second of race time.

Candidates are ranked by this score, and the three plans are selected
structurally rather than as a straight top three (see below).

---

## `total_penalty`

### 1. Tyre wear

The largest term. For every lap of every stint:

```
(100 - performance) × tyre_loss_seconds_per_percent ÷ paceModifier
                   × driver_factor × severity_factor
```

- `performance` comes from the compound's `performanceCurve`, interpolated
  across the stint and scaled by `baseGrip` and tyre warm-up.
- `tyre_loss_seconds_per_percent` is per circuit (0.060–0.140 s).
- `paceModifier` comes from `weather.json`, because a wet lap loses more
  absolute time per percent of grip.
- `driver_factor` scales with the driver's tyre management against
  `NEUTRAL_RATING`.
- `severity_factor` rises with the circuit's energy demand, abrasiveness and
  tyre degradation, so drivers separate most on punishing circuits.

### 2. Traffic from extra stops

```
extra_stops × overtakingDifficulty × 1.4
```

A car that stops again rejoins behind cars it had already passed, and the cost
grows on circuits where passing is hard.

### 3. Race situation

```
(position - 1) × starting_position_penalty_seconds
+ stopDifficulty × 8
- safetyCarProbability × stops × sc_pit_saving_seconds
```

- Grid position costs time per slot on the way to the front.
- `oneStopDifficulty` / `twoStopDifficulty` / `threeStopDifficulty` express how
  much the circuit punishes each stop count.
- A safety car makes extra stops cheaper, so a higher probability rewards
  plans with more stops.

### 4. Pit lane

```
stops × (pitLaneLoss + team_delta)
```

`pitLaneLoss` is the circuit's pit entry-to-exit loss. `team_delta` is the
team's median pit lane loss against the field median, clamped to ±2 s, so a
slower pit crew pays a little more per stop. Both come from `tracks.json` and
`teams.json`.

---

## `driver_adjustment`

How many seconds this driver gains or gives up per extra stop:

| Term | Direction |
|---|---|
| `tyre_management` | weak managers gain more from fresh rubber |
| `aggression` | willingness to trade track position for pace |
| `consistency` | dislikes the extra risk of another stop |
| `qualifying` | defends track position when starting near the front |
| `overtaking`, `race_pace` | each extra stop costs less traffic on hard circuits |
| `wet_weather` | wet specialists extract more from fresh wet rubber |
| grid position | front-runners defend, back-markers trade places for tyres |

Every term is multiplied by the number of extra stops, so a one-stop plan is
decided by the tyre model alone. Ratings are measured against
`NEUTRAL_RATING` (8), not against zero.

---

## How the three plans are chosen

The engine does **not** simply take the top three scores. Each plan answers a
different race:

1. **Plan A** — the highest scoring strategy overall.
2. **Plan B** — the highest scoring strategy with a *different stop count*
   from Plan A, so it is the shape the race takes if the assumed conditions
   break. Falls back to the next best strategy if no such plan exists.
3. **Plan C** — the most aggressive remaining shape (most stops, then the most
   soft-tyre stints), broken by score.

Scores are not displayed, because the plans are presented as alternative race
scenarios rather than a ranked shortlist.
