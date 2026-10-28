# BoxBox AI - Strategy Scoring

## Total Score

Every generated strategy receives a score out of **100**.

The highest scoring strategy becomes **Plan A**.

The second highest becomes **Plan B**.

The highest scoring aggressive strategy becomes **Plan C**.

---

# Score Breakdown

| Category | Weight |
|----------|--------|
| Tyre Suitability | 35 |
| Track Characteristics | 25 |
| Driver Profile | 15 |
| Race Situation | 15 |
| Pit Strategy | 10 |

Total = **100**

---

# 1. Tyre Suitability (35)

Factors:

- Grip
- Durability
- Warm-up
- Wear Rate
- Ideal Track Severity

Uses:

- compounds.json
- tracks.json

---

# 2. Track Characteristics (25)

Factors:

- Track Temperature
- Energy Demand
- Abrasiveness
- Tyre Degradation

Uses:

- tracks.json

---

# 3. Driver Profile (15)

Factors:

- Tyre Management
- Race Pace
- Consistency
- Aggression

Uses:

- drivers.json

---

# 4. Race Situation (15)

Factors:

- Starting Position
- Overtaking Difficulty
- Weather
- Safety Car Probability
- VSC Probability

Uses:

- user input
- weather.json
- tracks.json

---

# 5. Pit Strategy (10)

Factors:

- Pit Lane Loss
- Team Pit Stop Performance

Uses:

- teams.json
- tracks.json

---

# Strategy Selection

1. Generate all legal strategies.
2. Score every strategy.
3. Sort by score.
4. Highest score = Plan A.
5. Second highest = Plan B.
6. Highest scoring aggressive strategy = Plan C.

---

# Future Improvements

- Fuel load modelling
- Track evolution
- Driver confidence
- Dynamic Safety Car simulation
- Multiple weather phases