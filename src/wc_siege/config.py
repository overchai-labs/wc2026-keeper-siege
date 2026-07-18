"""
config.py -- one place for every knob, so no magic numbers hide in the code.

If a reviewer on r/dataisbeautiful asks "why 8 saves?" or "which tournaments?",
the honest answer is: it's all right here, and none of it is load-bearing.
"""
from pathlib import Path

# --- Paths -----------------------------------------------------------------
# Everything is anchored to the repo root so the code runs from anywhere.
ROOT = Path(__file__).resolve().parents[2]
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

# --- The better "siege" signal (answers the Spain-Cape Verde objection) -----
# Saves alone miss blocked/off-target shots, so a 74%-possession battering can
# look quiet. We carry shots-on-target-against and post-shot xG alongside saves
# and let the reader compare. These are the FBref goalkeeping columns we keep.
KEEPER_METRICS = {
    "saves": "Saves",            # shots saved
    "sota": "SoTA",              # shots on target against (the real "pressure" proxy)
    "psxg": "PSxG",              # post-shot expected goals faced (shot quality faced)
    "ga": "GA",                  # goals against
}
