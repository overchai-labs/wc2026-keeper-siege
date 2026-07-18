"""
Step 2 -- CLEAN
===============

Turn the raw FBref pulls (data/raw/<season>.csv) into ONE tidy table:

    one row = one team, in one group-stage game
    columns = season, teams, game_id, team, opponent, saves, sota, psxg, ga

Why a separate step: FBref returns wide, multi-header tables that differ slightly
year to year. Isolating the messy reshape here means analyze.py / model.py never
have to know what FBref's HTML looked like.

NOTE: the exact FBref column names can drift between editions. This step looks up
columns by fuzzy name (config.KEEPER_METRICS) and will tell you loudly if one is
missing, rather than silently producing garbage. After your first real pull, if a
column isn't found, print the raw CSV header and adjust config.KEEPER_METRICS.
"""
from __future__ import annotations

import pandas as pd

from . import config

# The canonical schema every downstream step relies on.
TIDY_COLUMNS = ["season", "teams", "game_id", "team", "opponent", "saves", "sota", "psxg", "ga"]


def _find_col(df: pd.DataFrame, wanted: str) -> str | None:
    """Find a column whose name contains `wanted` (case-insensitive).

    FBref sometimes flattens multi-headers to e.g. 'Performance_Saves' -- matching
    on a substring keeps us robust to that without hard-coding every variant.
    """
    wanted_low = wanted.lower()
    for col in df.columns:
        if wanted_low in str(col).lower():
            return col
    return None


def _tidy_one_season(season: str) -> pd.DataFrame:
    raw_path = config.RAW_DIR / f"{season}.csv"
    if not raw_path.exists():
        raise FileNotFoundError(
            f"{raw_path} not found. Run `python -m wc_siege.collect --season {season}` "
            "on your home machine first."
        )

    df = pd.read_csv(raw_path)

    # Locate the goalkeeping metric columns by fuzzy name.
    resolved = {}
    for key, fbref_name in config.KEEPER_METRICS.items():
        col = _find_col(df, fbref_name)
        if col is None:
            raise KeyError(
                f"[clean] {season}: couldn't find a column for '{fbref_name}'. "
                f"Available columns: {list(df.columns)}"
            )
        resolved[key] = col

    # Identity columns: team, opponent, and a per-game id. soccerdata usually
    # exposes 'team', 'opponent', and a 'game' string like '2026-06-13 Spain-Cape Verde'.
    team_col = _find_col(df, "team") or "team"
    opp_col = _find_col(df, "opponent") or "opponent"
    game_col = _find_col(df, "game") or _find_col(df, "date")

    tidy = pd.DataFrame(
        {
            "season": season,
            "teams": config.SEASONS[season]["teams"],
            "game_id": df[game_col] if game_col else range(len(df)),
            "team": df[team_col],
            "opponent": df[opp_col],
            "saves": pd.to_numeric(df[resolved["saves"]], errors="coerce"),
            "sota": pd.to_numeric(df[resolved["sota"]], errors="coerce"),
            "psxg": pd.to_numeric(df[resolved["psxg"]], errors="coerce"),
            "ga": pd.to_numeric(df[resolved["ga"]], errors="coerce"),
        }
    )

    # Group stage only: knockout games confound the comparison (see README).
    # soccerdata tags round/stage; if present, filter to the group phase.
    round_col = _find_col(df, "round") or _find_col(df, "stage")
    if round_col is not None:
        mask = df[round_col].astype(str).str.contains("group", case=False, na=False)
        tidy = tidy[mask.values]

    return tidy.dropna(subset=["saves"]).reset_index(drop=True)


def clean(seasons: list[str] | None = None) -> pd.DataFrame:
    """Clean every available season and write the combined tidy table."""
    seasons = seasons or list(config.SEASONS)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    frames = []
    for season in seasons:
        try:
            frames.append(_tidy_one_season(season))
            print(f"[clean] {season}: ok")
        except FileNotFoundError as exc:
            print(f"[clean] skipping {season}: {exc}")

    if not frames:
        raise SystemExit("[clean] no raw data found. Run the collector first.")

    combined = pd.concat(frames, ignore_index=True)[TIDY_COLUMNS]
    out = config.PROCESSED_DIR / "team_games.csv"
    combined.to_csv(out, index=False)
    print(f"[clean] wrote {out.relative_to(config.ROOT)} ({len(combined)} team-game rows)")
    return combined


if __name__ == "__main__":
    clean()
