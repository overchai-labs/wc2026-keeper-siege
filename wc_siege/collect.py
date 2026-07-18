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


def _fetch_one_season(season: str) -> pd.DataFrame:
    """Pull team-level goalkeeper match logs for a single World Cup edition.

    Returns a raw (wide, multi-indexed) DataFrame straight from FBref. We do NOT
    clean it here -- collection and cleaning are separate steps on purpose, so a
    change to one never silently breaks the other.
    """
    # Imported lazily so that `--help` and the sample-data path don't require
    # soccerdata to be installed.
    import soccerdata as sd

    print(f"[collect] World Cup {season}: contacting FBref via soccerdata ...")
    # soccerdata >=1.9.0 launches an undetected Chrome (Selenium) here to clear
    # Cloudflare. The FIRST call may pause ~30-60s while it starts the browser and
    # fetches a chromedriver -- that is expected, let it run. If you still get a
    # 403 loop, try setting the env var KEEPER_HEADFUL=1 (opens a visible window,
    # which Cloudflare trusts more), which we honour below.
    kwargs = {}
    if os.environ.get("KEEPER_HEADFUL") == "1":
        kwargs["headless"] = False
    fbref = sd.FBref(leagues=config.FBREF_LEAGUE, seasons=season, **kwargs)

    # `read_team_match_stats(stat_type="keeper")` returns ONE ROW PER TEAM PER
    # GAME with the goalkeeping columns (Saves, SoTA, PSxG, GA, ...). That is
    # exactly the granularity we want -- no per-player joining needed.
    gk = fbref.read_team_match_stats(stat_type="keeper")
    print(f"[collect] World Cup {season}: got {len(gk)} team-game rows.")
    return gk


def collect(seasons: list[str] | None = None) -> None:
    """Fetch each requested season and save it verbatim to data/raw/<season>.csv."""
    seasons = seasons or list(config.SEASONS)
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)

    for season in seasons:
        try:
            gk = _fetch_one_season(season)
        except Exception as exc:  # noqa: BLE001 -- we want a friendly message
            print(
                f"[collect] FAILED for {season}: {exc}\n"
                "          If this is a 403, you are almost certainly on a blocked\n"
                "          (cloud/datacenter) IP -- run this from your home machine.",
                file=sys.stderr,
            )
            continue

        out = config.RAW_DIR / f"{season}.csv"
        # Flatten FBref's multi-level column headers so the CSV is readable.
        gk.to_csv(out)
        print(f"[collect] wrote {out.relative_to(config.ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull World Cup GK match logs from FBref.")
    parser.add_argument(
        "--season",
        action="append",
        choices=list(config.SEASONS),
        help="Limit to one season (repeatable). Default: all three.",
    )
    args = parser.parse_args()
    collect(args.season)


if __name__ == "__main__":
    main()
