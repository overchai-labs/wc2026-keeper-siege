"""
Step 5 -- VISUALISE
===================

The chart that should have been the original Reddit post: the FULL distribution of
per-game "siege load", 32-team era vs 2026, with no threshold doing the talking.

Two panels:
  (1) Overlaid distributions of per-game max-saves (the honest headline).
  (2) A small sensitivity strip: per-game siege probability at 6/8/10 saves, so the
      reader can see the result doesn't hinge on the cutoff.

We keep it matplotlib-only and colour-blind-safe. No chartjunk.
"""
from __future__ import annotations

import numpy as np

from . import config
from .analyze import group_stage, load_team_games, per_game_siege_load, siege_rates

# Colour-blind-safe: blue = old 32-team era, orange = new 48-team 2026.
C_OLD = "#4C72B0"
C_NEW = "#DD8452"


def _ecdf(values: np.ndarray):
    x = np.sort(values)
    y = np.arange(1, len(x) + 1) / len(x)
    return x, y


def make_figure(metric: str = "max_saves", save: bool = True):
    import matplotlib.pyplot as plt

    team_games, synthetic = load_team_games()
    per_game = per_game_siege_load(group_stage(team_games))  # group-stage comparison

    old = per_game.loc[per_game["teams"] == 32, metric].to_numpy()
    new = per_game.loc[per_game["teams"] == 48, metric].to_numpy()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [2, 1]})

    # --- Panel 1: the full distribution as complementary CDF ----------------
    # We plot P(a game has AT LEAST x saves) -- reads directly as "siege risk".
    for vals, colour, label in ((old, C_OLD, "32-team (2018+2022)"), (new, C_NEW, "48-team (2026)")):
        if len(vals) == 0:
            continue
        x, y = _ecdf(vals)
        ax1.step(x, 1 - y + 1 / len(vals), where="post", color=colour, lw=2.2, label=label)
    ax1.set_xlabel(f"{metric.replace('max_', 'max per-game ')} (besieged keeper)")
    ax1.set_ylabel("P(game reaches at least this many)")
    ax1.set_title("How often a World Cup game buries a goalkeeper")
    ax1.legend(frameon=False)
    ax1.grid(alpha=0.25)

    # --- Panel 2: sensitivity strip -----------------------------------------
    rates = siege_rates(per_game, metric)
    thresholds = config.SIEGE_THRESHOLDS
    x = np.arange(len(thresholds))
    width = 0.38
    p_old = [per_game.loc[per_game["teams"] == 32, metric].ge(t).mean() for t in thresholds]
    p_new = [per_game.loc[per_game["teams"] == 48, metric].ge(t).mean() for t in thresholds]
    ax2.bar(x - width / 2, p_old, width, color=C_OLD, label="32-team")
    ax2.bar(x + width / 2, p_new, width, color=C_NEW, label="2026")
    ax2.set_xticks(x)
    ax2.set_xticklabels([f">={t}" for t in thresholds])
    metric_label = "saves" if metric == "max_saves" else "shots on target"
    ax2.set_xlabel(f"{metric_label} threshold")
    ax2.set_ylabel("per-game probability")
    ax2.set_title("Not tuned to one cutoff")
    ax2.legend(frameon=False)
    ax2.grid(alpha=0.25, axis="y")

    tag = "  [SYNTHETIC SAMPLE DATA -- NOT REAL]" if synthetic else ""
    fig.suptitle("2026 World Cup: goalkeeper siege load vs the 32-team era" + tag, fontweight="bold")
    fig.tight_layout()

    if save:
        config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
        suffix = "_SAMPLE" if synthetic else ""
        out = config.FIGURES_DIR / f"siege_distribution_{metric}{suffix}.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print(f"[viz] wrote {out.relative_to(config.ROOT)}")
    return fig


if __name__ == "__main__":
    make_figure("max_saves")
    make_figure("max_sota")
