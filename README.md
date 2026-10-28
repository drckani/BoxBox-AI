# 🏎️ BoxBox AI

An AI-powered Formula 1 race strategy simulator that models tyre degradation, pit stop strategy, race conditions, and driver characteristics to recommend the optimal race plan.

Instead of relying on fixed strategies, BoxBox AI simulates hundreds of possible tyre sequences, evaluates them using a custom scoring engine, and produces multiple race strategies together with an AI-generated race engineer briefing.

---

## Features

- 🏎️ 2026 Formula 1 driver database
- 👤 Custom driver creation with performance ratings
- 🌎 Multiple Formula 1 circuits
- ☀️ Dry and Wet race support
- 🛞 Weekend tyre compound allocation (C1–C5)
- 📉 Dynamic tyre degradation modelling
- 📊 Performance curve simulation for every stint
- ⛽ Intelligent pit stop window calculation
- 🧮 Strategy scoring engine
- 🤖 AI-generated race engineer briefing using Gemini
- 📋 Three complete strategy recommendations

  - Plan A (Optimal)
  - Plan B (Alternative)
  - Plan C (Aggressive)

---

## Strategy Engine

Every generated strategy is evaluated using multiple race factors including

- tyre degradation
- compound performance curves
- tyre warm-up
- driver tyre management
- race pace
- consistency
- aggression
- qualifying performance
- starting position
- pit lane time loss
- safety car probability
- track degradation
- track abrasiveness
- track temperature
- traffic penalties
- overtaking difficulty

The engine generates hundreds of legal tyre sequences before selecting the highest scoring strategies.

---

## AI Briefing

After simulation, Gemini generates a race engineer briefing explaining

- why the strategy was chosen
- expected strengths
- tyre usage
- pit windows
- risks
- comparison against alternative strategies

The briefing only uses the simulation output and does not invent race data.

---

## Project Structure

```
BoxBox-AI/

│
├── main.py
├── strategy_engine.py
├── gemini_engine.py
├── data_loader.py
│
├── json/
│   ├── drivers.json
│   ├── tracks.json
│   ├── teams.json
│   ├── compounds.json
│   └── weather.json
│
├── DATA_METHODOLOGY.md
├── SCORING.md
└── strategy_scoring.md
```

---

## Installation

Clone the repository

```bash
git clone https://github.com/drckani/BoxBox-AI.git

cd BoxBox-AI
```

Install dependencies

```bash
pip install -r requirements.txt
```

Create a `.env` file

```text
GEMINI_API_KEY=YOUR_API_KEY
```

---

## Important Setup

The project expects all dataset files to be inside a folder named:

```
json/
```

Your directory should look like:

```
BoxBox-AI/

main.py
strategy_engine.py
data_loader.py
gemini_engine.py

json/
    drivers.json
    tracks.json
    teams.json
    tracks.json
    compounds.json
    weather.json
```

GitHub sometimes doesn't preserve empty folders. If the `json` directory is missing after cloning, simply create a folder named `json` and place all provided JSON files inside it.

---

## Running

```bash
streamlit run main.py
```

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

- Full race simulation
- Safety Car and VSC events
- Live weather transitions
- Team-specific pit stop performance
- Fuel load simulation
- ERS deployment modelling
- DRS train simulation
- Undercut / Overcut prediction
- Monte Carlo race simulation
- Historical race validation
- Telemetry visualisation

---

## Disclaimer

BoxBox AI is an educational project built for software engineering, data modelling, and AI experimentation. It is not affiliated with Formula One, the FIA, Pirelli, or any Formula 1 team.

Driver ratings, tyre models, and strategy outputs are simplified predictive models and should not be interpreted as official race strategy.
