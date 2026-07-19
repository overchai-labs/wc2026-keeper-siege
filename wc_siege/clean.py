"""
Step 2 -- CLEAN
===============

Turn the raw FBref pulls (data/raw/<season>.csv) into ONE tidy table:

    one row = one team, in one FINALS group-stage game
    columns = season, teams, game_id, team, opponent, saves, sota, ga

Two jobs happen here, and only here:
  1. FILTER to the finals (group stage + knockouts). The raw pull is the whole 2026
     campaign (qualifiers + friendlies + finals); we keep only the finals rounds and
     tag each row 'group' or 'knockout' in a `stage` column.
  2. SELECT + rename the goalkeeping columns collect.py flattened
     (Performance_Saves -> saves, etc.).

Keeping this messy reshape isolated means analyze.py never has to know what FBref's
HTML looked like.
"""
from __future__ import annotations

import pandas as pd

from . import config

# The canonical schema every downstream step relies on.
TIDY_COLUMNS = ["season", "teams", "game_id", "stage", "round",
                "team", "opponent", "saves", "sota", "ga"]


def _tidy_one_season(season: str) -> pd.DataFrame:
    raw_path = config.RAW_DIR / f"{season}.csv"
    if not raw_path.exists():
        raise FileNotFoundError(
            f"{raw_path} not found. Run `python -m wc_siege.collect --season {season}` "
            "on your home machine first."
        )

    df = pd.read_csv(raw_path)

    # 1) Finals only (group stage + knockouts); tag the stage.
    if "round" not in df.columns:
        raise KeyError(f"[clean] {season}: no 'round' column. Columns: {list(df.columns)}")
    df = df[df["round"].isin(config.FINALS_ROUNDS)].copy()
    if df.empty:
        rounds = sorted(pd.read_csv(raw_path)["round"].dropna().unique())
        raise SystemExit(
            f"[clean] {season}: no finals rounds found. Round values present: {rounds}"
        )
    df["stage"] = df["round"].where(df["round"] != config.GROUP_STAGE_ROUND, "group")
    df["stage"] = df["stage"].where(df["stage"] == "group", "knockout")

    # 2) Select the goalkeeping columns (fail loudly if a name drifted).
    missing = [c for c in config.KEEPER_METRICS.values() if c not in df.columns]
    if missing:
        raise KeyError(
            f"[clean] {season}: missing columns {missing}. Available: {list(df.columns)}"
        )

    # A canonical game_id that is IDENTICAL for both teams in a match. FBref writes
    # the game from each team's perspective ("Algeria-Argentina" vs "Argentina-Algeria"),
    # so we can't use its 'game' string -- the two keepers would never pair up. Instead:
    # date + the alphabetically-sorted pair of teams. Both rows of a match collapse to
    # one key, which is what lets us take the besieged (max-saves) keeper per game.
    pair = [
        "-".join(sorted([str(t), str(o)]))
        for t, o in zip(df["team"], df["opponent"])
    ]
    game_id = df["date"].astype(str) + " " + pd.Series(pair, index=df.index)

    tidy = pd.DataFrame(
        {
            "season": season,
            "teams": config.SEASONS[season]["teams"],
            "game_id": game_id,
            "stage": df["stage"].values,
            "round": df["round"].values,
            "team": df["team"],
            "opponent": df["opponent"],
            "saves": pd.to_numeric(df[config.KEEPER_METRICS["saves"]], errors="coerce"),
            "sota": pd.to_numeric(df[config.KEEPER_METRICS["sota"]], errors="coerce"),
            "ga": pd.to_numeric(df[config.KEEPER_METRICS["ga"]], errors="coerce"),
        }
    )
    return tidy.dropna(subset=["saves"]).reset_index(drop=True)


def clean(seasons: list[str] | None = None) -> pd.DataFrame:
    """Clean every available season and write the combined tidy table."""
    seasons = seasons or list(config.SEASONS)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    frames = []
    for season in seasons:
        try:
            tidy = _tidy_one_season(season)
            frames.append(tidy)
            n_games = tidy["game_id"].nunique()
            print(f"[clean] {season}: ok -- {len(tidy)} team-games across {n_games} games")
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
