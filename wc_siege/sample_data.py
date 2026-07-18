"""
sample_data.py -- SYNTHETIC placeholder data (NOT REAL).
=======================================================

This exists for ONE reason: so you can run the whole pipeline (clean -> analyze ->
model -> viz) and see the flow end-to-end BEFORE the real FBref pull lands. Every
number it produces is made up.

It writes to data/processed/team_games_SAMPLE.csv (a separate file), so it can
never be mistaken for or overwrite the real data/processed/team_games.csv.

The generator does encode the hypothesis under test (bigger, more-lopsided field
-> more saves for the battered team) so the demo charts look believable -- but
that is exactly why you must NOT trust its conclusions. The real data decides.

    python -m wc_siege.sample_data
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

RNG = np.random.default_rng(2026)


def _simulate_group_stage(season: str) -> pd.DataFrame:
    """Make up a plausible group stage for one edition."""
    info = config.SEASONS[season]
    n_teams = info["teams"]

    # 2026 adds teams by widening the strength spread downward (more minnows).
    spread = 1.0 if n_teams == 32 else 1.35
    strength = RNG.normal(0.0, spread, size=n_teams)

    # Build the right number of group games by randomly pairing teams.
    n_games = info["group_games"]
    rows = []
    for g in range(n_games):
        a, b = RNG.choice(n_teams, size=2, replace=False)
        gap = strength[a] - strength[b]  # >0 => team a stronger

        # The weaker team gets peppered: shots-on-target-against rises with the gap.
        for team, opp, adv in ((a, b, gap), (b, a, -gap)):
            base = 3.5 + max(0.0, -adv) * 2.6          # facing a stronger side -> more SoT
            sota = RNG.poisson(base)
            ga = min(sota, RNG.binomial(sota, 0.28))    # ~28% of SoT become goals
            saves = sota - ga
            rows.append(
                {
                    "season": season,
                    "teams": n_teams,
                    "game_id": f"{season}-G{g:02d}",
                    "team": f"T{team:02d}",
                    "opponent": f"T{opp:02d}",
                    "saves": int(saves),
                    "sota": int(sota),
                    "ga": int(ga),
                }
            )
    return pd.DataFrame(rows)


def generate() -> pd.DataFrame:
    frames = [_simulate_group_stage(s) for s in config.SEASONS]
    df = pd.concat(frames, ignore_index=True)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = config.PROCESSED_DIR / "team_games_SAMPLE.csv"
    df.to_csv(out, index=False)
    print(f"[sample_data] wrote SYNTHETIC {out.relative_to(config.ROOT)} ({len(df)} rows)")
    print("[sample_data] NOTE: these numbers are fake -- for wiring up the pipeline only.")
    return df


if __name__ == "__main__":
    generate()
