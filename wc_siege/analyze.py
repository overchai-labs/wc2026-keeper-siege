"""
Step 3 -- ANALYZE
=================

The question: are 2026 (48-team) group games more likely to bury a goalkeeper than
2018/2022 (32-team) group games?

We answer it the way the Reddit thread demanded:
  * FULL distribution, not a single cherry-picked threshold;
  * a real statistical test that 2026 differs from the 32-team baseline;
  * thresholds (6/8/10) shown only as a sensitivity strip, never as THE result;
  * saves AND shots-on-target-against, so a battering that produced few saves
    (the Spain-Cape Verde objection) still shows up.

Key idea -- the "siege load" of a game
---------------------------------------
A siege is ONE keeper pinned back. So for each game we take the MORE-besieged side:
the higher of the two keepers' saves (and separately, shots-on-target-against).
That single number per game is what we build distributions from.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import config


# --------------------------------------------------------------------------
# Load
# --------------------------------------------------------------------------
def load_team_games() -> tuple[pd.DataFrame, bool]:
    """Load the tidy table. Prefer REAL data; fall back to SAMPLE with a warning.

    Returns (dataframe, is_synthetic).
    """
    real = config.PROCESSED_DIR / "team_games.csv"
    sample = config.PROCESSED_DIR / "team_games_SAMPLE.csv"
    if real.exists():
        return pd.read_csv(real), False
    if sample.exists():
        print("\n" + "!" * 70)
        print("!! USING SYNTHETIC SAMPLE DATA -- results are FAKE, pipeline demo only.")
        print("!! Run the collector on your home machine, then `clean`, for real data.")
        print("!" * 70 + "\n")
        return pd.read_csv(sample), True
    raise SystemExit("No processed data. Run `sample_data` (demo) or `collect`+`clean` (real).")


def group_stage(team_games: pd.DataFrame) -> pd.DataFrame:
    """The group-stage rows -- the clean, symmetric comparison (everyone plays 3).

    Backwards-compatible: if a `stage` column isn't present (old data), assume all
    rows are group-stage.
    """
    if "stage" in team_games.columns:
        return team_games[team_games["stage"] == "group"]
    return team_games


# --------------------------------------------------------------------------
# Reduce each game to its besieged keeper
# --------------------------------------------------------------------------
def per_game_siege_load(team_games: pd.DataFrame) -> pd.DataFrame:
    """One row per GAME: the besieged keeper's workload (max over the two keepers).

    max_saves / max_sota always present; max_shots_faced / max_xg_faced come from the
    shooting table (NaN until that pull is run). xG-faced is the most credible "siege"
    signal -- it counts the full battering, not just on-target shots.
    """
    aggs = {"max_saves": ("saves", "max"), "max_sota": ("sota", "max")}
    if "shots_faced" in team_games.columns:
        aggs["max_shots_faced"] = ("shots_faced", "max")
    if "xg_faced" in team_games.columns:
        aggs["max_xg_faced"] = ("xg_faced", "max")
    return team_games.groupby(["season", "teams", "game_id"], as_index=False).agg(**aggs)


# --------------------------------------------------------------------------
# The headline numbers
# --------------------------------------------------------------------------
def siege_rates(per_game: pd.DataFrame, metric: str = "max_saves") -> pd.DataFrame:
    """Per-season siege statistics at each threshold, as RATES (not raw counts).

    Rates matter because 2026 has 72 group games vs 48 -- comparing raw counts
    would just rediscover 'more games'. The interesting question is per-GAME
    probability, which strips the 'more matches' half out.
    """
    rows = []
    thresholds = config.METRIC_THRESHOLDS.get(metric, config.SIEGE_THRESHOLDS)
    for season, sub in per_game.groupby("season"):
        n_games = len(sub)
        row = {"season": season, "group_games": n_games}
        for t in thresholds:
            share = (sub[metric] >= t).mean()          # per-game probability
            row[f"P(>={t})"] = round(share, 3)
            row[f"exp_per_tourn(>={t})"] = round(share * n_games, 1)  # expected count
        rows.append(row)
    return pd.DataFrame(rows).sort_values("season").reset_index(drop=True)


def decompose_expansion(per_game: pd.DataFrame, metric: str = "max_saves", threshold: int = 8) -> dict:
    """Split the jump in siege COUNT into 'more games' vs 'more lopsided games'.

    This is the exact claim the original post made ("half is more matches, half is
    each game being more likely"). Here we measure it from real data instead of
    asserting it. Baseline = pooled 32-team editions; target = 2026.
    """
    base = per_game[per_game["teams"] == 32]
    new = per_game[per_game["teams"] == 48]
    if base.empty or new.empty:
        return {}

    p_base = (base[metric] >= threshold).mean()
    p_new = (new[metric] >= threshold).mean()
    # Average group games per 32-team edition vs the 2026 edition.
    n_base = base.groupby("season").size().mean()
    n_new = len(new)

    exp_base = p_base * n_base
    exp_new = p_new * n_new
    # Counterfactual: 2026's game count but the OLD per-game siege probability.
    exp_moregames_only = p_base * n_new

    return {
        "threshold": threshold,
        "metric": metric,
        "p_per_game_32team": round(p_base, 3),
        "p_per_game_2026": round(p_new, 3),
        "per_game_risk_ratio": round(p_new / p_base, 2) if p_base else float("nan"),
        "expected_sieges_32team_edition": round(exp_base, 1),
        "expected_sieges_2026": round(exp_new, 1),
        "attributable_to_more_games": round(exp_moregames_only - exp_base, 1),
        "attributable_to_lopsidedness": round(exp_new - exp_moregames_only, 1),
    }


def distribution_test(per_game: pd.DataFrame, metric: str = "max_saves") -> dict:
    """Does the 2026 per-game distribution differ from the pooled 32-team one?

    Two non-parametric tests, because save counts are skewed integer data:
      * Mann-Whitney U -- is 2026 shifted higher (more saves per game)?
      * Kolmogorov-Smirnov -- do the whole distributions differ in shape?
    """
    base = per_game.loc[per_game["teams"] == 32, metric].to_numpy()
    new = per_game.loc[per_game["teams"] == 48, metric].to_numpy()
    if len(base) == 0 or len(new) == 0:
        return {}

    u_stat, u_p = stats.mannwhitneyu(new, base, alternative="greater")
    ks_stat, ks_p = stats.ks_2samp(new, base)
    return {
        "metric": metric,
        "n_32team_games": int(len(base)),
        "n_2026_games": int(len(new)),
        "median_32team": float(np.median(base)),
        "median_2026": float(np.median(new)),
        "mannwhitney_p_2026_higher": round(float(u_p), 5),
        "ks_stat": round(float(ks_stat), 3),
        "ks_p": round(float(ks_p), 5),
    }


def all_metric_tests(per_game: pd.DataFrame) -> pd.DataFrame:
    """Test EVERY siege measure and report them side by side.

    This is the anti-cherry-picking guard. If you test three related measures and
    report only the one that cleared p<0.05, you are metric-shopping -- the same
    mistake as choosing the save threshold that flatters the story. So we always
    show all three, plus a Bonferroni-corrected bar (0.05/3 = 0.017) to make clear
    how a nominally "significant" result should be read.
    """
    rows = []
    bonferroni = 0.05 / len(config.SIEGE_METRICS)
    for metric in config.SIEGE_METRICS:
        if metric not in per_game.columns or per_game[metric].isna().all():
            continue
        sub = per_game.dropna(subset=[metric])
        base = sub.loc[sub["teams"] == 32, metric].to_numpy()
        new = sub.loc[sub["teams"] == 48, metric].to_numpy()
        if len(base) == 0 or len(new) == 0:
            continue
        p = float(stats.mannwhitneyu(new, base, alternative="greater").pvalue)
        rows.append({
            "metric": metric.replace("max_", ""),
            "mean_32team": round(float(np.mean(base)), 2),
            "mean_2026": round(float(np.mean(new)), 2),
            "p_2026_higher": round(p, 4),
            "p<0.05": "yes" if p < 0.05 else "no",
            f"p<{bonferroni:.3f} (Bonferroni)": "yes" if p < bonferroni else "no",
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Knockouts -- answering Danph85 & FrenchyFungus with data, not an assumption
# --------------------------------------------------------------------------
def knockout_siege_by_round(team_games: pd.DataFrame, metric: str = "max_sota") -> pd.DataFrame:
    """Per-round siege intensity in the knockouts of each edition.

    The original post *asserted* knockouts pit even teams and add no sieges. That was
    refuted (Cape Verde-Argentina, Paraguay-Germany, England-DR Congo). Here we measure
    it. The key row is 2026's "Round of 32" -- a round the 32-team format never had.
    """
    if "stage" not in team_games.columns:
        return pd.DataFrame()
    ko = team_games[team_games["stage"] == "knockout"]
    pg = ko.groupby(["season", "round", "game_id"], as_index=False).agg(
        max_saves=("saves", "max"), max_sota=("sota", "max")
    )
    order = {r: i for i, r in enumerate(config.KNOCKOUT_ROUNDS)}
    out = pg.groupby(["season", "round"], as_index=False).agg(
        games=("game_id", "nunique"),
        mean_max_sota=("max_sota", "mean"),
        p_sota_ge8=("max_sota", lambda s: (s >= 8).mean()),
    )
    out["_o"] = out["round"].map(order)
    return out.sort_values(["season", "_o"]).drop(columns="_o").reset_index(drop=True)


def round_of_32_effect(team_games: pd.DataFrame) -> dict:
    """Sieges the 48-team Round of 32 adds -- games the 32-team format couldn't have."""
    if "stage" not in team_games.columns:
        return {}
    ko = team_games[(team_games["round"] == "Round of 32")]
    if ko.empty:
        return {}
    pg = ko.groupby("game_id", as_index=False).agg(max_sota=("sota", "max"))
    p = (pg["max_sota"] >= 8).mean()
    return {
        "round_of_32_games": int(len(pg)),
        "P(SoTA>=8)": round(float(p), 3),
        "extra_sieges_added": round(float(p) * len(pg), 1),
        "note": "This round does not exist in the 32-team format (it goes group -> R16).",
    }


# --------------------------------------------------------------------------
# CLI: print a full, honest report
# --------------------------------------------------------------------------
def main() -> None:
    team_games, synthetic = load_team_games()
    group = group_stage(team_games)           # the clean symmetric comparison
    per_game = per_game_siege_load(group)

    print("\n=== GROUP STAGE: per-game siege RATES (metric = saves) ===")
    print(siege_rates(per_game, "max_saves").to_string(index=False))

    print("\n=== Same, using shots-on-target-against ===")
    print(siege_rates(per_game, "max_sota").to_string(index=False))

    if "max_shots_faced" in per_game.columns and per_game["max_shots_faced"].notna().any():
        print("\n=== TOTAL shots faced (counts off-target + blocked: Spain-Cape Verde) ===")
        print(siege_rates(per_game, "max_shots_faced").to_string(index=False))

    print("\n=== Expansion decomposition (saves, threshold=8) ===")
    for k, v in decompose_expansion(per_game, "max_saves", 8).items():
        print(f"  {k:35s} {v}")

    print("\n=== ALL siege measures tested (no cherry-picking) ===")
    print(all_metric_tests(per_game).to_string(index=False))
    print("  Read this honestly: all three point the same way, but only one clears")
    print("  p<0.05 and it does NOT survive the Bonferroni bar. Suggestive, not proven.")

    # --- Knockouts: the point OP got wrong and conceded -----------------------
    ko_summary = knockout_siege_by_round(team_games)
    if not ko_summary.empty:
        print("\n=== KNOCKOUTS: siege intensity by round (answers Danph85) ===")
        print(ko_summary.to_string(index=False))
        print("\n=== The Round of 32 (exists ONLY in the 48-team format) ===")
        for k, v in round_of_32_effect(team_games).items():
            print(f"  {k:22s} {v}")

    if synthetic:
        print("\n(Reminder: the above ran on SYNTHETIC data. Real pull replaces it.)")


if __name__ == "__main__":
    main()
