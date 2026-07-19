"""
Step 4 (Part 2) -- MODEL
========================

The analyze.py comparison (2018/2022 vs 2026) is CONFOUNDED: 2026 differs from the
past both because the field grew (32 -> 48 teams) AND because it's a later era
(tactics, shot volume). We cannot tell those apart from the real comparison alone.

This model isolates the EXPANSION effect by holding "football" constant:

  1. team_strengths()   -- rate each team from real goals (scored - conceded / game)
  2. fit_pressure_law() -- fit ONE law: bigger strength gap -> more shots on target
                           faced by the weaker keeper (a Poisson rate in |gap|)
  3. validate()         -- feed the law 2026's real matchups; does it reproduce the
                           observed 2026 siege distribution? (if not, don't trust it)
  4. counterfactual()   -- run a 32-team field and a 48-team field through the SAME
                           law, changing ONLY the spread of team strengths. The gap
                           in siege frequency is the pure effect of expansion.

Honest limitations (state them, don't hide them):
  * Strengths come from only 3 group games/team -- noisy ratings.
  * We model the besieged keeper's shots-on-target as Poisson(rate(|gap|)); the max of
    two keepers isn't literally Poisson, so this is a phenomenological fit, not physics.
  * The 32- vs 48-team strength POOLS still carry some era signal; we mean-center each
    pool so only the SPREAD (which is what expansion changes) drives the counterfactual.

Run it:
    python -m wc_siege.model
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import ks_2samp

from . import config
from .analyze import load_team_games

RNG = np.random.default_rng(2026)
SIEGE = 8  # shots-on-target threshold used only to report a headline count


# --------------------------------------------------------------------------
# 1. Team strengths (from goals, to avoid circularity with the shot outcome)
# --------------------------------------------------------------------------
def team_strengths(tidy: pd.DataFrame) -> pd.DataFrame:
    """Rate each team by average goal difference across its group games.

    We deliberately rate on GOALS, while the pressure law predicts SHOTS -- so the
    rating isn't built from the very quantity we then model (less circular).
    Goals scored by a team = goals the opponent conceded (opponent's `ga`).
    """
    opp = tidy[["game_id", "team", "ga"]].rename(columns={"team": "opponent", "ga": "gf"})
    g = tidy.merge(opp, on=["game_id", "opponent"], how="left")
    g["gd"] = g["gf"] - g["ga"]
    s = g.groupby(["season", "team"], as_index=False)["gd"].mean().rename(columns={"gd": "gd_per_game"})
    # Standardise across all teams so "strength" is in comparable units.
    s["strength"] = (s["gd_per_game"] - s["gd_per_game"].mean()) / s["gd_per_game"].std()
    return s


def _games_with_gap(tidy: pd.DataFrame, strengths: pd.DataFrame) -> pd.DataFrame:
    """One row per game: the besieged keeper's SoTA and the |strength gap|."""
    m = tidy.merge(strengths[["season", "team", "strength"]], on=["season", "team"])
    agg = m.groupby(["season", "teams", "game_id"]).agg(
        max_sota=("sota", "max"),
        s_lo=("strength", "min"),
        s_hi=("strength", "max"),
    ).reset_index()
    agg["abs_gap"] = agg["s_hi"] - agg["s_lo"]
    return agg


# --------------------------------------------------------------------------
# 2. The pressure law:  E[besieged SoTA] = exp(b0 + b1 * |gap|)
# --------------------------------------------------------------------------
def fit_pressure_law(games: pd.DataFrame) -> tuple[float, float]:
    """Poisson regression of besieged-keeper SoTA on the absolute strength gap.

    b1 > 0 means: the more mismatched the game, the more shots the weaker keeper faces.
    That is the mechanism the whole "expansion -> more sieges" idea rests on, and here
    we let the real data say whether it's true and how strong it is.
    """
    x = games["abs_gap"].to_numpy(float)
    y = games["max_sota"].to_numpy(float)

    def neg_log_lik(b: np.ndarray) -> float:
        rate = np.exp(b[0] + b[1] * x)
        return float(np.sum(rate - y * np.log(rate)))  # Poisson NLL (drop constant)

    res = minimize(neg_log_lik, x0=[np.log(y.mean()), 0.0], method="BFGS")
    return float(res.x[0]), float(res.x[1])


def rate(law: tuple[float, float], abs_gap: np.ndarray) -> np.ndarray:
    b0, b1 = law
    return np.exp(b0 + b1 * np.asarray(abs_gap, float))


# --------------------------------------------------------------------------
# 3. Validate the law against the REAL 2026 distribution
# --------------------------------------------------------------------------
def validate(law: tuple[float, float], games: pd.DataFrame, n_rep: int = 2000) -> dict:
    """Does the fitted law, fed 2026's real matchups, reproduce real 2026 sieges?"""
    g26 = games[games["teams"] == 48]
    r = rate(law, g26["abs_gap"].to_numpy())
    actual = g26["max_sota"].to_numpy()

    sims = RNG.poisson(r, size=(n_rep, len(r)))            # simulate each real game many times
    pred_p8 = (sims >= SIEGE).mean(axis=1)                 # predicted P(SoTA>=8) per replicate
    lo, hi = np.percentile(pred_p8, [2.5, 97.5])

    ks = ks_2samp(sims.reshape(-1), actual)                # shape check: sim vs actual
    return {
        "actual_P(>=8)": round((actual >= SIEGE).mean(), 3),
        "predicted_P(>=8)": round(pred_p8.mean(), 3),
        "predicted_95CI": (round(lo, 3), round(hi, 3)),
        "ks_p_sim_vs_actual": round(float(ks.pvalue), 3),  # high p => distributions agree
    }


# --------------------------------------------------------------------------
# 4. Counterfactual: 32-team vs 48-team field, SAME law
# --------------------------------------------------------------------------
def _simulate_format(pool: np.ndarray, n_groups: int, law, n_sims: int) -> dict:
    """Monte-Carlo a whole group stage for a field drawn from `pool`.

    4 teams per group, full round-robin = 6 games/group. So 8 groups -> 48 games
    (32-team format) and 12 groups -> 72 games (48-team format), matching reality.
    """
    per_game_siege = []
    per_tourn_siege = []
    for _ in range(n_sims):
        total = 0
        n_games = 0
        for _g in range(n_groups):
            grp = RNG.choice(pool, size=4, replace=True)          # 4 teams into a group
            for i in range(4):
                for j in range(i + 1, 4):                          # the 6 group games
                    gap = abs(grp[i] - grp[j])
                    sota = RNG.poisson(rate(law, gap))
                    total += int(sota >= SIEGE)
                    n_games += 1
        per_tourn_siege.append(total)
        per_game_siege.append(total / n_games)
    return {
        "exp_sieges_per_tournament": round(float(np.mean(per_tourn_siege)), 2),
        "per_game_siege_prob": round(float(np.mean(per_game_siege)), 4),
    }


def counterfactual(strengths: pd.DataFrame, law, n_sims: int = 4000) -> dict:
    """Isolate expansion: same law, only the strength SPREAD differs between formats."""
    # Mean-center each pool so the OVERALL level (an era proxy) is removed and only the
    # spread -- which is what adding weaker teams changes -- drives the difference.
    # season may load as int or str depending on the CSV round-trip; compare as str.
    season = strengths["season"].astype(str)
    pool32 = strengths.loc[season.isin(["2018", "2022"]), "strength"].to_numpy()
    pool48 = strengths.loc[season == "2026", "strength"].to_numpy()
    pool32 = pool32 - pool32.mean()
    pool48 = pool48 - pool48.mean()

    res32 = _simulate_format(pool32, n_groups=8, law=law, n_sims=n_sims)
    res48 = _simulate_format(pool48, n_groups=12, law=law, n_sims=n_sims)

    ratio_rate = res48["per_game_siege_prob"] / res32["per_game_siege_prob"]
    ratio_count = res48["exp_sieges_per_tournament"] / res32["exp_sieges_per_tournament"]
    return {
        "std_of_strengths_32team": round(float(pool32.std()), 3),
        "std_of_strengths_48team": round(float(pool48.std()), 3),
        "32team": res32,
        "48team": res48,
        "per_game_expansion_multiplier": round(ratio_rate, 2),
        "per_tournament_multiplier": round(ratio_count, 2),
        "field_growth_multiplier": round(72 / 48, 2),  # the raw 1.5x, for comparison
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> None:
    tidy, synthetic = load_team_games()
    if synthetic:
        print("\n(!!) Running on SYNTHETIC data -- model output is illustrative only.\n")

    strengths = team_strengths(tidy)
    games = _games_with_gap(tidy, strengths)

    law = fit_pressure_law(games)
    print("=== Pressure law:  E[besieged SoTA] = exp(b0 + b1*|gap|) ===")
    print(f"  b0 = {law[0]:.3f}   b1 = {law[1]:.3f}   "
          f"(b1>0 => bigger mismatch, more shots faced)")

    print("\n=== Validation: does the law reproduce REAL 2026 sieges? ===")
    for k, v in validate(law, games).items():
        print(f"  {k:22s} {v}")

    print("\n=== Counterfactual: 32-team vs 48-team field, SAME law ===")
    cf = counterfactual(strengths, law)
    for k, v in cf.items():
        print(f"  {k:32s} {v}")

    print(
        "\nInterpretation: the per-game expansion multiplier is the share of the siege "
        "increase\nthat comes purely from a wider field of teams -- with football held "
        "constant."
    )


if __name__ == "__main__":
    main()
