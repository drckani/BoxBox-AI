# 🏎️ BoxBox AI

An AI-assisted Formula 1 race strategy simulator that models tyre degradation,
pit stop strategy, race conditions and driver characteristics to recommend a
race plan.

Instead of applying a fixed strategy, BoxBox AI enumerates every legal tyre
sequence, allocates stint lengths with a dynamic program, scores each plan in
seconds of race time, and returns three plans together with an AI-written race
engineer briefing.

Strategy selection is fully deterministic. The language model never chooses a
strategy — it only explains plans the engine has already chosen.

---

## Features

- 🏎️ 2026 Formula 1 driver database
- 👤 Custom driver creation with performance ratings
- 🌎 24 Formula 1 circuits
- ☀️ Dry and wet race support
- 🛞 Weekend tyre compound allocation (C1–C5)
- 📉 Dynamic tyre degradation modelling
- 📊 Performance curve simulation for every stint
- ⛽ Dynamic-programming stint allocation with realistic pit windows
- 🧮 Transparent, seconds-based strategy scoring
- 🤖 AI race engineer briefing via Gemini
- 📋 Three complete strategy recommendations

  - Plan A — the fastest plan in clean air
  - Plan B — the same race with a different stop count
  - Plan C — the most aggressive shape available

---

## How it works

1. **Tyre life** — each compound's base life is reduced by circuit severity,
   track temperature and the driver's tyre management, then divided by the
   weather wear rate.
2. **Stint allocation** — a memoised dynamic program splits the race distance
   across the stints to maximise summed tyre performance, with a minimum stint
   length so it never suggests pitting again after a few laps.
3. **Scoring** — tyre wear, traffic, pit lane time, stop difficulty, safety car
   probability, grid position and driver characteristics are combined into a
   single penalty in seconds. See [SCORING.md](SCORING.md).
4. **Selection** — plans are chosen structurally, not as a plain top three: the
   best plan, the best plan with a different stop count, and the most
   aggressive available shape.
5. **Explanation** — Gemini receives the finished plans and their roles, and is
   instructed not to re-rank or invent anything.

---

## Project Structure

```
BoxBox-AI/
├── main.py                  # Streamlit interface
├── strategy_engine.py       # Tyre model, DP stint allocation, scoring
├── gemini_engine.py         # Gemini briefing generation and fallbacks
├── data_loader.py           # JSON dataset access
│
├── drivers.json             # 2026 driver profiles and ratings
├── tracks.json              # 24 circuits and their characteristics
├── teams.json               # Team pit lane performance
├── compounds.json           # C1–C5, Intermediate and Wet compounds
├── weather.json             # Dry and wet conditions
│
├── tests/
│   └── test_strategy_engine.py
│
├── SCORING.md               # How every strategy is scored
├── DATA_METHODOLOGY.md      # Datasets, derived fields and rating scale
├── requirements.txt
├── .env.example
├── LICENSE
└── README.md
```

The datasets sit next to `data_loader.py`, and their path is resolved from that
file, so the app runs from any working directory.

---

## Installation

Clone the repository and install the dependencies:

```bash
git clone https://github.com/drckani/BoxBox-AI.git
cd BoxBox-AI
pip install -r requirements.txt
```

---

## Configuration

Strategy generation needs no configuration. Only the AI briefings need a
Gemini API key.

```bash
cp .env.example .env
```

Then put your key in `.env`:

```text
GEMINI_API_KEY=your-key-here
```

Create a key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
The key is also read from `GEMINI_API_KEY` in the environment or from
`.streamlit/secrets.toml`. A real environment variable takes precedence over
`.env`.

Without a key the app still generates strategies and simply skips the AI
overviews, so it is usable out of the box.

`.env` is ignored by git — never commit it.

---

## Running

```bash
streamlit run main.py
```

---

## Tests

The engine tests have no third-party dependencies:

```bash
python3 tests/test_strategy_engine.py
```

or, with pytest installed:

```bash
pytest tests/
```

They cover the model invariants the documentation claims: softer compounds have
shorter life, better tyre management lengthens it, extra stops cost more pit
time, a slower pit crew costs more, a safety car reduces the cost of stopping,
grid position changes the recommendation, and wet races only use wet compounds.

---

## Design Decisions

- **The engine decides, the model explains.** Gemini receives plans that are
  already chosen and is told not to propose, rank or alter anything, so the
  output cannot drift from the simulation.
- **Scores are seconds, not points.** Every heuristic is expressed as time
  lost or gained, which makes the weights interpretable and comparable.
- **Model unavailability is not fatal.** A retired or overloaded Gemini model
  is skipped for the next candidate, and a rejected key falls through to the
  next configured key, so a single stale model name does not break the app.
- **Data problems fail loudly in tests.** Derived circuit fields are asserted
  to exist on every track, so the engine cannot silently fall back to a default.

---

## Limitations

- The model is deterministic and rule-based, not a trained predictor.
- Safety cars, retirements and weather transitions are modelled as
  probabilities and penalties, not simulated as discrete events.
- Ratings are simplified 1–10 engineering judgements, not measured telemetry.
- Tyre life and grip curves are approximations calibrated by hand.

---

## Technologies

- Python
- Streamlit
- Google Gemini API
- JSON
- Dynamic Programming
- Performance Curve Modelling
- Predictive Tyre Simulation

---

## Future Improvements

- Full lap-by-lap race simulation
- Discrete Safety Car and VSC events
- Live weather transitions
- Fuel load simulation
- ERS deployment modelling
- DRS train simulation
- Undercut / overcut prediction
- Monte Carlo race simulation
- Historical race validation
- Telemetry visualisation

---

## License

MIT — see [LICENSE](LICENSE).

---

## Disclaimer

BoxBox AI is an educational project built for software engineering, data
modelling and AI experimentation. It is not affiliated with Formula One, the
FIA, Pirelli, or any Formula 1 team.

Driver ratings, tyre models and strategy outputs are simplified predictive
models and should not be interpreted as official race strategy.
