"""
Step 1 -- COLLECT
=================

Goal: get, for every World Cup group-stage game in 2018, 2022 and 2026, how many
saves each team's goalkeeper made (plus shots-on-target-against and post-shot xG).

Source: FBref (StatsBomb data), via the `soccerdata` library, which rate-limits
politely and caches raw pages locally so you don't hammer the site.

IMPORTANT ABOUT WHERE THIS RUNS
-------------------------------
FBref blocks datacenter/cloud IPs (returns 403). Run this on your own machine /
home internet, where FBref serves pages normally. Once it succeeds it writes CSVs
into data/raw/, and those get committed -- so every later step (and anyone who
clones the repo) works WITHOUT re-scraping. That is the whole point of committing
the raw pull: reproducibility that doesn't depend on FBref being reachable.

Run it with:
    python -m wc_siege.collect            # pull all three tournaments
    python -m wc_siege.collect --season 2026
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

from . import config


def _fetch_one(season: str, stat_type: str) -> pd.DataFrame:
    """Pull one FBref team-match table (e.g. 'keeper' or 'shooting') for a season.

    Returns a raw (wide, multi-indexed) DataFrame straight from FBref, flattened. We
    do NOT clean it here -- collection and cleaning are separate steps on purpose, so a
    change to one never silently breaks the other. The pull includes the whole campaign
    (qualifiers + friendlies + finals); clean.py filters to the finals.
    """
    # Imported lazily so that `--help` and the sample-data path don't require
    # soccerdata to be installed.
    import soccerdata as sd

    print(f"[collect] World Cup {season} / {stat_type}: contacting FBref via soccerdata ...")
    # soccerdata >=1.9.0 launches an undetected Chrome (Selenium) here to clear
    # Cloudflare. The FIRST call may pause ~30-60s while it starts the browser and
    # fetches a chromedriver -- that is expected, let it run. If you still get a
    # 403 loop, try setting the env var KEEPER_HEADFUL=1 (opens a visible window,
    # which Cloudflare trusts more), which we honour below.
    kwargs = {}
    if os.environ.get("KEEPER_HEADFUL") == "1":
        kwargs["headless"] = False
    fbref = sd.FBref(leagues=config.FBREF_LEAGUE, seasons=season, **kwargs)

    df = _flatten(fbref.read_team_match_stats(stat_type=stat_type))
    print(f"[collect] World Cup {season} / {stat_type}: got {len(df)} team-game rows.")
    return df


def _flatten(gk: pd.DataFrame) -> pd.DataFrame:
    """Flatten FBref's MultiIndex index+columns into a plain, readable table.

    FBref groups goalkeeping stats under headers like ('Performance', 'Saves').
    We move the index (league/season/team/game) into columns and join each column's
    non-empty header levels with '_', so ('Performance','Saves') -> 'Performance_Saves'
    while ('date','') -> 'date'. This is what makes the saved CSV usable downstream.
    """
    gk = gk.reset_index()
    flat = []
    for col in gk.columns:
        if isinstance(col, tuple):
            parts = [
                str(p) for p in col
                if p not in ("", None) and str(p) != "nan" and not str(p).startswith("Unnamed")
            ]
            flat.append("_".join(parts) if parts else "index")
        else:
            flat.append(str(col))
    gk.columns = flat
    return gk


def collect(seasons: list[str] | None = None, stats: list[str] | None = None) -> None:
    """Fetch each (season, stat_type) and save to data/raw/<season>_<stat>.csv."""
    seasons = seasons or list(config.SEASONS)
    stats = stats or list(config.STAT_TYPES)
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)

    for season in seasons:
        for stat in stats:
            out = config.RAW_DIR / f"{season}_{stat}.csv"
            if out.exists() and os.environ.get("KEEPER_FORCE") != "1":
                print(f"[collect] {out.relative_to(config.ROOT)} exists -- skipping "
                      "(set KEEPER_FORCE=1 to refetch).")
                continue
            try:
                df = _fetch_one(season, stat)
            except Exception as exc:  # noqa: BLE001 -- we want a friendly message
                print(
                    f"[collect] FAILED for {season}/{stat}: {exc}\n"
                    "          If this is a 403, you are almost certainly on a blocked\n"
                    "          (cloud/datacenter) IP -- run this from your home machine.",
                    file=sys.stderr,
                )
                continue
            df.to_csv(out, index=False)  # already flattened + index reset in _flatten
            print(f"[collect] wrote {out.relative_to(config.ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull World Cup team-match tables from FBref.")
    parser.add_argument(
        "--season",
        action="append",
        choices=list(config.SEASONS),
        help="Limit to one season (repeatable). Default: all three.",
    )
    parser.add_argument(
        "--stat",
        action="append",
        choices=list(config.STAT_TYPES),
        help=f"Limit to one stat table (repeatable). Default: all of {config.STAT_TYPES}.",
    )
    args = parser.parse_args()
    collect(args.season, args.stat)


if __name__ == "__main__":
    main()
