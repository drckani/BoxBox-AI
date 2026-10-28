import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "json"

print("USING DATA LOADER:", __file__)
print("DATA_DIR =", DATA_DIR)
print("Exists =", DATA_DIR.exists())
def load_json(filename):
    with (DATA_DIR / filename).open("r", encoding="utf-8") as file:
        return json.load(file)


# -----------------------------
# LOAD ALL DATASETS
# -----------------------------

def get_tracks():
    return load_json("tracks.json")


def get_drivers():
    return load_json("drivers.json")["drivers"]


def get_teams():
    return load_json("teams.json")


def get_compounds():
    return load_json("compounds.json")


def get_weather():
    return load_json("weather.json")


# -----------------------------
# SINGLE OBJECT HELPERS
# -----------------------------

def get_track(track_id):
    tracks = get_tracks()
    return next(
        (track for track in tracks if track["id"] == track_id),
        None,
    )


def get_driver(driver_id):
    drivers = get_drivers()
    return next(
        (driver for driver in drivers if driver["id"] == driver_id),
        None,
    )


def get_team(team_id):
    teams = get_teams()
    return next(
        (team for team in teams if team["id"] == team_id),
        None,
    )


def get_compound(compound_id):
    compounds = get_compounds()
    return next(
        (compound for compound in compounds if compound["id"] == compound_id),
        None,
    )


def get_weather_type(weather_name):
    weather = get_weather()
    return next(
        (
            w
            for w in weather
            if w["name"].lower() == weather_name.lower()
        ),
        None,
    )