"""
config.py -- one place for every knob, so no magic numbers hide in the code.

If a reviewer on r/dataisbeautiful asks "why 8 saves?" or "which tournaments?",
the honest answer is: it's all right here, and none of it is load-bearing.
"""
from pathlib import Path

# --- Paths -----------------------------------------------------------------
# Everything is anchored to the repo root so the code runs from anywhere.
# wc_siege/config.py -> parents[0]=wc_siege, parents[1]=repo root
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"           # committed FBref pulls (one CSV per edition)
PROCESSED_DIR = ROOT / "data" / "processed"  # tidy, analysis-ready CSVs
FIGURES_DIR = ROOT / "figures"

# --- What we pull ----------------------------------------------------------
# FBref identifies the men's World Cup as league "INT-World Cup".
# Seasons are the tournament years. 2018 & 2022 were 32-team; 2026 is 48-team.
FBREF_LEAGUE = "INT-World Cup"
SEASONS = {
    "2018": {"teams": 32, "group_games": 48},   # 8 groups of 4  -> 48 group games
    "2022": {"teams": 32, "group_games": 48},   # 8 groups of 4  -> 48 group games
    "2026": {"teams": 48, "group_games": 72},   # 12 groups of 4 -> 72 group games
}

# --- The "siege" definition ------------------------------------------------
# We deliberately do NOT hard-code a single threshold as the headline result.
# The Reddit critique was right: a cutoff turns a continuous thing binary just to
# make a scarier claim. We report the FULL distribution, and only show these
# thresholds as a sensitivity strip so the reader sees the result isn't tuned.
SIEGE_THRESHOLDS = [6, 8, 10]

# Total shots faced live on a different scale (medians ~14-15, not ~3-5), so they need
# their own thresholds. Keyed by metric so nothing silently reuses the wrong scale.
METRIC_THRESHOLDS = {
    "max_saves": [6, 8, 10],
    "max_sota": [6, 8, 10],
    "max_shots_faced": [15, 20, 25],
}

# The three siege measures we test. We report ALL of them, always -- reporting only the
# one that reached p<0.05 would be metric-shopping, the same sin as picking the cutoff
# that flatters the result. See analyze.all_metric_tests().
SIEGE_METRICS = ["max_saves", "max_sota", "max_shots_faced"]

# FBref's "INT-World Cup" bundles qualifiers + friendlies + the finals. The finals
# group stage is tagged with this exact round label. Filtering on it is what turns
# 880 raw rows into the 144 (72 games x 2 keepers) we actually want.
GROUP_STAGE_ROUND = "Group stage"

# Knockout rounds of the FINALS (exact FBref strings). These are unambiguous -- the
# qualifying play-offs use compound labels like "Second round - Semi-finals", so an
# exact match never picks up qualifier games. Crucially, "Round of 32" exists ONLY in
# the 48-team (2026) format: the 32-team format went group -> Round of 16. That extra
# round is the knockout half of the expansion effect (see Danph85's point on Reddit).
KNOCKOUT_ROUNDS = [
    "Round of 32", "Round of 16", "Quarter-finals", "Semi-finals",
    "Third-place match", "Final",
]
FINALS_ROUNDS = [GROUP_STAGE_ROUND] + KNOCKOUT_ROUNDS

# --- The better "siege" signal (answers the Spain-Cape Verde objection) -----
# Saves alone miss blocked/off-target shots, so a 74%-possession battering can
# look quiet. We carry shots-on-target-against alongside saves so the reader can
# compare. Column names are FBref's basic goalkeeping table, flattened by
# collect.py as "<group>_<stat>" (e.g. the Performance block -> Performance_Saves).
# NOTE: post-shot xG (PSxG) lives in FBref's *advanced* keeper table (keeper_adv),
# not this basic one -- a future enhancement, not needed for the headline result.
KEEPER_METRICS = {
    "saves": "Performance_Saves",  # shots saved
    "sota": "Performance_SoTA",    # shots on target against (the real "pressure" proxy)
    "ga": "Performance_GA",        # goals conceded by the keeper
}

# --- FBref stat tables we pull -------------------------------------------------
# "keeper"   -> saves / shots-on-target-against (the besieged keeper's workload)
# "shooting" -> a team's OWN total shots and xG. Paired across a game, the opponent's
#               shooting IS the pressure the keeper's side absorbed -> shots-faced and
#               xG-faced. xG-faced is the credible "siege" signal that answers the
#               Spain 0-0 Cape Verde objection (27 shots, 2.1 xG, but only 7 on target).
STAT_TYPES = ["keeper", "shooting"]

# Total-shots and xG columns in FBref's shooting table are matched fuzzily in clean.py
# (their exact flattened names, e.g. "Standard_Sh" / "Expected_xG", are confirmed after
# the first real pull). These regexes identify them regardless of the header grouping.
SHOOTING_SHOTS_RE = r"(^|_)Sh$"    # total shots (NOT SoT / Sh/90 / etc.)
SHOOTING_XG_RE = r"(^|_)xG$"       # expected goals (NOT npxG / xGA)
