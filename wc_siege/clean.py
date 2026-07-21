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

import re

import numpy as np
import pandas as pd

from . import config

# The canonical schema every downstream step relies on. shots_faced / xg_faced come
# from the shooting table (the opponent's attacking output); they are NaN if the
# shooting pull hasn't been run yet, so downstream code treats them as optional.
TIDY_COLUMNS = ["season", "teams", "game_id", "stage", "round",
                "team", "opponent", "saves", "sota", "ga",
                "shots_faced", "xg_faced", "poss_conceded", "box_touches_conceded"]


def _canonical_game_id(df: pd.DataFrame) -> pd.Series:
    """date + alphabetically-sorted team pair -> IDENTICAL for both teams in a match.

    FBref writes each game from one team's perspective ("Algeria-Argentina" vs
    "Argentina-Algeria"), so its 'game' string differs between the two rows. This key
    collapses both rows of a match to one id, which is what lets us (a) take the
    besieged keeper per game and (b) join a team to its opponent's shooting.
    """
    pair = ["-".join(sorted([str(t), str(o)])) for t, o in zip(df["team"], df["opponent"])]
    return df["date"].astype(str) + " " + pd.Series(pair, index=df.index)


def _find_regex(df: pd.DataFrame, pattern: str) -> str | None:
    """First column matching `pattern`, ignoring per-90 / 'Per' variants."""
    rx = re.compile(pattern)
    hits = [c for c in df.columns
            if rx.search(str(c)) and "90" not in str(c) and "Per" not in str(c)]
    return hits[0] if hits else None


def _finals_shooting(season: str) -> pd.DataFrame | None:
    """Per (game_id, team) total shots + xG from the shooting table, finals only.

    Returns None if the shooting pull hasn't been run yet (pipeline still works with
    just the keeper data, with shots_faced/xg_faced left as NaN).
    """
    p = config.RAW_DIR / f"{season}_shooting.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    df = df[df["round"].isin(config.FINALS_ROUNDS)].copy()
    shots_col = _find_regex(df, config.SHOOTING_SHOTS_RE)
    xg_col = _find_regex(df, config.SHOOTING_XG_RE)
    return pd.DataFrame(
        {
            "game_id": _canonical_game_id(df),
            "team": df["team"],
            "shots": pd.to_numeric(df[shots_col], errors="coerce") if shots_col else np.nan,
            "xg": pd.to_numeric(df[xg_col], errors="coerce") if xg_col else np.nan,
        }
    )


def _finals_possession(season: str) -> pd.DataFrame | None:
    """Per (game_id, team) possession % + touches in the attacking penalty area.

    Returns None if the possession pull hasn't been run yet.
    """
    p = config.RAW_DIR / f"{season}_possession.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    df = df[df["round"].isin(config.FINALS_ROUNDS)].copy()
    poss_col = _find_regex(df, config.POSSESSION_POSS_RE)
    box_col = _find_regex(df, config.POSSESSION_BOX_RE)
    return pd.DataFrame(
        {
            "game_id": _canonical_game_id(df),
            "team": df["team"],
            "poss": pd.to_numeric(df[poss_col], errors="coerce") if poss_col else np.nan,
            "box_touches": pd.to_numeric(df[box_col], errors="coerce") if box_col else np.nan,
        }
    )


def _tidy_one_season(season: str) -> pd.DataFrame:
    raw_path = config.RAW_DIR / f"{season}_keeper.csv"
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

    tidy = pd.DataFrame(
        {
            "season": season,
            "teams": config.SEASONS[season]["teams"],
            "game_id": _canonical_game_id(df),
            "stage": df["stage"].values,
            "round": df["round"].values,
            "team": df["team"],
            "opponent": df["opponent"],
            "saves": pd.to_numeric(df[config.KEEPER_METRICS["saves"]], errors="coerce"),
            "sota": pd.to_numeric(df[config.KEEPER_METRICS["sota"]], errors="coerce"),
            "ga": pd.to_numeric(df[config.KEEPER_METRICS["ga"]], errors="coerce"),
        }
    )

    # Pressure a keeper's side ABSORBED = the OPPONENT's attacking output. Join each
    # team to its opponent's shooting row (same game_id) to get shots-faced / xG-faced.
    shoot = _finals_shooting(season)
    if shoot is not None:
        opp = shoot.rename(columns={"team": "opponent", "shots": "shots_faced", "xg": "xg_faced"})
        tidy = tidy.merge(opp, on=["game_id", "opponent"], how="left")
    else:
        tidy["shots_faced"] = np.nan
        tidy["xg_faced"] = np.nan

    # Territorial pressure conceded = the OPPONENT's possession and box touches. This is
    # the "pinned in its own box" dimension the Reddit critics said saves entirely miss.
    poss = _finals_possession(season)
    if poss is not None:
        opp_p = poss.rename(columns={
            "team": "opponent", "poss": "poss_conceded", "box_touches": "box_touches_conceded",
        })
        tidy = tidy.merge(opp_p, on=["game_id", "opponent"], how="left")
    else:
        tidy["poss_conceded"] = np.nan
        tidy["box_touches_conceded"] = np.nan

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
